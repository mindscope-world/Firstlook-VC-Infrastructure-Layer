// Deal sourcing: theses (versioned), the ranked feed, feedback and re-runs.
// Scoring runs in the Python sourcing service; requests reach it through the
// outbox (topics sourcing.requested and sourcing.feedback).

import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { requireAuth, requirePermission } from "../lib/auth.js";
import { audit, enqueue, scopeOf, withTenant, type Tx } from "../lib/db.js";

const uuid = z.string().uuid();

// Mirrors services/sourcing/src/firstlook_sourcing/taxonomy.py.
export const TAXONOMY = {
  sectors: ["fintech", "insurtech", "agritech", "healthtech", "edtech", "logistics", "commerce", "climate", "mobility", "proptech", "saas", "devtools", "ai", "media"],
  stages: ["pre-seed", "seed", "series-a", "series-b", "series-c", "growth"],
  regions: ["africa", "east-africa", "west-africa", "southern-africa", "north-africa", "central-africa"],
};

const thesisBody = z.object({
  name: z.string().min(1).max(120),
  sectors: z.array(z.enum(TAXONOMY.sectors as [string, ...string[]])).default([]),
  stages: z.array(z.enum(TAXONOMY.stages as [string, ...string[]])).default([]),
  // Regions from the list, or ISO country codes.
  geographies: z.array(z.string().regex(/^([a-z-]+|[A-Z]{2})$/)).default([]),
  cheque_min_usd: z.number().nonnegative().nullable().default(null),
  cheque_max_usd: z.number().positive().nullable().default(null),
  founder_profile: z.string().max(2000).default(""),
  description: z.string().max(4000).default(""),
});

async function insertVersion(tx: Tx, tenantId: string, thesisId: string, version: number, b: z.infer<typeof thesisBody>, userId: string) {
  const { rows } = await tx.query(
    `INSERT INTO thesis_versions (tenant_id, thesis_id, version, sectors, stages, geographies, cheque_min_usd, cheque_max_usd,
                                  founder_profile, description, created_by)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) RETURNING id`,
    [tenantId, thesisId, version, b.sectors, b.stages, b.geographies, b.cheque_min_usd, b.cheque_max_usd, b.founder_profile, b.description, userId],
  );
  return rows[0].id as string;
}

export async function sourcingRoutes(app: FastifyInstance) {
  app.addHook("preHandler", requireAuth);

  app.get("/sourcing/taxonomy", async () => TAXONOMY);

  app.get("/theses", async (req) =>
    withTenant(scopeOf(req.principal), async (tx) => {
      const { rows } = await tx.query(`
        SELECT v.thesis_id AS id, v.name, v.active, v.version, v.id AS version_id, v.sectors, v.stages, v.geographies,
               v.cheque_min_usd, v.cheque_max_usd, v.founder_profile, v.description, v.created_at AS updated_at,
               (SELECT json_build_object('id', r.id, 'status', r.status, 'finished_at', r.finished_at, 'scored', r.scored,
                                         'ranker', r.ranker, 'rerank_model', r.rerank_model)
                  FROM score_runs r JOIN thesis_versions tv ON tv.id = r.thesis_version_id
                 WHERE tv.thesis_id = v.thesis_id ORDER BY r.started_at DESC LIMIT 1) AS last_run,
               (SELECT count(*) FROM sourcing_feedback f WHERE f.thesis_id = v.thesis_id) AS labels
          FROM current_thesis_versions v ORDER BY v.active DESC, v.name`);
      return rows;
    }),
  );

  app.get("/theses/:id/versions", async (req) => {
    const { id } = z.object({ id: uuid }).parse(req.params);
    return withTenant(scopeOf(req.principal), async (tx) => {
      const { rows } = await tx.query(
        `SELECT v.id, v.version, v.sectors, v.stages, v.geographies, v.cheque_min_usd, v.cheque_max_usd, v.founder_profile,
                v.description, v.created_at, u.name AS created_by
           FROM thesis_versions v LEFT JOIN users u ON u.id = v.created_by
          WHERE v.thesis_id = $1 ORDER BY v.version DESC`,
        [id],
      );
      return rows;
    });
  });

  app.post("/theses", { preHandler: requirePermission("theses:write") }, async (req, reply) => {
    const body = thesisBody.parse(req.body);
    const scope = scopeOf(req.principal);
    return withTenant(scope, async (tx) => {
      const t = await tx.query("INSERT INTO theses (tenant_id, name, created_by) VALUES ($1, $2, $3) RETURNING id", [scope.tenantId, body.name, scope.userId]);
      const thesisId = t.rows[0].id as string;
      const versionId = await insertVersion(tx, scope.tenantId, thesisId, 1, body, scope.userId!);
      await audit(tx, scope, "thesis.created", "thesis", thesisId, { version: 1 });
      await enqueue(tx, scope.tenantId, "sourcing.requested", { thesis_version_id: versionId, reason: "thesis_created" }, thesisId);
      return reply.code(201).send({ id: thesisId, version_id: versionId, version: 1 });
    });
  });

  // Editing a thesis creates a new version; earlier scores keep pointing at theirs.
  app.put("/theses/:id", { preHandler: requirePermission("theses:write") }, async (req, reply) => {
    const { id } = z.object({ id: uuid }).parse(req.params);
    const body = thesisBody.parse(req.body);
    const scope = scopeOf(req.principal);
    return withTenant(scope, async (tx) => {
      const cur = await tx.query("SELECT max(version) AS v FROM thesis_versions WHERE thesis_id = $1", [id]);
      if (cur.rows[0].v === null) return reply.code(404).send({ error: "not found" });
      const version = Number(cur.rows[0].v) + 1;
      await tx.query("UPDATE theses SET name = $2 WHERE id = $1", [id, body.name]);
      const versionId = await insertVersion(tx, scope.tenantId, id, version, body, scope.userId!);
      await audit(tx, scope, "thesis.updated", "thesis", id, { version });
      await enqueue(tx, scope.tenantId, "sourcing.requested", { thesis_version_id: versionId, reason: "thesis_updated" }, id);
      return { id, version_id: versionId, version };
    });
  });

  app.patch("/theses/:id", { preHandler: requirePermission("theses:write") }, async (req, reply) => {
    const { id } = z.object({ id: uuid }).parse(req.params);
    const { active } = z.object({ active: z.boolean() }).parse(req.body);
    const scope = scopeOf(req.principal);
    return withTenant(scope, async (tx) => {
      const { rowCount } = await tx.query("UPDATE theses SET active = $2 WHERE id = $1", [id, active]);
      if (!rowCount) return reply.code(404).send({ error: "not found" });
      await audit(tx, scope, active ? "thesis.activated" : "thesis.archived", "thesis", id);
      return { id, active };
    });
  });

  app.get("/sourcing/feed", async (req, reply) => {
    const q = z
      .object({
        thesis: uuid,
        limit: z.coerce.number().int().min(1).max(200).default(50),
        hide_pipeline: z.enum(["true", "false"]).default("false"),
        hide_downvoted: z.enum(["true", "false"]).default("true"),
      })
      .parse(req.query);
    const scope = scopeOf(req.principal);
    return withTenant(scope, async (tx) => {
      const run = await tx.query(
        `SELECT r.id, r.ranker, r.rerank_model, r.finished_at, r.candidates, r.scored, r.reranked, v.version
           FROM score_runs r JOIN thesis_versions v ON v.id = r.thesis_version_id
          WHERE v.thesis_id = $1 AND r.status = 'done' ORDER BY r.started_at DESC LIMIT 1`,
        [q.thesis],
      );
      if (run.rows.length === 0) return reply.send({ run: null, items: [] });
      const { rows } = await tx.query(
        `SELECT s.company_id, c.name, c.domain, c.country, c.stage, c.sectors, c.description, c.last_round_usd, c.last_round_at,
                s.rank, s.stage1_score, s.stage2_score, s.final_score, s.features, s.rationale, s.concerns, s.citations,
                (SELECT d.stage FROM deals d WHERE d.company_id = c.id ORDER BY d.updated_at DESC LIMIT 1) AS deal_stage,
                (SELECT f.vote FROM sourcing_feedback f WHERE f.thesis_id = $2 AND f.company_id = c.id AND f.user_id = $3) AS my_vote,
                (SELECT coalesce(sum(f.vote), 0) FROM sourcing_feedback f WHERE f.thesis_id = $2 AND f.company_id = c.id) AS team_votes,
                NOT EXISTS (SELECT 1 FROM company_scores p JOIN score_runs r2 ON r2.id = p.run_id JOIN thesis_versions v2 ON v2.id = r2.thesis_version_id
                             WHERE v2.thesis_id = $2 AND p.company_id = c.id AND p.run_id <> s.run_id
                               AND r2.started_at < now() - interval '7 days') AS new_this_week
           FROM company_scores s JOIN companies c ON c.id = s.company_id
          WHERE s.run_id = $1
            AND ($4::boolean IS FALSE OR NOT EXISTS (SELECT 1 FROM deals d WHERE d.company_id = c.id))
            AND ($5::boolean IS FALSE OR NOT EXISTS (SELECT 1 FROM sourcing_feedback f WHERE f.thesis_id = $2 AND f.company_id = c.id AND f.user_id = $3 AND f.vote < 0))
          ORDER BY s.rank LIMIT $6`,
        [run.rows[0].id, q.thesis, scope.userId, q.hide_pipeline === "true", q.hide_downvoted === "true", q.limit],
      );
      return { run: run.rows[0], items: rows };
    });
  });

  app.post("/sourcing/feedback", { preHandler: requirePermission("sourcing:feedback") }, async (req) => {
    const b = z
      .object({ thesis_id: uuid, company_id: uuid, vote: z.union([z.literal(1), z.literal(-1), z.literal(0)]), reason: z.string().max(500).optional() })
      .parse(req.body);
    const scope = scopeOf(req.principal);
    return withTenant(scope, async (tx) => {
      if (b.vote === 0) {
        await tx.query("DELETE FROM sourcing_feedback WHERE thesis_id = $1 AND company_id = $2 AND user_id = $3", [b.thesis_id, b.company_id, scope.userId]);
        return { vote: 0 };
      }
      // Store the features the user was looking at, so training learns from what they saw.
      const latest = await tx.query(
        `SELECT s.thesis_version_id, s.features FROM company_scores s JOIN thesis_versions v ON v.id = s.thesis_version_id
          WHERE v.thesis_id = $1 AND s.company_id = $2 ORDER BY s.created_at DESC LIMIT 1`,
        [b.thesis_id, b.company_id],
      );
      const version =
        latest.rows[0]?.thesis_version_id ??
        (await tx.query("SELECT id FROM current_thesis_versions WHERE thesis_id = $1", [b.thesis_id])).rows[0]?.id;
      await tx.query(
        `INSERT INTO sourcing_feedback (tenant_id, thesis_id, thesis_version_id, company_id, user_id, vote, reason, features)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
         ON CONFLICT (thesis_id, company_id, user_id) DO UPDATE SET vote = EXCLUDED.vote, reason = EXCLUDED.reason,
           features = EXCLUDED.features, thesis_version_id = EXCLUDED.thesis_version_id, updated_at = now()`,
        [scope.tenantId, b.thesis_id, version, b.company_id, scope.userId, b.vote, b.reason ?? null, latest.rows[0]?.features ?? {}],
      );
      await enqueue(tx, scope.tenantId, "sourcing.feedback", { thesis_id: b.thesis_id }, b.thesis_id);
      return { vote: b.vote };
    });
  });

  app.post("/sourcing/run", { preHandler: requirePermission("theses:write") }, async (req) => {
    const b = z.object({ thesis_id: uuid.optional(), collect: z.boolean().default(false) }).parse(req.body ?? {});
    const scope = scopeOf(req.principal);
    return withTenant(scope, async (tx) => {
      let versionId: string | null = null;
      if (b.thesis_id) {
        versionId = (await tx.query("SELECT id FROM current_thesis_versions WHERE thesis_id = $1", [b.thesis_id])).rows[0]?.id ?? null;
      }
      await enqueue(tx, scope.tenantId, "sourcing.requested", { thesis_version_id: versionId, collect: b.collect, reason: "manual" });
      await audit(tx, scope, "sourcing.run_requested", "thesis", b.thesis_id ?? null, { collect: b.collect });
      return { queued: true };
    });
  });

  app.get("/companies/:id/signals", async (req) => {
    const { id } = z.object({ id: uuid }).parse(req.params);
    return withTenant(scopeOf(req.principal), async (tx) => {
      const { rows } = await tx.query(
        `SELECT signal, value, source, url, detail, observed_at FROM signal_observations
          WHERE company_id = $1 ORDER BY observed_at DESC LIMIT 200`,
        [id],
      );
      return rows;
    });
  });
}
