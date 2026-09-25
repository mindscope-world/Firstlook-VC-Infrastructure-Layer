"use client";

import { useState } from "react";
import { api, useApi } from "@/lib/api";
import { date } from "@/lib/format";
import { Button } from "@/components/ui";

export interface Thesis {
  id: string;
  name: string;
  active: boolean;
  version: number;
  sectors: string[];
  stages: string[];
  geographies: string[];
  cheque_min_usd: number | null;
  cheque_max_usd: number | null;
  founder_profile: string;
  description: string;
  labels: number;
  last_run: { id: string; status: string; finished_at: string | null; scored: number; ranker: string; rerank_model: string | null } | null;
}

interface Taxonomy {
  sectors: string[];
  stages: string[];
  regions: string[];
}

function Chips({ options, value, onChange, label }: { options: string[]; value: string[]; onChange: (v: string[]) => void; label: (s: string) => string }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((o) => {
        const on = value.includes(o);
        return (
          <button
            key={o}
            type="button"
            onClick={() => onChange(on ? value.filter((x) => x !== o) : [...value, o])}
            className={`rounded-full px-3 py-1 text-xs font-medium transition ${on ? "bg-ink text-white" : "bg-[#f4f1ed] text-muted hover:text-ink"}`}
          >
            {label(o)}
          </button>
        );
      })}
    </div>
  );
}

const pretty = (s: string) => s.replace(/-/g, " ").replace(/^\w/, (c) => c.toUpperCase());

export function ThesisEditor({ thesis, onClose, onSaved }: { thesis: Thesis | null; onClose: () => void; onSaved: (id: string) => void }) {
  const { data: tax } = useApi<Taxonomy>("/sourcing/taxonomy");
  const versions = useApi<{ id: string; version: number; created_at: string; created_by: string | null }[]>(thesis ? `/theses/${thesis.id}/versions` : null);
  const [form, setForm] = useState({
    name: thesis?.name ?? "",
    sectors: thesis?.sectors ?? [],
    stages: thesis?.stages ?? [],
    regions: (thesis?.geographies ?? []).filter((g) => g.length > 2),
    countries: (thesis?.geographies ?? []).filter((g) => g.length === 2).join(", "),
    cheque_min_usd: thesis?.cheque_min_usd?.toString() ?? "",
    cheque_max_usd: thesis?.cheque_max_usd?.toString() ?? "",
    founder_profile: thesis?.founder_profile ?? "",
    description: thesis?.description ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => setForm({ ...form, [k]: v });

  async function save() {
    setSaving(true);
    setError(null);
    const countries = form.countries.split(/[\s,]+/).map((c) => c.trim().toUpperCase()).filter((c) => /^[A-Z]{2}$/.test(c));
    const body = {
      name: form.name.trim(),
      sectors: form.sectors,
      stages: form.stages,
      geographies: [...form.regions, ...countries],
      cheque_min_usd: form.cheque_min_usd ? Number(form.cheque_min_usd) : null,
      cheque_max_usd: form.cheque_max_usd ? Number(form.cheque_max_usd) : null,
      founder_profile: form.founder_profile,
      description: form.description,
    };
    try {
      const res = await api<{ id: string }>(thesis ? `/theses/${thesis.id}` : "/theses", { method: thesis ? "PUT" : "POST", json: body });
      onSaved(res.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  const input = "w-full rounded-2xl border border-line bg-white px-4 py-2.5 text-sm outline-none focus:border-brand focus:ring-4 focus:ring-brand/15";
  const label = "mb-1.5 block text-xs font-semibold uppercase tracking-[0.1em] text-faint";

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-ink/30 backdrop-blur-sm" onClick={onClose}>
      <div className="h-full w-full max-w-xl overflow-y-auto bg-[#fbf9f7] p-8 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between">
          <div>
            <h2 className="display text-[28px]">{thesis ? "Edit thesis" : "New thesis"}</h2>
            <p className="mt-1 text-sm text-muted">
              {thesis ? `Saving creates version ${thesis.version + 1}; the feed re-ranks against it.` : "The feed ranks every tracked company against it."}
            </p>
          </div>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
        <div className="mt-6 space-y-5">
          <div>
            <label className={label}>Name</label>
            <input className={input} value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="East Africa financial inclusion" />
          </div>
          <div>
            <label className={label}>Sectors</label>
            <Chips options={tax?.sectors ?? []} value={form.sectors} onChange={(v) => set("sectors", v)} label={pretty} />
          </div>
          <div>
            <label className={label}>Stages (two or more stages away are filtered out)</label>
            <Chips options={tax?.stages ?? []} value={form.stages} onChange={(v) => set("stages", v)} label={pretty} />
          </div>
          <div>
            <label className={label}>Geographies (companies elsewhere are filtered out)</label>
            <Chips options={tax?.regions ?? []} value={form.regions} onChange={(v) => set("regions", v)} label={pretty} />
            <input className={`${input} mt-2`} value={form.countries} onChange={(e) => set("countries", e.target.value)} placeholder="Extra countries as ISO codes, e.g. NG, GH" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={label}>Cheque min (USD)</label>
              <input className={input} inputMode="numeric" value={form.cheque_min_usd} onChange={(e) => set("cheque_min_usd", e.target.value.replace(/\D/g, ""))} placeholder="250000" />
            </div>
            <div>
              <label className={label}>Cheque max (USD)</label>
              <input className={input} inputMode="numeric" value={form.cheque_max_usd} onChange={(e) => set("cheque_max_usd", e.target.value.replace(/\D/g, ""))} placeholder="1000000" />
            </div>
          </div>
          <div>
            <label className={label}>Founder profile</label>
            <textarea className={`${input} min-h-20`} value={form.founder_profile} onChange={(e) => set("founder_profile", e.target.value)} />
          </div>
          <div>
            <label className={label}>Thesis in your words</label>
            <textarea
              className={`${input} min-h-28`}
              value={form.description}
              onChange={(e) => set("description", e.target.value)}
              placeholder="What you back and why. Used for similarity matching and by the re-ranking model."
            />
          </div>
          {error && <p className="rounded-2xl bg-[#fbe3df] px-4 py-2.5 text-sm text-[#a33a2c]">{error}</p>}
          <Button onClick={save} disabled={saving || !form.name.trim()}>
            {saving ? "Saving…" : thesis ? `Save as version ${thesis.version + 1}` : "Create thesis"}
          </Button>
        </div>
        {thesis && versions.data && versions.data.length > 0 && (
          <div className="mt-10">
            <p className={label}>Version history</p>
            <ul className="space-y-1 text-sm">
              {versions.data.map((v) => (
                <li key={v.id} className="flex justify-between text-muted">
                  <span>Version {v.version}</span>
                  <span>
                    {v.created_by ?? "system"} · {date(v.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
