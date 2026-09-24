import crypto from "node:crypto";
import { describe, expect, it } from "vitest";
import { can, issueSession, verifySession } from "../src/lib/auth.js";
import { verifySlackSignature } from "../src/routes/slack.js";

describe("sessions", () => {
  it("round-trips and rejects tampering", async () => {
    const p = { userId: crypto.randomUUID(), tenantId: crypto.randomUUID(), role: "partner" as const, email: "a@b.vc" };
    const token = await issueSession(p);
    expect(await verifySession(token)).toEqual(p);
    const [h, body, sig] = token.split(".");
    const forged = Buffer.from(JSON.stringify({ ...JSON.parse(Buffer.from(body!, "base64url").toString()), role: "admin" })).toString("base64url");
    await expect(verifySession(`${h}.${forged}.${sig}`)).rejects.toThrow();
  });

  it("maps roles to permissions", () => {
    const base = { userId: "u", tenantId: "t", email: "" };
    expect(can({ ...base, role: "viewer" }, "graph:read")).toBe(true);
    expect(can({ ...base, role: "viewer" }, "review:decide")).toBe(false);
    expect(can({ ...base, role: "associate" }, "deals:restrict")).toBe(false);
    expect(can({ ...base, role: "partner" }, "deals:restrict")).toBe(true);
    expect(can({ ...base, role: "partner" }, "nonexistent")).toBe(false);
  });
});

describe("slack signature", () => {
  const secret = "s3cret";
  const body = "team_id=T1&text=acme";
  const ts = "1790000000";
  const sig = "v0=" + crypto.createHmac("sha256", secret).update(`v0:${ts}:${body}`).digest("hex");

  it("accepts a valid signature", () => {
    expect(verifySlackSignature(secret, ts, body, sig, 1790000010)).toBe(true);
  });
  it("rejects wrong body, wrong secret and stale timestamps", () => {
    expect(verifySlackSignature(secret, ts, body + "x", sig, 1790000010)).toBe(false);
    expect(verifySlackSignature("other", ts, body, sig, 1790000010)).toBe(false);
    expect(verifySlackSignature(secret, ts, body, sig, 1790000000 + 3600)).toBe(false);
    expect(verifySlackSignature(secret, undefined, body, sig)).toBe(false);
  });
});
