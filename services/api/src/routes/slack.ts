// Slack slash command: /firstlook <company or person>
//
// Slack signs each request; we verify the signature, map the Slack workspace
// to a tenant, and answer from the graph with viewer-level visibility (no
// restricted deals, no private interactions), as an ephemeral message.

import crypto from "node:crypto";
import type { FastifyInstance } from "fastify";
import { config } from "../config.js";
import { systemPool, withTenant, type Tx } from "../lib/db.js";
import { warmPaths } from "./graph.js";

export function verifySlackSignature(
  secret: string,
  timestamp: string | undefined,
  body: string,
  signature: string | undefined,
  nowSeconds = Math.floor(Date.now() / 1000),
): boolean {
  if (!timestamp || !signature) return false;
  if (Math.abs(nowSeconds - Number(timestamp)) > 60 * 5) return false; // replay window
  const expected = "v0=" + crypto.createHmac("sha256", secret).update(`v0:${timestamp}:${body}`).digest("hex");
  const a = Buffer.from(expected);
  const b = Buffer.from(signature);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

type Block = Record<string, unknown>;

export async function lookup(tx: Tx, query: string, webUrl: string): Promise<{ text: string; blocks: Block[] }> {
  const { rows } = await tx.query(
    `SELECT e.id, e.type::text AS type, e.canonical_name AS name
       FROM entities e WHERE e.merged_into IS NULL AND e.type IN ('company', 'person')
        AND (e.canonical_name ILIKE '%' || $1 || '%' OR similarity(e.canonical_name, $1) > 0.35
             OR EXISTS (SELECT 1 FROM identifiers i WHERE i.entity_id = e.id AND i.kind IN ('domain', 'email') AND i.value = lower($1)))
      ORDER BY (e.type = 'company') DESC, similarity(e.canonical_name, $1) DESC LIMIT 1`,
    [query],
  );
  const hit = rows[0];
  if (!hit) {
    return { text: `No company or person matching "${query}".`, blocks: [] };
  }

  const lines: string[] = [];
  let header: string;
  if (hit.type === "company") {
    const c = await tx.query(
      `SELECT c.name, c.domain, c.description,
              (SELECT json_agg(json_build_object('name', d.name, 'stage', d.stage)) FROM deals d WHERE d.company_id = c.id) AS deals,
              (SELECT max(i.occurred_at) FROM interactions i JOIN interaction_participants ip ON ip.interaction_id = i.id
                 JOIN people p ON p.id = ip.person_id WHERE p.company_id = c.id) AS last_contact
         FROM companies c WHERE c.id = $1`,
      [hit.id],
    );
    const co = c.rows[0];
    header = `*${co.name}*${co.domain ? ` · ${co.domain}` : ""}`;
    if (co.description) lines.push(co.description);
    for (const d of co.deals ?? []) lines.push(`Deal: ${d.name} (${d.stage})`);
    lines.push(co.last_contact ? `Last contact: ${new Date(co.last_contact).toISOString().slice(0, 10)}` : "No interactions yet");
  } else {
    const p = await tx.query(
      `SELECT p.full_name, p.title, c.name AS company,
              (SELECT json_agg(json_build_object('name', pi.full_name, 'strength', (e.props->>'strength')::float) ORDER BY (e.props->>'strength')::float DESC)
                 FROM edges e JOIN people pi ON pi.id = e.src_id WHERE e.dst_id = p.id AND e.type = 'knows' AND e.valid_to IS NULL) AS knows
         FROM people p LEFT JOIN companies c ON c.id = p.company_id WHERE p.id = $1`,
      [hit.id],
    );
    const pr = p.rows[0];
    header = `*${pr.full_name}*${pr.title ? ` · ${pr.title}` : ""}${pr.company ? `, ${pr.company}` : ""}`;
    for (const k of (pr.knows ?? []).slice(0, 3)) lines.push(`Knows ${k.name} (strength ${Number(k.strength).toFixed(2)})`);
  }

  const paths = await warmPaths(tx, hit.id, 3);
  if (paths.length > 0) {
    lines.push("*Warm paths*");
    for (const path of paths) {
      const names = (path.people as { name: string }[]).map((x) => x.name).join(" → ");
      lines.push(`• ${names} (${Number(path.score).toFixed(2)})`);
    }
  }
  const link = `${webUrl}/${hit.type === "company" ? "companies" : "people"}/${hit.id}`;
  const text = `${header}\n${lines.join("\n")}`;
  return {
    text,
    blocks: [
      { type: "section", text: { type: "mrkdwn", text } },
      { type: "context", elements: [{ type: "mrkdwn", text: `<${link}|Open in Firstlook>` }] },
    ],
  };
}

export async function slackRoutes(app: FastifyInstance) {
  // Keep the raw body: the signature covers the exact bytes Slack sent.
  app.addContentTypeParser("application/x-www-form-urlencoded", { parseAs: "string" }, (_req, body, done) => {
    done(null, body);
  });

  app.post("/slack/commands", async (req, reply) => {
    const raw = req.body as string;
    if (!config.slackSigningSecret) return reply.code(503).send({ error: "Slack is not configured" });
    const ok = verifySlackSignature(
      config.slackSigningSecret,
      req.headers["x-slack-request-timestamp"] as string | undefined,
      raw,
      req.headers["x-slack-signature"] as string | undefined,
    );
    if (!ok) return reply.code(401).send({ error: "bad signature" });

    const form = new URLSearchParams(raw);
    const teamId = form.get("team_id");
    const text = (form.get("text") ?? "").trim();
    const install = await systemPool.query("SELECT tenant_id FROM slack_installations WHERE team_id = $1", [teamId]);
    if (install.rows.length === 0) {
      return { response_type: "ephemeral", text: "This Slack workspace isn't connected to Firstlook yet." };
    }
    if (!text) return { response_type: "ephemeral", text: "Usage: `/firstlook <company or person>`" };

    const answer = await withTenant({ tenantId: install.rows[0].tenant_id, userId: null, role: "viewer" }, (tx) =>
      lookup(tx, text, config.webUrl),
    );
    return { response_type: "ephemeral", ...answer };
  });
}
