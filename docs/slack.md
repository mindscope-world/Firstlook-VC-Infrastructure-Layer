# Slack app (dev workspace)

1. Create an app at api.slack.com from `docs/slack-manifest.yml`, replacing the URLs. For local testing, expose port 13000 with a tunnel such as `ngrok http 13000`.
2. Set `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET` and `SLACK_SIGNING_SECRET` in `.env`.
3. As an admin, go to Settings and choose **Add to Slack**. Then set the deal channel ID (the bot must be invited to that channel).

- `/firstlook <company or person>` answers ephemerally from the graph: deals, last contact and warm paths. It uses viewer-level visibility, so restricted deals and private interactions never appear.
- When a deal is created or changes stage, a message goes to the deal channel (`firstlook_ingest.slack`, consuming `deals.events`). Restricted deals are never posted.
