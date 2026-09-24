"use client";

import { useState } from "react";
import { api, useApi } from "@/lib/api";
import { date } from "@/lib/format";
import { Badge, Button, Card, Loading, PageHeader } from "@/components/ui";
import type { Me } from "@/components/shell";

interface Slack {
  installed: boolean;
  team_name?: string;
  deal_channel_id?: string | null;
}
interface AuditRow {
  id: number;
  actor_type: string;
  actor: string | null;
  action: string;
  resource_type: string;
  details: Record<string, unknown>;
  created_at: string;
}

function SlackCard({ admin }: { admin: boolean }) {
  const { data, reload } = useApi<Slack>("/ingest/slack");
  const [channel, setChannel] = useState("");
  const [note, setNote] = useState<string | null>(null);
  if (!data) return <Loading />;
  return (
    <Card title="Slack">
      {data.installed ? (
        <div className="space-y-3 text-sm">
          <p>
            Connected to <b>{data.team_name}</b>. Use <code>/firstlook &lt;company&gt;</code> in any channel.
          </p>
          <p>Deal channel: {data.deal_channel_id ?? <span className="text-muted">not set</span>}</p>
          {admin && (
            <form
              className="flex gap-2"
              onSubmit={async (e) => {
                e.preventDefault();
                try {
                  await api("/ingest/slack", { method: "PATCH", json: { deal_channel_id: channel } });
                  setNote("Saved.");
                  await reload();
                } catch (err) {
                  setNote(err instanceof Error ? err.message : String(err));
                }
              }}
            >
              <input value={channel} onChange={(e) => setChannel(e.target.value)} placeholder="Channel ID, e.g. C0123ABCD" className="w-56 rounded-lg border border-line px-3 py-1.5" />
              <Button type="submit">Set deal channel</Button>
            </form>
          )}
          {note && <p className="text-xs text-muted">{note}</p>}
        </div>
      ) : admin ? (
        <a href="/api/ingest/slack/install" className="inline-block rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-white">
          Add to Slack
        </a>
      ) : (
        <p className="text-sm text-muted">An admin can connect Slack.</p>
      )}
    </Card>
  );
}

export default function SettingsPage() {
  const { data: me } = useApi<Me>("/me");
  const team = useApi<{ id: string; name: string; email: string; role: string }[]>("/team");
  const admin = me?.role === "admin";
  const audit = useApi<AuditRow[]>(admin ? "/audit?limit=50" : null);

  return (
    <>
      <PageHeader title="Settings" />
      <div className="space-y-6">
        <SlackCard admin={admin} />
        <Card title="Team">
          {!team.data ? (
            <Loading error={team.error} />
          ) : (
            <ul className="divide-y divide-line text-sm">
              {team.data.map((u) => (
                <li key={u.id} className="flex items-center justify-between py-2">
                  <span>
                    {u.name} <span className="text-muted">{u.email}</span>
                  </span>
                  <Badge>{u.role}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
        {admin && (
          <Card title="Audit log">
            {!audit.data ? (
              <Loading error={audit.error} />
            ) : (
              <table className="w-full text-xs">
                <tbody className="divide-y divide-line">
                  {audit.data.map((a) => (
                    <tr key={a.id}>
                      <td className="py-1.5 pr-3 text-muted">{date(a.created_at)}</td>
                      <td className="py-1.5 pr-3">{a.actor ?? a.actor_type}</td>
                      <td className="py-1.5 pr-3 font-medium">{a.action}</td>
                      <td className="py-1.5 truncate text-muted">{a.resource_type}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        )}
      </div>
    </>
  );
}
