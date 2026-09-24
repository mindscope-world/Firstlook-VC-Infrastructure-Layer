"use client";

import { useState } from "react";
import { api, useApi } from "@/lib/api";
import { relative, STAGE_LABEL, STAGES, usd } from "@/lib/format";
import { Badge, Button, EntityLink, Loading, PageHeader } from "@/components/ui";

interface Deal {
  id: string;
  name: string;
  stage: string;
  restricted: boolean;
  round_size_usd: number | null;
  company_id: string | null;
  company: string | null;
  team: { id: string; name: string }[] | null;
  last_interaction_at: string | null;
  updated_at: string;
}

export default function DealsPage() {
  const { data, error, reload } = useApi<Deal[]>("/deals");
  const [name, setName] = useState("");
  const [restricted, setRestricted] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function move(deal: Deal, direction: 1 | -1) {
    const idx = STAGES.indexOf(deal.stage as (typeof STAGES)[number]);
    const next = STAGES[idx + direction];
    if (!next) return;
    try {
      await api(`/deals/${deal.id}`, { method: "PATCH", json: { stage: next } });
      await reload();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    }
  }

  async function create() {
    if (!name.trim()) return;
    try {
      await api("/deals", { method: "POST", json: { name: name.trim(), restricted } });
      setName("");
      setRestricted(false);
      await reload();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <>
      <PageHeader
        title="Deals"
        subtitle="Pipeline. Moving a deal posts to your Slack deal channel; restricted deals are visible only to their deal team."
        actions={
          <form
            className="flex items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void create();
            }}
          >
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="New deal name" className="w-48 rounded-full border border-line bg-white px-4 py-2 text-sm outline-none focus:border-brand" />
            <label className="flex items-center gap-1 text-xs text-muted">
              <input type="checkbox" checked={restricted} onChange={(e) => setRestricted(e.target.checked)} /> restricted
            </label>
            <Button type="submit">Add</Button>
          </form>
        }
      />
      {message && <p className="mb-4 rounded-2xl bg-[#fbe3df] px-4 py-2.5 text-sm text-[#a33a2c]">{message}</p>}
      {!data ? (
        <Loading error={error} />
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-4">
          {STAGES.map((stage) => {
            const deals = data.filter((d) => d.stage === stage);
            return (
              <div key={stage} className="w-60 shrink-0">
                <h3 className="mb-2 flex items-center justify-between px-1 text-xs font-semibold uppercase text-muted">
                  {STAGE_LABEL[stage]} <span>{deals.length}</span>
                </h3>
                <div className="space-y-2">
                  {deals.map((d) => (
                    <div key={d.id} className="rounded-2xl bg-white/90 p-4 text-sm shadow-[0_8px_24px_rgba(16,19,26,0.06),0_1px_2px_rgba(16,19,26,0.04)]">
                      <p className="font-medium">
                        {d.name} {d.restricted && <Badge tone="warn">restricted</Badge>}
                      </p>
                      {d.company_id && (
                        <p className="text-xs">
                          <EntityLink type="company" id={d.company_id}>
                            {d.company}
                          </EntityLink>
                        </p>
                      )}
                      <p className="mt-1 text-xs text-muted">
                        {usd(d.round_size_usd)} · updated {relative(d.updated_at)}
                      </p>
                      <div className="mt-2 flex justify-between">
                        <Button variant="ghost" onClick={() => move(d, -1)} disabled={stage === STAGES[0]}>
                          ←
                        </Button>
                        <Button variant="ghost" onClick={() => move(d, 1)} disabled={stage === STAGES[STAGES.length - 1]}>
                          →
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
