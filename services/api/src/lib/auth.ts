import { SignJWT, jwtVerify } from "jose";
import type { FastifyReply, FastifyRequest } from "fastify";
import { config } from "../config.js";

// Session tokens are shared with the Python services (firstlook_core.auth):
// HS256, issuer "firstlook", claims sub (user), tid (tenant), role, email.

export interface Principal {
  userId: string;
  tenantId: string;
  role: Role;
  email: string;
}

export const ROLES = ["admin", "partner", "associate", "platform", "finance", "viewer"] as const;
export type Role = (typeof ROLES)[number];

const key = () => new TextEncoder().encode(config.sessionSecret);
export const COOKIE = "fl_session";

export async function issueSession(p: Principal): Promise<string> {
  return new SignJWT({ tid: p.tenantId, role: p.role, email: p.email })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuer("firstlook")
    .setSubject(p.userId)
    .setIssuedAt()
    .setExpirationTime(`${config.sessionTtlSeconds}s`)
    .sign(key());
}

export async function verifySession(token: string): Promise<Principal> {
  const { payload } = await jwtVerify(token, key(), { issuer: "firstlook", algorithms: ["HS256"] });
  if (!payload.sub || typeof payload.tid !== "string" || !ROLES.includes(payload.role as Role)) {
    throw new Error("malformed session");
  }
  return { userId: payload.sub, tenantId: payload.tid, role: payload.role as Role, email: String(payload.email ?? "") };
}

// What each role may do. Row-level security still decides which rows are visible.
const PERMISSIONS: Record<string, Role[]> = {
  "graph:read": ["admin", "partner", "associate", "platform", "finance", "viewer"],
  "review:decide": ["admin", "partner", "associate", "platform"],
  "extractions:decide": ["admin", "partner", "associate", "platform"],
  "deals:write": ["admin", "partner", "associate"],
  "deals:restrict": ["admin", "partner"],
  "audit:read": ["admin"],
  "theses:write": ["admin", "partner"],
  "sourcing:feedback": ["admin", "partner", "associate", "platform"],
};

export function can(p: Principal, permission: keyof typeof PERMISSIONS | string): boolean {
  return PERMISSIONS[permission]?.includes(p.role) ?? false;
}

declare module "fastify" {
  interface FastifyRequest {
    principal: Principal;
  }
}

export async function requireAuth(req: FastifyRequest, reply: FastifyReply): Promise<void> {
  const header = req.headers.authorization;
  const token = req.cookies[COOKIE] ?? (header?.startsWith("Bearer ") ? header.slice(7) : undefined);
  if (!token) {
    return reply.code(401).send({ error: "not signed in" });
  }
  try {
    req.principal = await verifySession(token);
  } catch {
    return reply.code(401).send({ error: "invalid session" });
  }
}

export function requirePermission(permission: string) {
  return async (req: FastifyRequest, reply: FastifyReply) => {
    if (!can(req.principal, permission)) {
      return reply.code(403).send({ error: `requires ${permission}` });
    }
  };
}
