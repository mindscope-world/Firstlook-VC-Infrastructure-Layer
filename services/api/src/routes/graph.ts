import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { requireAuth, requirePermission } from "../lib/auth.js";
import { scopeOf, withTenant, type Tx } from "../lib/db.js";

const uuid = z.string().uuid();
const page = z.object({ limit: z.coerce.number().int().min(1).max(200).default(50), offset: z.coerce.number().int().min(0).default(0) });

/** Warm paths with names attached. Shared by the web UI and the Slack command. */
export async function warmPaths(tx: Tx, target: string, limit = 5) {
  const { rows } = await tx.query(
    `SELECT w.path, w.score, w.hops, w.edge_types,
            (SELECT json_agg(json_build_object('id', e.id, 'name', e.canonical_name,
                     'internal', coalesce(p.is_internal, false), 'title', p.title) ORDER BY o.ord)
               FROM unnest(w.path) WITH ORDINALITY AS o(id, ord)
               JOIN entities e ON e.id = o.id LEFT JOIN people p ON p.id = e.id) AS people
       FROM warm_paths($1, 3, $2) w`,
    [target, limit],
  );
  return rows;
}

export async function graphRoutes(app: FastifyInstance) {
  app.addHook("preHandler", requireAuth);
  app.addHook("preHandler", requirePermission("graph:read"));

  app.get("/dashboard", async (req) =>
    withTenant(scopeOf(req.principal), async (tx) => {
      const counts = await tx.query(`
        SELECT
          (SELECT count(*) FROM interactions WHERE occurred_at > now() - interval '30 days') AS interactions_30d,
          (SELECT count(*) FROM people p JOIN entities e ON e.id = p.id WHERE e.merged_into IS NULL AND NOT p.is_internal) AS people,
          (SELECT count(*) FROM companies c JOIN entities e ON e.id = c.id WHERE e.merged_into IS NULL) AS companies,
          (SELECT count(*) FROM deals) AS deals,
          (SELECT count(*) FROM er_candidates WHERE status = 'pending') AS review_pending,
          (SELECT count(*) FROM extractions WHERE status = 'proposed') AS extractions_proposed,
          (SELECT count(*) FROM extractions WHERE kind = 'next_step' AND status = 'accepted') AS next_steps_open`);
      const recent = await tx.query(`
        SELECT i.id, i.kind, i.subject, i.occurred_at, i.direction,
               (SELECT string_agg(coalesce(ip.display_name, ip.email::text), ', ')
                  FROM interaction_participants ip WHERE ip.interaction_id = i.id AND ip.role IN ('from', 'organizer', 'speaker')) AS from_names
          FROM interactions i ORDER BY i.occurred_at DESC LIMIT 8`);
      const strongest = await tx.query(`
        SELECT e.dst_id AS person_id, px.full_name, c.name AS company, max((e.props->>'strength')::float) AS strength
          FROM edges e JOIN people px ON px.id = e.dst_id LEFT JOIN companies c ON c.id = px.company_id
         WHERE e.type = 'knows' AND e.valid_to IS NULL
         GROUP BY e.dst_id, px.full_name, c.name ORDER BY strength DESC LIMIT 8`);
      return { counts: counts.rows[0], recent: recent.rows, strongest: strongest.rows };
    }),
  );

  app.get("/interactions", async (req) => {
    const q = page.extend({ kind: z.string().optional(), q: z.string().optional(), person: uuid.optional(), company: uuid.optional() }).parse(req.query);
    return withTenant(scopeOf(req.principal), async (tx) => {
      const { rows } = await tx.query(
        `SELECT i.id, i.kind, i.subject, i.occurred_at, i.direction, i.visibility, left(i.body_text, 240) AS snippet,
                (SELECT json_agg(json_build_object('name', coalesce(ip.display_name, ip.email::text), 'email', ip.email, 'role', ip.role, 'person_id', ip.person_id))
                   FROM interaction_participants ip WHERE ip.interaction_id = i.id) AS participants,
                (SELECT count(*) FROM extractions x WHERE x.interaction_id = i.id) AS extraction_count
           FROM interactions i
          WHERE ($1::text IS NULL OR i.kind::text = $1)
            AND ($2::text IS NULL OR i.subject ILIKE '%' || $2 || '%' OR i.body_text ILIKE '%' || $2 || '%')
            AND ($3::uuid IS NULL OR EXISTS (SELECT 1 FROM interaction_participants ip WHERE ip.interaction_id = i.id AND ip.person_id = $3))
            AND ($4::uuid IS NULL OR EXISTS (SELECT 1 FROM interaction_participants ip JOIN people p ON p.id = ip.person_id
                                              WHERE ip.interaction_id = i.id AND p.company_id = $4))
          ORDER BY i.occurred_at DESC LIMIT $5 OFFSET $6`,
        [q.kind ?? null, q.q ?? null, q.person ?? null, q.company ?? null, q.limit, q.offset],
      );
      return rows;
    });
  });

  app.get("/interactions/:id", async (req, reply) => {
    const { id } = z.object({ id: uuid }).parse(req.params);
    return withTenant(scopeOf(req.principal), async (tx) => {
      const { rows } = await tx.query(
        `SELECT i.id, i.kind, i.external_id, i.thread_id, i.subject, i.occurred_at, i.direction, i.visibility,
                i.body_text, i.signature, i.metadata, i.deal_id
           FROM interactions i WHERE i.id = $1`,
        [id],
      );
      if (rows.length === 0) return reply.code(404).send({ error: "not found" });
      // Sequential: a pg client runs one query at a time.
      const participants = await tx.query(
          `SELECT ip.role, ip.email, ip.display_name, ip.person_id, p.full_name, p.title, p.is_internal
             FROM interaction_participants ip LEFT JOIN people p ON p.id = ip.person_id WHERE ip.interaction_id = $1`,
          [id],
        );
      const attachments = await tx.query("SELECT id, filename, content_type, size_bytes FROM attachments WHERE interaction_id = $1", [id]);
      const extractions = await tx.query(
          "SELECT id, kind, payload, citations, confidence, status, model, created_at FROM extractions WHERE interaction_id = $1 ORDER BY kind, created_at",
          [id],
        );
      const thread = await tx.query(
          "SELECT id, subject, occurred_at, direction FROM interactions WHERE thread_id = $1 AND thread_id IS NOT NULL ORDER BY occurred_at",
          [rows[0].thread_id],
        );
      return { ...rows[0], participants: participants.rows, attachments: attachments.rows, extractions: extractions.rows, thread: thread.rows };
    });
  });

  app.get("/people", async (req) => {
    const q = page.extend({ q: z.string().optional(), internal: z.enum(["true", "false"]).optional() }).parse(req.query);
    return withTenant(scopeOf(req.principal), async (tx) => {
      const { rows } = await tx.query(
        `SELECT p.id, p.full_name, p.primary_email, p.title, p.is_internal, c.id AS company_id, c.name AS company,
                (SELECT max((e.props->>'strength')::float) FROM edges e WHERE e.dst_id = p.id AND e.type = 'knows' AND e.valid_to IS NULL) AS strength,
                (SELECT max(i.occurred_at) FROM interaction_participants ip JOIN interactions i ON i.id = ip.interaction_id WHERE ip.person_id = p.id) AS last_interaction_at
           FROM people p JOIN entities e ON e.id = p.id LEFT JOIN companies c ON c.id = p.company_id
          WHERE e.merged_into IS NULL
            AND ($1::text IS NULL OR p.full_name ILIKE '%' || $1 || '%' OR p.primary_email ILIKE '%' || $1 || '%' OR c.name ILIKE '%' || $1 || '%')
            AND ($2::boolean IS NULL OR p.is_internal = $2)
          ORDER BY strength DESC NULLS LAST, p.full_name LIMIT $3 OFFSET $4`,
        [q.q ?? null, q.internal === undefined ? null : q.internal === "true", q.limit, q.offset],
      );
      return rows;
    });
  });

  app.get("/people/:id", async (req, reply) => {
    const { id } = z.object({ id: uuid }).parse(req.params);
    return withTenant(scopeOf(req.principal), async (tx) => {
      const person = await tx.query(
        `SELECT p.id, p.full_name, p.primary_email, p.title, p.is_internal, e.merged_into, c.id AS company_id, c.name AS company, c.domain AS company_domain
           FROM people p JOIN entities e ON e.id = p.id LEFT JOIN companies c ON c.id = p.company_id WHERE p.id = $1`,
        [id],
      );
      if (person.rows.length === 0) return reply.code(404).send({ error: "not found" });
      if (person.rows[0].merged_into) return reply.code(301).send({ redirect: person.rows[0].merged_into });
      // Sequential: a pg client runs one query at a time.
      const identifiers = await tx.query("SELECT kind, value FROM identifiers WHERE entity_id = $1 ORDER BY kind, value", [id]);
      const relationships = await tx.query(
          `SELECT e.src_id AS team_person_id, pi.full_name AS team_member, e.props
             FROM edges e JOIN people pi ON pi.id = e.src_id
            WHERE e.dst_id = $1 AND e.type = 'knows' AND e.valid_to IS NULL
            ORDER BY (e.props->>'strength')::float DESC`,
          [id],
        );
      const related = await tx.query(
          `SELECT CASE WHEN e.src_id = $1 THEN e.dst_id ELSE e.src_id END AS person_id, p.full_name, e.type, e.props
             FROM edges e JOIN people p ON p.id = CASE WHEN e.src_id = $1 THEN e.dst_id ELSE e.src_id END
            WHERE (e.src_id = $1 OR e.dst_id = $1) AND e.type IN ('co_occurs', 'introduced') AND e.valid_to IS NULL
            ORDER BY (e.props->>'strength')::float DESC NULLS LAST LIMIT 20`,
          [id],
        );
      const interactions = await tx.query(
          `SELECT i.id, i.kind, i.subject, i.occurred_at, i.direction FROM interactions i
            WHERE EXISTS (SELECT 1 FROM interaction_participants ip WHERE ip.interaction_id = i.id AND ip.person_id = $1)
            ORDER BY i.occurred_at DESC LIMIT 25`,
          [id],
        );
      const review = await tx.query(
          "SELECT id, score FROM er_candidates WHERE status = 'pending' AND (provisional_entity_id = $1 OR candidate_entity_id = $1)",
          [id],
        );
      return {
        ...person.rows[0],
        identifiers: identifiers.rows,
        relationships: relationships.rows,
        related: related.rows,
        interactions: interactions.rows,
        pending_review: review.rows,
        warm_paths: person.rows[0].is_internal ? [] : await warmPaths(tx, id),
      };
    });
  });

  app.get("/companies", async (req) => {
    const q = page.extend({ q: z.string().optional() }).parse(req.query);
    return withTenant(scopeOf(req.principal), async (tx) => {
      const { rows } = await tx.query(
        `SELECT c.id, c.name, c.domain, c.country, c.description,
                (SELECT count(*) FROM people p JOIN entities pe ON pe.id = p.id WHERE p.company_id = c.id AND pe.merged_into IS NULL) AS people,
                (SELECT d.stage FROM deals d WHERE d.company_id = c.id ORDER BY d.updated_at DESC LIMIT 1) AS deal_stage,
                (SELECT max(i.occurred_at) FROM interactions i JOIN interaction_participants ip ON ip.interaction_id = i.id
                   JOIN people p ON p.id = ip.person_id WHERE p.company_id = c.id) AS last_interaction_at
           FROM companies c JOIN entities e ON e.id = c.id
          WHERE e.merged_into IS NULL AND ($1::text IS NULL OR c.name ILIKE '%' || $1 || '%' OR c.domain ILIKE '%' || $1 || '%')
          ORDER BY last_interaction_at DESC NULLS LAST, c.name LIMIT $2 OFFSET $3`,
        [q.q ?? null, q.limit, q.offset],
      );
      return rows;
    });
  });

  app.get("/companies/:id", async (req, reply) => {
    const { id } = z.object({ id: uuid }).parse(req.params);
    return withTenant(scopeOf(req.principal), async (tx) => {
      const company = await tx.query("SELECT c.*, e.merged_into FROM companies c JOIN entities e ON e.id = c.id WHERE c.id = $1", [id]);
      if (company.rows.length === 0) return reply.code(404).send({ error: "not found" });
      if (company.rows[0].merged_into) return reply.code(301).send({ redirect: company.rows[0].merged_into });
      // Sequential: a pg client runs one query at a time.
      const people = await tx.query(
          `SELECT p.id, p.full_name, p.title, p.primary_email,
                  (SELECT max((e.props->>'strength')::float) FROM edges e WHERE e.dst_id = p.id AND e.type = 'knows' AND e.valid_to IS NULL) AS strength
             FROM people p JOIN entities e ON e.id = p.id WHERE p.company_id = $1 AND e.merged_into IS NULL ORDER BY strength DESC NULLS LAST`,
          [id],
        );
      const deals = await tx.query("SELECT id, name, stage, restricted, round_size_usd, updated_at FROM deals WHERE company_id = $1 ORDER BY updated_at DESC", [id]);
      const interactions = await tx.query(
          `SELECT DISTINCT i.id, i.kind, i.subject, i.occurred_at FROM interactions i
             JOIN interaction_participants ip ON ip.interaction_id = i.id JOIN people p ON p.id = ip.person_id
            WHERE p.company_id = $1 ORDER BY i.occurred_at DESC LIMIT 25`,
          [id],
        );
      return { ...company.rows[0], people: people.rows, deals: deals.rows, interactions: interactions.rows, warm_paths: await warmPaths(tx, id) };
    });
  });

  app.get("/warm-paths", async (req) => {
    const q = z.object({ target: uuid, limit: z.coerce.number().int().min(1).max(25).default(10) }).parse(req.query);
    return withTenant(scopeOf(req.principal), (tx) => warmPaths(tx, q.target, q.limit));
  });

  app.get("/search", async (req) => {
    const q = z.object({ q: z.string().min(1) }).parse(req.query);
    return withTenant(scopeOf(req.principal), async (tx) => {
      const { rows } = await tx.query(
        `SELECT e.id, e.type, e.canonical_name AS name, similarity(e.canonical_name, $1) AS score
           FROM entities e WHERE e.merged_into IS NULL AND e.type IN ('person', 'company', 'deal')
            AND (e.canonical_name ILIKE '%' || $1 || '%' OR similarity(e.canonical_name, $1) > 0.3)
          ORDER BY score DESC LIMIT 15`,
        [q.q],
      );
      return rows;
    });
  });
}
