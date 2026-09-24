import type { NextConfig } from "next";

const apiUrl = process.env.API_URL ?? "http://localhost:14100";
const ingestUrl = process.env.INGEST_URL ?? "http://localhost:14200";

// The browser only ever talks to this origin. /api/ingest/* goes to the
// Python ingest service, everything else under /api/* to the TypeScript API,
// so the session cookie is first-party for both.
const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      { source: "/api/ingest/:path*", destination: `${ingestUrl}/:path*` },
      { source: "/api/:path*", destination: `${apiUrl}/:path*` },
    ];
  },
};

export default nextConfig;
