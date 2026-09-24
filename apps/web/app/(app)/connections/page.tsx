"use client";

import { useState } from "react";
import { api, useApi } from "@/lib/api";
import { relative } from "@/lib/format";
import { Badge, Button, Card, Empty, Loading, PageHeader } from "@/components/ui";

interface Provider {
  provider: string;
  label: string;
  configured: boolean;
}
interface Account {
  id: string;
  provider: string;
  account_email: string;
  status: string;
  last_error: string | null;
  last_synced_at: string | null;
  items: number;
  settings: {
    labels?: string[];
    folders?: string[];
    exclude_personal?: boolean;
    personal_labels?: string[];
    default_visibility?: "team" | "private";
  };
}

function AccountRow({ a, onChange }: { a: Account; onChange: () => void }) {
  const [open, setOpen] = useState(false);
  const [labels, setLabels] = useState<{ id: string; name: string }[] | null>(null);
  const [selected, setSelected] = useState<string[]>(a.settings.labels ?? a.settings.folders ?? []);
  const [excludePersonal, setExcludePersonal] = useState(a.settings.exclude_personal ?? true);
  const [visibility, setVisibility] = useState(a.settings.default_visibility ?? "team");
  const [note, setNote] = useState<string | null>(null);
  const mailbox = a.provider === "google" || a.provider === "microsoft";

  async function loadLabels() {
    setOpen(!open);
    if (!labels && mailbox) {
      try {
        setLabels(await api(`/ingest/connectors/${a.id}/labels`));
      } catch (e) {
        setNote(e instanceof Error ? e.message : String(e));
      }
    }
  }

  async function save() {
    const key = a.provider === "google" ? "labels" : "folders";
    await api(`/ingest/connectors/${a.id}`, {
      method: "PATCH",
      json: { [key]: selected, exclude_personal: excludePersonal, default_visibility: visibility },
    });
    setNote("Saved. Sync restarts with the new scope.");
    onChange();
  }

  async function act(path: string, method: string) {
    try {
      const res = await api<Record<string, unknown>>(`/ingest/connectors/${a.id}${path}`, { method });
      setNote(res.mode === "inline" ? `Fetched a page: ${res.stored} new, ${res.skipped} skipped.` : "Sync started.");
      onChange();
    } catch (e) {
      setNote(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <li className="py-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium">{a.account_email}</span>
        <Badge>{a.provider}</Badge>
        <Badge tone={a.status === "active" ? "good" : a.status === "error" ? "bad" : "neutral"}>{a.status}</Badge>
        <span className="text-xs text-muted">
          {a.items} items · synced {relative(a.last_synced_at)}
        </span>
        <span className="ml-auto flex gap-1">
          <Button variant="secondary" onClick={loadLabels}>
            Settings
          </Button>
          <Button variant="secondary" onClick={() => act("/sync", "POST")}>
            Sync now
          </Button>
          <Button variant="danger" onClick={() => act("", "DELETE")}>
            Disconnect
          </Button>
        </span>
      </div>
      {a.last_error && <p className="mt-1 text-xs text-[#a33a2c]">{a.last_error}</p>}
      {open && (
        <div className="mt-3 space-y-3 rounded-2xl bg-[#f7f4f0] p-4 text-sm">
          {mailbox && (
            <div>
              <p className="text-xs font-medium text-muted">
                {a.provider === "google" ? "Labels" : "Folders"} to sync (none selected = all mail except promotions, social and updates)
              </p>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {(labels ?? []).map((l) => {
                  const value = a.provider === "google" ? l.name : l.id;
                  const on = selected.includes(value);
                  return (
                    <button
                      key={l.id}
                      onClick={() => setSelected(on ? selected.filter((x) => x !== value) : [...selected, value])}
                      className={`rounded-full border px-2 py-0.5 text-xs ${on ? "border-brand bg-brand-soft text-brand-deep" : "border-line bg-white"}`}
                    >
                      {l.name}
                    </button>
                  );
                })}
                {labels === null && <span className="text-xs text-muted">Loading…</span>}
              </div>
            </div>
          )}
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={excludePersonal} onChange={(e) => setExcludePersonal(e.target.checked)} />
            Exclude personal email (messages labelled or categorised “Personal”)
          </label>
          <label className="flex items-center gap-2">
            Visible to
            <select value={visibility} onChange={(e) => setVisibility(e.target.value as "team" | "private")} className="rounded-full border border-line bg-white px-3 py-1">
              <option value="team">the whole team</option>
              <option value="private">only me</option>
            </select>
          </label>
          <Button onClick={save}>Save</Button>
        </div>
      )}
      {note && <p className="mt-2 text-xs text-muted">{note}</p>}
    </li>
  );
}

function CrmImport() {
  const [vendor, setVendor] = useState("hubspot");
  const [objectType, setObjectType] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<string | null>(null);

  async function upload() {
    if (!file) return;
    const form = new FormData();
    form.set("vendor", vendor);
    if (objectType) form.set("object_type", objectType);
    form.set("file", file);
    try {
      const r = await api<Record<string, number>>("/ingest/imports/csv", { method: "POST", body: form });
      setResult(`Imported ${r.companies} companies, ${r.people} people, ${r.deals} deals, ${r.notes} notes; ${r.queued_for_review} sent to the review queue.`);
    } catch (e) {
      setResult(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <Card title="Import from your CRM">
      <p className="mb-3 text-sm text-muted">
        Upload a CSV export from Affinity, HubSpot, Salesforce or Airtable. Records go through entity resolution, so re-importing updates instead of duplicating.
      </p>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <select value={vendor} onChange={(e) => setVendor(e.target.value)} className="rounded-full border border-line bg-white px-3 py-2">
          <option value="hubspot">HubSpot</option>
          <option value="affinity">Affinity</option>
          <option value="salesforce">Salesforce</option>
          <option value="airtable">Airtable</option>
        </select>
        <select value={objectType} onChange={(e) => setObjectType(e.target.value)} className="rounded-full border border-line bg-white px-3 py-2">
          <option value="">Detect contents</option>
          <option value="people">People</option>
          <option value="companies">Companies</option>
          <option value="deals">Deals</option>
          <option value="notes">Notes</option>
        </select>
        <input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <Button onClick={upload} disabled={!file}>
          Import
        </Button>
      </div>
      {result && <p className="mt-3 text-sm">{result}</p>}
    </Card>
  );
}

export default function ConnectionsPage() {
  const providers = useApi<Provider[]>("/ingest/connectors/providers");
  const accounts = useApi<Account[]>("/ingest/connectors");
  const params = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;

  return (
    <>
      <PageHeader title="Connections" subtitle="Connect your own mailbox, calendar and call recordings. You choose what gets synced." />
      {params?.get("connected") && <p className="mb-4 rounded-2xl bg-[#e5f0e8] px-4 py-2.5 text-sm text-[#2f6b45]">Connected. The first sync has started.</p>}
      {params?.get("error") && <p className="mb-4 rounded-2xl bg-[#fbe3df] px-4 py-2.5 text-sm text-[#a33a2c]">Connection failed: {params.get("error")}</p>}
      <div className="space-y-6">
        <Card title="Add a connection">
          {!providers.data ? (
            <Loading error={providers.error} />
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {providers.data.map((p) => (
                <div key={p.provider} className="flex items-center justify-between rounded-2xl border border-line p-4 text-sm">
                  <span>{p.label}</span>
                  {p.configured ? (
                    <a href={`/api/ingest/connectors/${p.provider}/start`} className="rounded-full bg-ink px-4 py-2 text-sm font-medium text-white hover:bg-ink-soft">
                      Connect
                    </a>
                  ) : (
                    <span className="text-xs text-muted" title="Set the OAuth client ID and secret in .env (docs/connectors.md)">
                      not configured
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
        <Card title="Your connections">
          {!accounts.data ? (
            <Loading error={accounts.error} />
          ) : accounts.data.length === 0 ? (
            <Empty>No connections yet.</Empty>
          ) : (
            <ul className="divide-y divide-line">
              {accounts.data.map((a) => (
                <AccountRow key={a.id} a={a} onChange={accounts.reload} />
              ))}
            </ul>
          )}
        </Card>
        <CrmImport />
      </div>
    </>
  );
}
