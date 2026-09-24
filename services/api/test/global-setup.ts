// Seeds firstlook_test with the synthetic funds using the Python seed script,
// so API tests run against exactly the data the pipeline produces.
import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import pg from "pg";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../../..");

export default async function setup() {
  const host = process.env.TEST_PG_HOSTPORT ?? "localhost:15432";
  const owner = `postgresql://firstlook:firstlook@${host}/firstlook_test`;
  const client = new pg.Client({ connectionString: owner, connectionTimeoutMillis: 2000 });
  try {
    await client.connect();
    await client.end();
  } catch {
    process.env.FIRSTLOOK_DB_UNAVAILABLE = "1";
    console.warn("local Postgres not running: DB tests will be skipped (make up)");
    return;
  }
  const python = path.join(root, ".venv", "bin", "python");
  execFileSync(python, ["-m", "firstlook_fixtures.seed", "--reset"], {
    cwd: root,
    stdio: "inherit",
    env: {
      ...process.env,
      ENV: "test",
      DATABASE_URL: `postgresql://firstlook_app:firstlook_app@${host}/firstlook_test`,
      DATABASE_OWNER_URL: owner,
      DATABASE_SYSTEM_URL: `postgresql://firstlook_system:firstlook_system@${host}/firstlook_test`,
      STORAGE_BACKEND: "local",
      STORAGE_LOCAL_ROOT: path.join(root, ".data", "test-objects"),
      BUS_BACKEND: "memory",
    },
  });
}
