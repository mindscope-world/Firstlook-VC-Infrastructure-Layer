// Configuration from the environment, with defaults matching compose/.

const env = process.env;

export const config = {
  env: env.ENV ?? "local",
  port: Number(env.API_PORT ?? 14100),
  // RLS-bound role for all tenant data; the system role is used only to map a
  // login (email, WorkOS org, Slack team) to a tenant before any context exists.
  databaseUrl: env.DATABASE_URL ?? "postgresql://firstlook_app:firstlook_app@localhost:15432/firstlook",
  databaseSystemUrl:
    env.DATABASE_SYSTEM_URL ?? "postgresql://firstlook_system:firstlook_system@localhost:15432/firstlook",
  sessionSecret: env.SESSION_SECRET ?? "local-dev-session-secret-change-me",
  sessionTtlSeconds: 12 * 3600,
  webUrl: env.WEB_URL ?? "http://localhost:13000",
  devLogin: (env.DEV_LOGIN ?? (["local", "test", "ci"].includes(env.ENV ?? "local") ? "true" : "false")) === "true",
  workos: {
    apiKey: env.WORKOS_API_KEY,
    clientId: env.WORKOS_CLIENT_ID,
    redirectUri: env.WORKOS_REDIRECT_URI ?? "http://localhost:13000/api/auth/workos/callback",
  },
  slackSigningSecret: env.SLACK_SIGNING_SECRET,
};

if (config.env !== "local" && config.env !== "test" && config.env !== "ci") {
  if (config.sessionSecret.startsWith("local-dev")) {
    throw new Error("SESSION_SECRET must be set outside local development");
  }
}
