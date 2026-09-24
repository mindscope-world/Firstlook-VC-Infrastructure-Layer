import { defineConfig } from "vitest/config";

const pg = process.env.TEST_PG_HOSTPORT ?? "localhost:15432";

export default defineConfig({
  test: {
    globalSetup: ["./test/global-setup.ts"],
    env: {
      ENV: "test",
      DATABASE_URL: `postgresql://firstlook_app:firstlook_app@${pg}/firstlook_test`,
      DATABASE_SYSTEM_URL: `postgresql://firstlook_system:firstlook_system@${pg}/firstlook_test`,
      SLACK_SIGNING_SECRET: "test-signing-secret",
      LOG_LEVEL: "silent",
    },
    fileParallelism: false,
  },
});
