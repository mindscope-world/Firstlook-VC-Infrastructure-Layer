import { afterAll, beforeAll, describe, expect, it } from "vitest";
import type { FastifyInstance } from "fastify";
import { buildApp } from "../src/app.js";
import { pool, systemPool } from "../src/lib/db.js";

const skip = process.env.FIRSTLOOK_DB_UNAVAILABLE === "1";

describe.skipIf(skip)("sourcing api", () => {
  let app: FastifyInstance;
  const cookies: Record<string, string> = {};
  const as = (email: string) => ({ cookie: cookies[email]! });

  beforeAll(async () => {
    app = buildApp();
    await app.ready();
    for (const email of ["paul@savanna.vc", "grace@savanna.vc", "lena@harbor.capital"]) {
      const res = await app.inject({ method: "POST", url: "/auth/dev-login", payload: { email } });
      cookies[email] = `fl_session=${res.cookies.find((c) => c.name === "fl_session")!.value}`;
    }
  });
  afterAll(async () => {
    await app.close();
    await pool.end();
    await systemPool.end();
  });

  it("lists the seeded thesis with its last run", async () => {
    const theses = (await app.inject({ method: "GET", url: "/theses", headers: as("paul@savanna.vc") })).json();
    expect(theses).toHaveLength(1);
    expect(theses[0].name).toBe("East Africa financial inclusion");
    expect(theses[0].last_run.status).toBe("done");
  });

  it("serves a ranked feed with features and cited rationale", async () => {
    const [thesis] = (await app.inject({ method: "GET", url: "/theses", headers: as("paul@savanna.vc") })).json();
    const feed = (await app.inject({ method: "GET", url: `/sourcing/feed?thesis=${thesis.id}`, headers: as("paul@savanna.vc") })).json();
    expect(feed.run.ranker).toBe("rules-v1");
    expect(feed.items.length).toBeGreaterThan(5);
    expect(feed.items.map((i: { rank: number }) => i.rank)).toEqual([...feed.items.map((i: { rank: number }) => i.rank)].sort((a, b) => a - b));
    const top = feed.items[0];
    expect(Object.keys(top.features).sort()).toEqual(["cheque", "geo", "momentum", "sector", "stage", "text", "warm"]);
    expect(top.rationale).toBeTruthy();
    expect(top.citations.length).toBeGreaterThan(0);
    const names = feed.items.map((i: { name: string }) => i.name);
    expect(names).not.toContain("NairaStack");
  });

  it("records feedback with features and hides downvoted companies", async () => {
    const [thesis] = (await app.inject({ method: "GET", url: "/theses", headers: as("grace@savanna.vc") })).json();
    const feed = (await app.inject({ method: "GET", url: `/sourcing/feed?thesis=${thesis.id}`, headers: as("grace@savanna.vc") })).json();
    const target = feed.items[1];
    const down = await app.inject({
      method: "POST", url: "/sourcing/feedback", headers: as("grace@savanna.vc"),
      payload: { thesis_id: thesis.id, company_id: target.company_id, vote: -1, reason: "Too early" },
    });
    expect(down.statusCode).toBe(200);
    const { rows } = await systemPool.query("SELECT vote, features FROM sourcing_feedback WHERE company_id = $1", [target.company_id]);
    expect(rows[0].vote).toBe(-1);
    expect(rows[0].features.sector).toBeDefined();
    const after = (await app.inject({ method: "GET", url: `/sourcing/feed?thesis=${thesis.id}`, headers: as("grace@savanna.vc") })).json();
    expect(after.items.map((i: { company_id: string }) => i.company_id)).not.toContain(target.company_id);
    const shown = (await app.inject({ method: "GET", url: `/sourcing/feed?thesis=${thesis.id}&hide_downvoted=false`, headers: as("grace@savanna.vc") })).json();
    expect(shown.items.find((i: { company_id: string }) => i.company_id === target.company_id).my_vote).toBe(-1);
    const events = await systemPool.query("SELECT count(*)::int AS n FROM outbox WHERE topic = 'sourcing.feedback'");
    expect(events.rows[0].n).toBeGreaterThan(0);
  });

  it("versions a thesis on edit and queues a re-score; only partners and admins can edit", async () => {
    const [thesis] = (await app.inject({ method: "GET", url: "/theses", headers: as("paul@savanna.vc") })).json();
    const body = { name: thesis.name, sectors: ["fintech"], stages: ["seed"], geographies: ["east-africa", "NG"], cheque_min_usd: 300000, cheque_max_usd: 1500000, founder_profile: "", description: thesis.description };
    const denied = await app.inject({ method: "PUT", url: `/theses/${thesis.id}`, headers: as("grace@savanna.vc"), payload: body });
    expect(denied.statusCode).toBe(403);
    const res = await app.inject({ method: "PUT", url: `/theses/${thesis.id}`, headers: as("paul@savanna.vc"), payload: body });
    expect(res.json().version).toBe(2);
    const versions = (await app.inject({ method: "GET", url: `/theses/${thesis.id}/versions`, headers: as("paul@savanna.vc") })).json();
    expect(versions.map((v: { version: number }) => v.version)).toEqual([2, 1]);
    const { rows } = await systemPool.query("SELECT payload FROM outbox WHERE topic = 'sourcing.requested' ORDER BY id DESC LIMIT 1");
    expect(rows[0].payload.thesis_version_id).toBe(res.json().version_id);
    const bad = await app.inject({ method: "POST", url: "/theses", headers: as("paul@savanna.vc"), payload: { ...body, sectors: ["crypto-casinos"] } });
    expect(bad.statusCode).toBe(400);
  });

  it("keeps theses and feeds per tenant", async () => {
    const [thesis] = (await app.inject({ method: "GET", url: "/theses", headers: as("paul@savanna.vc") })).json();
    expect((await app.inject({ method: "GET", url: "/theses", headers: as("lena@harbor.capital") })).json()).toEqual([]);
    const feed = (await app.inject({ method: "GET", url: `/sourcing/feed?thesis=${thesis.id}`, headers: as("lena@harbor.capital") })).json();
    expect(feed.items).toEqual([]);
  });
});
