import pg from "pg";
import { config } from "../config.js";
import type { Principal } from "./auth.js";

// Return numerics and bigints as numbers for JSON (counts, amounts, scores).
pg.types.setTypeParser(pg.types.builtins.INT8, (v) => Number(v));
pg.types.setTypeParser(pg.types.builtins.NUMERIC, (v) => Number(v));

export const pool = new pg.Pool({ connectionString: config.databaseUrl, max: 20 });
export const systemPool = new pg.Pool({ connectionString: config.databaseSystemUrl, max: 4 });

export type Tx = pg.PoolClient;

export interface Scope {
  tenantId: string;
  userId: string | null;
  role: string;
}

export function scopeOf(p: Principal): Scope {
  return { tenantId: p.tenantId, userId: p.userId, role: p.role };
}

/**
 * Run fn in a transaction confined by row-level security to one tenant.
 * The context is SET LOCAL, so it ends with the transaction and never leaks
 * to the next request that reuses this pooled connection.
 */
export async function withTenant<T>(scope: Scope, fn: (tx: Tx) => Promise<T>): Promise<T> {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    await client.query(
      "SELECT set_config('app.tenant_id', $1, true), set_config('app.user_id', $2, true), set_config('app.user_role', $3, true)",
      [scope.tenantId, scope.userId ?? "", scope.role],
    );
    const result = await fn(client);
    await client.query("COMMIT");
    return result;
  } catch (err) {
    await client.query("ROLLBACK").catch(() => undefined);
    throw err;
  } finally {
    client.release();
  }
}

export async function audit(
  tx: Tx,
  scope: Scope,
  action: string,
  resourceType: string,
  resourceId: string | null,
  details: Record<string, unknown> = {},
): Promise<void> {
  await tx.query(
    "INSERT INTO audit_events (tenant_id, actor_type, actor_id, action, resource_type, resource_id, details) VALUES ($1, $2, $3, $4, $5, $6, $7)",
    [scope.tenantId, scope.userId ? "user" : "service", scope.userId, action, resourceType, resourceId, details],
  );
}

export async function enqueue(
  tx: Tx,
  tenantId: string,
  topic: string,
  payload: Record<string, unknown>,
  key?: string,
): Promise<void> {
  await tx.query("INSERT INTO outbox (tenant_id, topic, key, payload) VALUES ($1, $2, $3, $4)", [
    tenantId,
    topic,
    key ?? null,
    { ...payload, tenant_id: tenantId },
  ]);
}
