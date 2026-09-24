import Fastify from "fastify";
import cookie from "@fastify/cookie";
import { ZodError } from "zod";
import { authRoutes } from "./routes/auth.js";
import { graphRoutes } from "./routes/graph.js";
import { slackRoutes } from "./routes/slack.js";
import { workflowRoutes } from "./routes/workflow.js";

export function buildApp() {
  const app = Fastify({ logger: { level: process.env.LOG_LEVEL ?? "info" }, trustProxy: true });
  app.register(cookie);

  app.setErrorHandler((err, req, reply) => {
    if (err instanceof ZodError) {
      return reply.code(400).send({ error: "invalid request", issues: err.issues });
    }
    req.log.error(err);
    const status = (err as { statusCode?: number }).statusCode ?? 500;
    const message = err instanceof Error ? err.message : "error";
    return reply.code(status).send({ error: status >= 500 ? "internal error" : message });
  });

  app.get("/healthz", async () => ({ status: "ok" }));
  app.register(authRoutes);
  app.register(slackRoutes);
  app.register(graphRoutes);
  app.register(workflowRoutes);
  return app;
}
