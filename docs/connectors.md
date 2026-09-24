# Connecting real accounts in development

The OAuth apps run in each provider's **testing** mode, which allows the team's own accounts on `localhost`. Production verification (Google CASA, Microsoft publisher verification, Meta business verification) is Phase 4 (plan §8).

Every redirect URI goes through the web app's proxy: `http://localhost:13000/api/ingest/connectors/<provider>/callback`.

## Google (Gmail + Calendar, Meet transcripts)
1. In Google Cloud Console, create a project and enable the Gmail API, Google Calendar API and Google Meet REST API.
2. OAuth consent screen: External, Testing. Add yourself as a test user. Scopes: `gmail.readonly`, `calendar.readonly`, `meetings.space.readonly`, `openid`, `email`.
3. Create a Web OAuth client with the redirect URIs `.../connectors/google/callback` and `.../connectors/google_meet/callback`.
4. Put `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`.

## Microsoft 365 (Outlook + Calendar)
1. In the Entra admin center, register an app (multitenant plus personal accounts). Add the redirect URI `.../connectors/microsoft/callback` (Web).
2. Add delegated Graph permissions: `Mail.Read`, `Calendars.Read`, `User.Read`, `offline_access`.
3. Create a client secret. Set `MICROSOFT_CLIENT_ID` and `MICROSOFT_CLIENT_SECRET`.

## Zoom (cloud recording transcripts)
Create a General (user-managed) OAuth app with the redirect `.../connectors/zoom/callback` and the scopes `cloud_recording:read:list_user_recordings`, `cloud_recording:read:list_recording_files`, `meeting:read:list_past_participants` and `user:read:email`.

## What gets synced
- **Gmail:** the last 365 days, excluding the Promotions, Social, Updates and Forums tabs, spam, trash and chats. You can restrict sync to chosen labels. Messages with a `Personal` label (configurable) are skipped.
- **Outlook:** Inbox and Sent Items by default (folders are configurable). Messages with the `Personal` category are skipped.
- **Bulk mail:** messages with List-Unsubscribe, Auto-Submitted or bulk Precedence headers are dropped by the resolver.
- **Visibility:** set per account to the whole team, or private to you.

A connected account starts a Temporal `AccountSyncWorkflow` (`sync-<account id>`): the backfill first, then incremental sync every 5 minutes. Without the worker, use **Sync now** (or `POST /api/ingest/connectors/<id>/sync?inline=true`) to fetch one page directly.
