// Human-in-the-loop decisions: entity-resolution review queue, proposed
// extractions, and deals. The decision logic lives in SQL functions
// (packages/schema) so every service applies it the same way.

import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { can, requireAuth, requirePermission } from "../lib/auth.js";
import { audit, enqueue, scopeOf, withTenant } from "../lib/db.js";

const uuid = z.string().uuid();
export const STAGES = ["sourced", "screening", "diligence", "ic", "term_sheet", "invested", "passed"] as const;

function pgError(err: unknown): { status: number; message: string } | null {
  const e = err as { code?: string; message?: string };
  if (e.code === "P0001") return { status: 409, message: e.message ?? "conflict" };
  if (e.code === "42501") return { status: 403, message: "not permitted" };
  return null;
}

export async function workflowRoutes(app: FastifyInstance) {
  app.addHook("preHandler", requireAuth);

  // -- entity resolution review queue --------------------------------------

  app.get("/review", async (req) =>
    withTenant(scopeOf(req.principal), async (tx) => {
      const { rows } = await tx.query(`
        SELECT c.id, c.entity_type, c.mention, c.score, c.features, c.created_at,
               json_build_object('id', pe.id, 'name', pe.canonical_name, 'title', pp.title, 'company', pc.name,
                 'identifiers', (SELECT json_agg(i.value) FROM identifiers i WHERE i.entity_id = pe.id),
                 'interactions', (SELECT count(*) FROM interaction_participants ip WHERE ip.person_id = pe.id)) AS provisional,
               json_build_object('id', ce.id, 'name', ce.canonical_name, 'title', cp.title, 'company', cc.name,
                 'identifiers', (SELECT json_agg(i.value) FROM identifiers i WHERE i.entity_id = ce.id),
                 'interactions', (SELECT count(*) FROM interaction_participants ip WHERE ip.person_id = ce.id)) AS candidate,
               s.connector AS source
          FROM er_candidates c
          JOIN entities pe ON pe.id = c.provisional_entity_id
          JOIN entities ce ON ce.id = c.candidate_entity_id
          LEFT JOIN people pp ON pp.id = pe.id LEFT JOIN companies pc ON pc.id = pp.company_id
          LEFT JOIN people cp ON cp.id = ce.id LEFT JOIN companies cc ON cc.id = cp.company_id
          LEFT JOIN sources s ON s.id = c.source_id
         WHERE c.status = 'pending'
         ORDER BY c.score DESC, c.created_at`);
      return rows;
    }),
  );

  app.post("/review/:id", { preHandler: requirePermission("review:decide") }, async (req, reply) => {
    const { id } = z.object({ id: uuid }).parse(req.params);
    const { decision } = z.object({ decision: z.enum(["merged", "distinct"]) }).parse(req.body);
    try {
      await withTenant(scopeOf(req.principal), (tx) =>
        tx.query("SELECT er_decide($1, $2, $3)", [id, decision, req.principal.userId]),
      );
    } catch (err) {
      const e = pgError(err);
      if (e) return reply.code(e.status).send({ error: e.message });
      throw err;
    }
    return { id, decision };
  });

  // -- extractions -----------------------------------------------------------

  app.get("/extractions", async (req) => {
    const q = z
      .object({
        status: z.enum(["proposed", "accepted", "rejected", "done"]).optional(),
        kind: z.enum(["intro", "next_step", "deal_mention"]).optional(),
        limit: z.coerce.number().int().min(1).max(200).default(100),
      })
      .parse(req.query);
    return withTenant(scopeOf(req.principal), async (tx) => {
      const { rows } = await tx.query(
        `SELECT x.id, x.kind, x.payload, x.citations, x.confidence, x.status, x.model, x.created_at, x.decided_at,
                i.id AS interaction_id, i.subject, i.occurred_at, i.kind AS interaction_kind
           FROM extractions x JOIN interactions i ON i.id = x.interaction_id
          WHERE ($1::text IS NULL OR x.status = $1) AND ($2::text IS NULL OR x.kind = $2)
          ORDER BY i.occurred_at DESC, x.kind LIMIT $3`,
        [q.status ?? null, q.kind ?? null, q.limit],
      );
      return rows;
    });
  });

  app.post("/extractions/:id", { preHandler: requirePermission("extractions:decide") }, async (req, reply) => {
    const { id } = z.object({ id: uuid }).parse(req.params);
    const { decision } = z.object({ decision: z.enum(["accepted", "rejected", "done"]) }).parse(req.body);
    try {
      const dealId = await withTenant(scopeOf(req.principal), async (tx) => {
        const { rows } = await tx.query("SELECT decide_extraction($1, $2, $3) AS deal_id", [
          id,
          decision,
          req.principal.userId,
        ]);
        return rows[0]?.deal_id ?? null;
      });
      return { id, decision, deal_id: dealId };
    } catch (err) {
      const e = pgError(err);
      if (e) return reply.code(e.status).send({ error: e.message });
      throw err;
    }
  });

  // -- deals -----------------------------------------------------------------

  app.get("/deals", async (req) =>
    withTenant(scopeOf(req.principal), async (tx) => {
      const { rows } = await tx.query(`
        SELECT d.id, d.name, d.stage, d.restricted, d.round_size_usd, d.created_at, d.updated_at,
               c.id AS company_id, c.name AS company, c.domain,
               (SELECT json_agg(json_build_object('id', u.id, 'name', u.name)) FROM deal_team_members m JOIN users u ON u.id = m.user_id WHERE m.deal_id = d.id) AS team,
               (SELECT max(i.occurred_at) FROM interactions i WHERE i.deal_id = d.id) AS last_interaction_at
          FROM deals d LEFT JOIN companies c ON c.id = d.company_id
          JOIN entities e ON e.id = d.id AND e.merged_into IS NULL
         ORDER BY d.updated_at DESC`);
      return rows;
    }),
  );

  app.post("/deals", { preHandler: requirePermission("deals:write") }, async (req, reply) => {
    const body = z
      .object({
        name: z.string().min(1),
        company_id: uuid.optional(),
        stage: z.enum(STAGES).default("sourced"),
        restricted: z.boolean().default(false),
        round_size_usd: z.number().positive().optional(),
      })
      .parse(req.body);
    if (body.restricted && !can(req.principal, "deals:restrict")) {
      return reply.code(403).send({ error: "only partners can create restricted deals" });
    }
    const scope = scopeOf(req.principal);
    return withTenant(scope, async (tx) => {
      const entity = await tx.query("INSERT INTO entities (tenant_id, type, canonical_name) VALUES ($1, 'deal', $2) RETURNING id", [
        scope.tenantId,
        body.name,
      ]);
      const id = entity.rows[0].id as string;
      await tx.query(
        "INSERT INTO deals (id, tenant_id, company_id, name, stage, restricted, round_size_usd, created_by) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
        [id, scope.tenantId, body.company_id ?? null, body.name, body.stage, body.restricted, body.round_size_usd ?? null, scope.userId],
      );
      // The creator is always on the deal team, so a restricted deal stays visible to them.
      await tx.query("INSERT INTO deal_team_members (tenant_id, deal_id, user_id) VALUES ($1, $2, $3)", [scope.tenantId, id, scope.userId]);
      await audit(tx, scope, "deal.created", "deal", id, { stage: body.stage, restricted: body.restricted });
      await enqueue(tx, scope.tenantId, "deals.events", { type: "deal.created", deal_id: id, name: body.name, stage: body.stage, actor_id: scope.userId }, id);
      return reply.code(201).send({ id });
    });
  });

  app.patch("/deals/:id", { preHandler: requirePermission("deals:write") }, async (req, reply) => {
    const { id } = z.object({ id: uuid }).parse(req.params);
    const body = z.object({ stage: z.enum(STAGES).optional(), restricted: z.boolean().optional() }).parse(req.body);
    if (body.restricted !== undefined && !can(req.principal, "deals:restrict")) {
      return reply.code(403).send({ error: "only partners can change deal restriction" });
    }
    const scope = scopeOf(req.principal);
    return withTenant(scope, async (tx) => {
      const before = await tx.query("SELECT name, stage, restricted FROM deals WHERE id = $1 FOR UPDATE", [id]);
      if (before.rows.length === 0) return reply.code(404).send({ error: "not found" });
      const prev = before.rows[0];
      await tx.query(
        "UPDATE deals SET stage = coalesce($2, stage), restricted = coalesce($3, restricted), updated_at = now() WHERE id = $1",
        [id, body.stage ?? null, body.restricted ?? null],
      );
      await audit(tx, scope, "deal.updated", "deal", id, { from: prev, to: body });
      if (body.stage && body.stage !== prev.stage) {
        const actor = await tx.query("SELECT name FROM users WHERE id = $1", [scope.userId]);
        await enqueue(
          tx,
          scope.tenantId,
          "deals.events",
          { type: "deal.stage_changed", deal_id: id, name: prev.name, from_stage: prev.stage, stage: body.stage, actor_id: scope.userId, actor_name: actor.rows[0]?.name },
          id,
        );
      }
      return { id, ...body };
    });
  });

  app.post("/deals/:id/team", { preHandler: requirePermission("deals:write") }, async (req, reply) => {
    const { id } = z.object({ id: uuid }).parse(req.params);
    const { user_id } = z.object({ user_id: uuid }).parse(req.body);
    const scope = scopeOf(req.principal);
    return withTenant(scope, async (tx) => {
      const deal = await tx.query("SELECT 1 FROM deals WHERE id = $1", [id]);
      if (deal.rows.length === 0) return reply.code(404).send({ error: "not found" });
      await tx.query("INSERT INTO deal_team_members (tenant_id, deal_id, user_id) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING", [
        scope.tenantId,
        id,
        user_id,
      ]);
      await audit(tx, scope, "deal.team_added", "deal", id, { user_id });
      return { id, user_id };
    });
  });

  app.get("/team", async (req) =>
    withTenant(scopeOf(req.principal), async (tx) => {
      const { rows } = await tx.query("SELECT id, name, email, role FROM users ORDER BY name");
      return rows;
    }),
  );

  app.get("/audit", { preHandler: requirePermission("audit:read") }, async (req) => {
    const q = z.object({ limit: z.coerce.number().int().min(1).max(500).default(100) }).parse(req.query);
    return withTenant(scopeOf(req.principal), async (tx) => {
      const { rows } = await tx.query(
        `SELECT a.id, a.actor_type, u.name AS actor, a.action, a.resource_type, a.resource_id, a.details, a.created_at
           FROM audit_events a LEFT JOIN users u ON u.id = a.actor_id ORDER BY a.id DESC LIMIT $1`,
        [q.limit],
      );
      return rows;
    });
  });
}
