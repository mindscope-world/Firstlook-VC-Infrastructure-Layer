import type { FastifyInstance, FastifyReply } from "fastify";
import { WorkOS } from "@workos-inc/node";
import { z } from "zod";
import { config } from "../config.js";
import { COOKIE, issueSession, requireAuth, type Principal, type Role } from "../lib/auth.js";
import { systemPool } from "../lib/db.js";

async function startSession(reply: FastifyReply, p: Principal) {
  const token = await issueSession(p);
  reply.setCookie(COOKIE, token, {
    path: "/",
    httpOnly: true,
    sameSite: "lax",
    secure: !["local", "test", "ci"].includes(config.env),
    maxAge: config.sessionTtlSeconds,
  });
  return token;
}

async function audit(tenantId: string, userId: string, action: string, details: Record<string, unknown>) {
  await systemPool.query(
    "INSERT INTO audit_events (tenant_id, actor_type, actor_id, action, resource_type, resource_id, details) VALUES ($1, 'user', $2::uuid, $3, 'session', $2::text, $4)",
    [tenantId, userId, action, details],
  );
}

export async function authRoutes(app: FastifyInstance) {
  // Development only: sign in as any seeded user by email.
  app.post("/auth/dev-login", async (req, reply) => {
    if (!config.devLogin) return reply.code(404).send({ error: "not found" });
    const body = z.object({ email: z.string().email(), tenant: z.string().optional() }).parse(req.body);
    const { rows } = await systemPool.query(
      `SELECT u.id, u.tenant_id, u.role::text AS role, u.email::text AS email, t.slug
         FROM users u JOIN tenants t ON t.id = u.tenant_id
        WHERE u.email = $1 AND ($2::text IS NULL OR t.slug = $2)`,
      [body.email, body.tenant ?? null],
    );
    if (rows.length === 0) return reply.code(404).send({ error: "no such user" });
    if (rows.length > 1) return reply.code(409).send({ error: "user exists in several tenants; pass tenant" });
    const u = rows[0];
    const p: Principal = { userId: u.id, tenantId: u.tenant_id, role: u.role as Role, email: u.email };
    await startSession(reply, p);
    await audit(p.tenantId, p.userId, "session.dev_login", {});
    return { user: p };
  });

  app.get("/auth/workos/start", async (_req, reply) => {
    if (!config.workos.apiKey || !config.workos.clientId) {
      return reply.code(503).send({ error: "WorkOS is not configured" });
    }
    const workos = new WorkOS(config.workos.apiKey);
    const url = workos.userManagement.getAuthorizationUrl({
      provider: "authkit",
      clientId: config.workos.clientId,
      redirectUri: config.workos.redirectUri,
    });
    return reply.redirect(url);
  });

  app.get("/auth/workos/callback", async (req, reply) => {
    const { code } = z.object({ code: z.string() }).parse(req.query);
    if (!config.workos.apiKey || !config.workos.clientId) {
      return reply.code(503).send({ error: "WorkOS is not configured" });
    }
    const workos = new WorkOS(config.workos.apiKey);
    const auth = await workos.userManagement.authenticateWithCode({ clientId: config.workos.clientId, code });
    // Tenants are matched by WorkOS organization; users must already be invited.
    const { rows } = await systemPool.query(
      `SELECT u.id, u.tenant_id, u.role::text AS role, u.email::text AS email
         FROM users u JOIN tenants t ON t.id = u.tenant_id
        WHERE t.workos_org_id = $1 AND u.email = $2`,
      [auth.organizationId ?? "", auth.user.email],
    );
    if (rows.length !== 1) return reply.redirect(`${config.webUrl}/login?error=not_invited`);
    const u = rows[0];
    await systemPool.query("UPDATE users SET workos_user_id = $1 WHERE id = $2", [auth.user.id, u.id]);
    const p: Principal = { userId: u.id, tenantId: u.tenant_id, role: u.role as Role, email: u.email };
    await startSession(reply, p);
    await audit(p.tenantId, p.userId, "session.sso_login", { provider: "workos" });
    return reply.redirect(`${config.webUrl}/`);
  });

  app.post("/auth/logout", async (_req, reply) => {
    reply.clearCookie(COOKIE, { path: "/" });
    return { ok: true };
  });

  app.get("/me", { preHandler: requireAuth }, async (req) => {
    const p = req.principal;
    const { rows } = await systemPool.query(
      `SELECT u.name, u.person_id, t.name AS tenant_name, t.slug AS tenant_slug
         FROM users u JOIN tenants t ON t.id = u.tenant_id WHERE u.id = $1 AND u.tenant_id = $2`,
      [p.userId, p.tenantId],
    );
    return { ...p, ...(rows[0] ?? {}) };
  });

  app.get("/auth/config", async () => ({ devLogin: config.devLogin, sso: Boolean(config.workos.apiKey) }));
}
