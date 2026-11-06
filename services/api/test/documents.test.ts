import { afterAll, beforeAll, describe, expect, it } from "vitest";
import type { FastifyInstance } from "fastify";
import { buildApp } from "../src/app.js";
import { pool, systemPool } from "../src/lib/db.js";

const skip = process.env.FIRSTLOOK_DB_UNAVAILABLE === "1";

describe.skipIf(skip)("documents api", () => {
  let app: FastifyInstance;
  const cookies: Record<string, string> = {};
  const as = (email: string) => ({ cookie: cookies[email]! });

  beforeAll(async () => {
    app = buildApp();
    await app.ready();
    for (const email of ["paul@savanna.vc", "grace@savanna.vc", "tom@savanna.vc", "lena@harbor.capital"]) {
      const res = await app.inject({ method: "POST", url: "/auth/dev-login", payload: { email } });
      cookies[email] = `fl_session=${res.cookies.find((c) => c.name === "fl_session")!.value}`;
    }
  });
  afterAll(async () => {
    await app.close();
    await pool.end();
    await systemPool.end();
  });

  it("lists the seeded documents with their fact sheets", async () => {
    const docs = (await app.inject({ method: "GET", url: "/documents", headers: as("paul@savanna.vc") })).json();
    const byName = Object.fromEntries(docs.map((d: { filename: string }) => [d.filename, d]));
    expect(Object.keys(byName).sort()).toEqual([
      "Chama Pay - Pre-seed.pptx",
      "Kilimo Data - Model.xlsx",
      "Kilimo Data - Seed Deck.pdf",
    ]);
    const deck = byName["Kilimo Data - Seed Deck.pdf"];
    expect(deck.origin).toBe("email_attachment");
    expect(deck.status).toBe("parsed");
    expect(deck.company.name).toBe("Kilimo Data");
    expect(deck.fact_sheet.status).toBe("proposed");
    // Another tenant sees none of them.
    const harbor = (await app.inject({ method: "GET", url: "/documents", headers: as("lena@harbor.capital") })).json();
    expect(harbor).toEqual([]);
  });

  it("filters by company and serves pages with cited fact sheet fields", async () => {
    const all = (await app.inject({ method: "GET", url: "/documents", headers: as("paul@savanna.vc") })).json();
    const deck = all.find((d: { filename: string }) => d.filename.endsWith(".pdf"));
    const forCompany = (
      await app.inject({ method: "GET", url: `/documents?company_id=${deck.company.id}`, headers: as("paul@savanna.vc") })
    ).json();
    expect(forCompany.map((d: { filename: string }) => d.filename).sort()).toEqual([
      "Kilimo Data - Model.xlsx",
      "Kilimo Data - Seed Deck.pdf",
    ]);

    const detail = (await app.inject({ method: "GET", url: `/documents/${deck.id}`, headers: as("paul@savanna.vc") })).json();
    expect(detail.pages).toHaveLength(6);
    const sheet = detail.fact_sheets[0];
    const raise = sheet.fields.round.raise_usd;
    expect(raise.value).toBe(1500000);
    const page = detail.pages.find((p: { page_no: number }) => p.page_no === raise.citation.page);
    expect(page.text.slice(raise.citation.start, raise.citation.end)).toBe(raise.citation.quote);

    const missing = await app.inject({ method: "GET", url: `/documents/${deck.id}`, headers: as("lena@harbor.capital") });
    expect(missing.statusCode).toBe(404);
  });

  it("accepts a fact sheet once, by an allowed role, and fills the company profile", async () => {
    const proposed = (await app.inject({ method: "GET", url: "/fact-sheets?status=proposed", headers: as("grace@savanna.vc") })).json();
    const sheet = proposed.find((s: { filename: string }) => s.filename === "Kilimo Data - Seed Deck.pdf");

    const denied = await app.inject({
      method: "POST", url: `/fact-sheets/${sheet.id}`, headers: as("tom@savanna.vc"), payload: { decision: "accepted" },
    });
    expect(denied.statusCode).toBe(403); // platform role can't decide fact sheets

    const before = await systemPool.query(
      "SELECT c.id, c.founded_year, c.description FROM fact_sheets f JOIN documents d ON d.id = f.document_id JOIN companies c ON c.id = d.company_id WHERE f.id = $1",
      [sheet.id],
    );
    const ok = await app.inject({
      method: "POST", url: `/fact-sheets/${sheet.id}`, headers: as("grace@savanna.vc"), payload: { decision: "accepted" },
    });
    expect(ok.statusCode).toBe(200);
    const again = await app.inject({
      method: "POST", url: `/fact-sheets/${sheet.id}`, headers: as("grace@savanna.vc"), payload: { decision: "rejected" },
    });
    expect(again.statusCode).toBe(409);

    // The sheet is linked to the company; profile values other sources already set are kept.
    const { rows } = await systemPool.query(
      "SELECT c.id, c.founded_year, c.description FROM fact_sheets f JOIN companies c ON c.id = f.company_id WHERE f.id = $1",
      [sheet.id],
    );
    expect(rows[0]).toEqual(before.rows[0]);
    const audit = await systemPool.query("SELECT 1 FROM audit_events WHERE action = 'fact_sheet.accepted' AND resource_id = $1", [sheet.id]);
    expect(audit.rowCount).toBe(1);

    const foreign = await app.inject({
      method: "POST", url: `/fact-sheets/${sheet.id}`, headers: as("lena@harbor.capital"), payload: { decision: "rejected" },
    });
    expect(foreign.statusCode).toBe(404);
  });
});
