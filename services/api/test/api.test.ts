import crypto from "node:crypto";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import type { FastifyInstance } from "fastify";
import { buildApp } from "../src/app.js";
import { pool, systemPool } from "../src/lib/db.js";

const skip = process.env.FIRSTLOOK_DB_UNAVAILABLE === "1";

describe.skipIf(skip)("api against the seeded synthetic fund", () => {
  let app: FastifyInstance;
  const cookies: Record<string, string> = {};

  async function login(email: string) {
    const res = await app.inject({ method: "POST", url: "/auth/dev-login", payload: { email } });
    expect(res.statusCode).toBe(200);
    const c = res.cookies.find((x) => x.name === "fl_session");
    cookies[email] = `fl_session=${c!.value}`;
  }
  const get = (email: string, url: string) => app.inject({ method: "GET", url, headers: { cookie: cookies[email]! } });
  const post = (email: string, url: string, payload: unknown, method: "POST" | "PATCH" = "POST") =>
    app.inject({ method, url, payload: payload as object, headers: { cookie: cookies[email]! } });

  beforeAll(async () => {
    app = buildApp();
    await app.ready();
    for (const e of ["paul@savanna.vc", "grace@savanna.vc", "lena@harbor.capital", "amani@savanna.vc"]) await login(e);
    await systemPool.query(
      "INSERT INTO slack_installations (tenant_id, team_id, team_name, encrypted_bot_token, deal_channel_id) SELECT id, 'T_SAVANNA', 'Savanna', '\\x00', 'C123456' FROM tenants WHERE slug = 'savanna' ON CONFLICT DO NOTHING",
    );
  });
  afterAll(async () => {
    await app.close();
    await pool.end();
    await systemPool.end();
  });

  it("requires a session", async () => {
    expect((await app.inject({ method: "GET", url: "/dashboard" })).statusCode).toBe(401);
    expect((await app.inject({ method: "GET", url: "/dashboard", headers: { cookie: "fl_session=garbage" } })).statusCode).toBe(401);
  });

  it("serves the dashboard and me", async () => {
    const me = (await get("paul@savanna.vc", "/me")).json();
    expect(me.tenant_slug).toBe("savanna");
    const d = (await get("paul@savanna.vc", "/dashboard")).json();
    expect(d.counts.interactions_30d).toBeGreaterThan(5);
    expect(d.counts.review_pending).toBeGreaterThanOrEqual(1);
    expect(d.strongest.length).toBeGreaterThan(0);
  });

  it("lists interactions with participants and shows citations", async () => {
    const list = (await get("paul@savanna.vc", "/interactions?q=Kilimo")).json();
    expect(list.length).toBeGreaterThan(0);
    const intro = list.find((i: { subject: string }) => i.subject?.startsWith("Intro: Paul"));
    const detail = (await get("paul@savanna.vc", `/interactions/${intro.id}`)).json();
    expect(detail.participants.map((p: { email: string }) => p.email)).toContain("joseph@riftvalley.vc");
    const cited = detail.extractions[0];
    expect(detail.body_text.slice(cited.citations[0].start, cited.citations[0].end)).toBe(cited.citations[0].quote);
  });

  it("resolves a review item", async () => {
    const queue = (await get("grace@savanna.vc", "/review")).json();
    const item = queue.find((c: { mention: { email?: string } }) => c.mention.email === "wanjiru.kamau@gmail.com");
    expect(item.candidate.name).toBe("Wanjiru Kamau");
    const res = await post("grace@savanna.vc", `/review/${item.id}`, { decision: "merged" });
    expect(res.statusCode).toBe(200);
    const again = await post("grace@savanna.vc", `/review/${item.id}`, { decision: "merged" });
    expect(again.statusCode).toBe(409);
  });

  it("accepts a deal mention, moves the deal, and emits events", async () => {
    const proposed = (await get("grace@savanna.vc", "/extractions?status=proposed&kind=deal_mention")).json();
    const duka = proposed.find((x: { payload: { company_name: string } }) => x.payload.company_name === "Duka Direct");
    const accepted = (await post("grace@savanna.vc", `/extractions/${duka.id}`, { decision: "accepted" })).json();
    expect(accepted.deal_id).toBeTruthy();
    const moved = await post("grace@savanna.vc", `/deals/${accepted.deal_id}`, { stage: "screening" }, "PATCH");
    expect(moved.statusCode).toBe(200);
    const { rows } = await systemPool.query("SELECT payload FROM outbox WHERE topic = 'deals.events' AND key = $1 ORDER BY id", [
      accepted.deal_id,
    ]);
    expect(rows.map((r) => r.payload.type)).toEqual(["deal.created", "deal.stage_changed"]);
  });

  it("hides restricted deals from people outside the deal team", async () => {
    const created = await post("amani@savanna.vc", "/deals", { name: "Project Baobab", restricted: true });
    expect(created.statusCode).toBe(201);
    const byAmani = (await get("amani@savanna.vc", "/deals")).json().map((d: { name: string }) => d.name);
    const byGrace = (await get("grace@savanna.vc", "/deals")).json().map((d: { name: string }) => d.name);
    expect(byAmani).toContain("Project Baobab");
    expect(byGrace).not.toContain("Project Baobab");
    const denied = await post("grace@savanna.vc", "/deals", { name: "Secret", restricted: true });
    expect(denied.statusCode).toBe(403);
  });

  it("finds warm paths to a company", async () => {
    const companies = (await get("paul@savanna.vc", "/companies?q=Kilimo")).json();
    const detail = (await get("paul@savanna.vc", `/companies/${companies[0].id}`)).json();
    expect(detail.warm_paths.length).toBeGreaterThan(0);
    const first = detail.warm_paths[0];
    expect(first.people[0].internal).toBe(true);
  });

  it("keeps tenants apart", async () => {
    const savannaCompanies = (await get("paul@savanna.vc", "/companies")).json();
    const pesaflow = savannaCompanies.find((c: { name: string; domain: string | null }) => c.name === "PesaFlow" || c.domain === "pesaflow.africa");
    expect((await get("lena@harbor.capital", `/companies/${pesaflow.id}`)).statusCode).toBe(404);
    const harborPeople = (await get("lena@harbor.capital", "/people")).json();
    expect(harborPeople.map((p: { primary_email: string }) => p.primary_email)).not.toContain("jane@pesaflow.africa");
  });

  it("answers the Slack command with signed requests only", async () => {
    const body = "team_id=T_SAVANNA&text=Kilimo";
    const ts = String(Math.floor(Date.now() / 1000));
    const sig = "v0=" + crypto.createHmac("sha256", "test-signing-secret").update(`v0:${ts}:${body}`).digest("hex");
    const headers = { "content-type": "application/x-www-form-urlencoded", "x-slack-request-timestamp": ts };
    const bad = await app.inject({ method: "POST", url: "/slack/commands", payload: body, headers: { ...headers, "x-slack-signature": "v0=bad" } });
    expect(bad.statusCode).toBe(401);
    const ok = await app.inject({ method: "POST", url: "/slack/commands", payload: body, headers: { ...headers, "x-slack-signature": sig } });
    expect(ok.statusCode).toBe(200);
    const json = ok.json();
    expect(json.response_type).toBe("ephemeral");
    expect(json.text).toContain("Kilimo Data");
    expect(json.text).toContain("Warm paths");
  });
});
