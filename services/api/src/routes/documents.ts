// Diligence documents and their fact sheets. Uploads and file downloads go
// through the ingest service (/api/ingest/documents); this serves the parsed
// pages and the human decision on proposed fact sheets.

import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { requireAuth, requirePermission } from "../lib/auth.js";
import { scopeOf, withTenant } from "../lib/db.js";

const uuid = z.string().uuid();

export async function documentRoutes(app: FastifyInstance) {
  app.addHook("preHandler", requireAuth);

  app.get("/documents", async (req) => {
    const q = z
      .object({
        company_id: uuid.optional(),
        deal_id: uuid.optional(),
        limit: z.coerce.number().int().min(1).max(200).default(100),
      })
      .parse(req.query);
    return withTenant(scopeOf(req.principal), async (tx) => {
      const { rows } = await tx.query(
        `SELECT d.id, d.filename, d.format, d.origin, d.status, d.error, d.page_count, d.ocr_pages, d.warnings,
                d.size_bytes, d.created_at, d.interaction_id,
                CASE WHEN c.id IS NULL THEN NULL ELSE json_build_object('id', c.id, 'name', c.name) END AS company,
                u.name AS uploaded_by,
                (SELECT json_build_object('id', f.id, 'status', f.status, 'coverage', f.coverage,
                                          'company_name', f.company_name)
                   FROM fact_sheets f WHERE f.document_id = d.id ORDER BY f.created_at DESC LIMIT 1) AS fact_sheet
           FROM documents d
           LEFT JOIN companies c ON c.id = d.company_id
           LEFT JOIN users u ON u.id = d.uploaded_by
          WHERE ($1::uuid IS NULL OR d.company_id = $1) AND ($2::uuid IS NULL OR d.deal_id = $2)
          ORDER BY d.created_at DESC LIMIT $3`,
        [q.company_id ?? null, q.deal_id ?? null, q.limit],
      );
      return rows;
    });
  });

  app.get("/documents/:id", async (req, reply) => {
    const { id } = z.object({ id: uuid }).parse(req.params);
    const doc = await withTenant(scopeOf(req.principal), async (tx) => {
      const { rows } = await tx.query(
        `SELECT d.id, d.filename, d.format, d.content_type, d.origin, d.status, d.error, d.page_count, d.ocr_pages,
                d.warnings, d.size_bytes, d.created_at, d.parsed_at, d.interaction_id, d.deal_id,
                CASE WHEN c.id IS NULL THEN NULL ELSE json_build_object('id', c.id, 'name', c.name) END AS company,
                u.name AS uploaded_by,
                coalesce((SELECT json_agg(json_build_object('page_no', p.page_no, 'kind', p.kind, 'title', p.title,
                                                            'text', p.text, 'ocr', p.ocr) ORDER BY p.page_no)
                            FROM document_pages p WHERE p.document_id = d.id), '[]') AS pages,
                coalesce((SELECT json_agg(json_build_object('id', f.id, 'status', f.status, 'coverage', f.coverage,
                                                            'dropped_uncited', f.dropped_uncited, 'fields', f.fields,
                                                            'company_name', f.company_name, 'model', f.model,
                                                            'created_at', f.created_at, 'decided_at', f.decided_at)
                                          ORDER BY f.created_at DESC)
                            FROM fact_sheets f WHERE f.document_id = d.id), '[]') AS fact_sheets
           FROM documents d
           LEFT JOIN companies c ON c.id = d.company_id
           LEFT JOIN users u ON u.id = d.uploaded_by
          WHERE d.id = $1`,
        [id],
      );
      return rows[0];
    });
    if (!doc) return reply.code(404).send({ error: "document not found" });
    return doc;
  });

  app.get("/fact-sheets", async (req) => {
    const q = z
      .object({ status: z.enum(["proposed", "accepted", "rejected", "superseded"]).optional() })
      .parse(req.query);
    return withTenant(scopeOf(req.principal), async (tx) => {
      const { rows } = await tx.query(
        `SELECT f.id, f.status, f.coverage, f.company_name, f.created_at, f.document_id, d.filename,
                CASE WHEN c.id IS NULL THEN NULL ELSE json_build_object('id', c.id, 'name', c.name) END AS company
           FROM fact_sheets f JOIN documents d ON d.id = f.document_id
           LEFT JOIN companies c ON c.id = coalesce(f.company_id, d.company_id)
          WHERE ($1::text IS NULL OR f.status = $1)
          ORDER BY f.created_at DESC LIMIT 200`,
        [q.status ?? null],
      );
      return rows;
    });
  });

  app.post("/fact-sheets/:id", { preHandler: requirePermission("fact_sheets:decide") }, async (req, reply) => {
    const { id } = z.object({ id: uuid }).parse(req.params);
    const { decision } = z.object({ decision: z.enum(["accepted", "rejected"]) }).parse(req.body);
    try {
      await withTenant(scopeOf(req.principal), (tx) =>
        tx.query("SELECT decide_fact_sheet($1, $2, $3)", [id, decision, req.principal.userId]),
      );
    } catch (err) {
      const e = err as { code?: string; message?: string };
      if (e.code === "P0001") {
        const notFound = e.message?.includes("not found");
        return reply.code(notFound ? 404 : 409).send({ error: e.message });
      }
      throw err;
    }
    return { id, decision };
  });
}
