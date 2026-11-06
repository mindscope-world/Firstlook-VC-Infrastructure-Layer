"use client";

import { useEffect, useState } from "react";
import { Check, Plus, RefreshCw, ThumbsDown, ThumbsUp } from "lucide-react";
import { api, useApi } from "@/lib/api";
import { relative, STAGE_LABEL, usd } from "@/lib/format";
import { Badge, Button, Card, Empty, EntityLink, Loading, PageHeader } from "@/components/ui";
import { ThesisEditor, type Thesis } from "@/components/thesis-editor";

interface Citation {
  fact_id: string;
  kind: string;
  label: string;
  url: string;
}
interface Item {
  company_id: string;
  name: string;
  domain: string | null;
  country: string | null;
  stage: string | null;
  sectors: string[];
  description: string | null;
  last_round_usd: number | null;
  rank: number;
  stage1_score: number;
  stage2_score: number | null;
  final_score: number;
  features: Record<string, number>;
  rationale: string | null;
  concerns: string | null;
  citations: Citation[];
  deal_stage: string | null;
  my_vote: number | null;
  team_votes: number;
  new_this_week: boolean;
}
interface Feed {
  run: { id: string; ranker: string; rerank_model: string | null; finished_at: string; candidates: number; scored: number; reranked: number; version: number } | null;
  items: Item[];
}

const FEATURE_LABEL: Record<string, string> = {
  sector: "Sector",
  stage: "Stage",
  geo: "Geography",
  cheque: "Cheque fit",
  text: "Thesis match",
  momentum: "Momentum",
  warm: "Warm intro",
};

function FeatureBars({ f }: { f: Record<string, number> }) {
  return (
    <div className="grid grid-cols-7 gap-2">
      {Object.keys(FEATURE_LABEL).map((k) => (
        <div key={k} title={`${FEATURE_LABEL[k]}: ${(f[k] ?? 0).toFixed(2)}`}>
          <div className="h-1.5 overflow-hidden rounded-full bg-[#efe9e3]">
            <div className="h-full rounded-full bg-brand" style={{ width: `${Math.round((f[k] ?? 0) * 100)}%`, opacity: 0.35 + 0.65 * (f[k] ?? 0) }} />
          </div>
          <p className="mt-1 truncate text-[10px] text-faint">{FEATURE_LABEL[k]}</p>
        </div>
      ))}
    </div>
  );
}

function Rationale({ item }: { item: Item }) {
  if (!item.rationale) {
    return <p className="text-sm text-faint">Ranked on signals only (outside the re-ranked top of this run).</p>;
  }
  return (
    <div className="space-y-2">
      <p className="text-sm leading-relaxed">{item.rationale}</p>
      {item.concerns && <p className="text-sm text-muted">Concern: {item.concerns}</p>}
      {item.citations.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {item.citations.map((c) => {
            const chip = (
              <span className="inline-flex max-w-[280px] items-center gap-1 truncate rounded-full bg-brand-soft px-2.5 py-0.5 text-[11px] text-brand-deep" title={c.label}>
                <span className="font-semibold">{c.kind}</span> {c.label}
              </span>
            );
            return c.url ? (
              <a key={c.fact_id} href={c.url} target="_blank" rel="noreferrer" className="hover:opacity-80">
                {chip}
              </a>
            ) : (
              <span key={c.fact_id}>{chip}</span>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function SourcingPage() {
  const theses = useApi<Thesis[]>("/theses");
  const [selected, setSelected] = useState<string | null>(null);
  const [editing, setEditing] = useState<Thesis | "new" | null>(null);
  const [hidePipeline, setHidePipeline] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const thesis = theses.data?.find((t) => t.id === selected) ?? null;
  const feed = useApi<Feed>(selected ? `/sourcing/feed?thesis=${selected}&hide_pipeline=${hidePipeline}` : null);

  useEffect(() => {
    if (!selected && theses.data?.length) setSelected(theses.data.find((t) => t.active)?.id ?? theses.data[0]!.id);
  }, [theses.data, selected]);

  async function vote(item: Item, v: 1 | -1) {
    await api("/sourcing/feedback", { method: "POST", json: { thesis_id: selected, company_id: item.company_id, vote: item.my_vote === v ? 0 : v } });
    await feed.reload();
  }

  async function addToPipeline(item: Item) {
    try {
      await api("/deals", { method: "POST", json: { name: item.name, company_id: item.company_id, stage: "sourced" } });
      setNote(`${item.name} added to the pipeline.`);
      await feed.reload();
    } catch (e) {
      setNote(e instanceof Error ? e.message : String(e));
    }
  }

  async function rerun() {
    await api("/sourcing/run", { method: "POST", json: { thesis_id: selected } });
    setNote("Re-ranking queued. The feed updates when the sourcing service finishes.");
  }

  if (!theses.data) return <Loading error={theses.error} />;

  return (
    <>
      <PageHeader
        title="Sourcing"
        subtitle="Companies ranked against your thesis from vendor data, registries, news, hiring and GitHub signals, and your team's relationships."
        actions={
          <div className="flex gap-2">
            {thesis && (
              <Button variant="secondary" onClick={() => setEditing(thesis)}>
                Edit thesis
              </Button>
            )}
            <Button onClick={() => setEditing("new")}>
              <Plus size={15} /> New thesis
            </Button>
          </div>
        }
      />

      {theses.data.length === 0 ? (
        <Card>
          <Empty>No thesis yet. Create one to start ranking companies.</Empty>
        </Card>
      ) : (
        <>
          <div className="mb-5 flex flex-wrap items-center gap-2">
            {theses.data.map((t) => (
              <button
                key={t.id}
                onClick={() => setSelected(t.id)}
                className={`rounded-full px-4 py-1.5 text-sm font-medium ${t.id === selected ? "bg-ink text-white" : "bg-white/80 text-muted shadow-[0_1px_2px_rgba(16,19,26,0.06)] hover:text-ink"}`}
              >
                {t.name}
                {!t.active && " (archived)"}
              </button>
            ))}
          </div>

          {thesis && (
            <Card className="mb-5">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                {thesis.sectors.map((s) => (
                  <Badge key={s} tone="brand">
                    {s}
                  </Badge>
                ))}
                {thesis.stages.map((s) => (
                  <Badge key={s}>{s}</Badge>
                ))}
                {thesis.geographies.map((g) => (
                  <Badge key={g} tone="info">
                    {g}
                  </Badge>
                ))}
                {(thesis.cheque_min_usd || thesis.cheque_max_usd) && (
                  <Badge>
                    cheque {usd(thesis.cheque_min_usd)}–{usd(thesis.cheque_max_usd)}
                  </Badge>
                )}
                <span className="ml-auto flex items-center gap-3 text-xs text-faint">
                  {feed.data?.run && (
                    <>
                      v{feed.data.run.version} · {feed.data.run.scored} ranked · {feed.data.run.ranker}
                      {feed.data.run.rerank_model ? ` · re-ranked by ${feed.data.run.rerank_model}` : ""} · {relative(feed.data.run.finished_at)}
                    </>
                  )}
                  <span>{thesis.labels} votes</span>
                  <Button variant="ghost" onClick={rerun}>
                    <RefreshCw size={13} /> Re-rank
                  </Button>
                </span>
              </div>
            </Card>
          )}

          <div className="mb-4 flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-muted">
              <input type="checkbox" checked={hidePipeline} onChange={(e) => setHidePipeline(e.target.checked)} /> Hide companies already in the pipeline
            </label>
            {note && <span className="text-sm text-muted">{note}</span>}
          </div>

          {!feed.data ? (
            <Loading error={feed.error} />
          ) : !feed.data.run ? (
            <Card>
              <Empty>This thesis hasn&apos;t been ranked yet. The sourcing service ranks new theses within a minute when it&apos;s running.</Empty>
            </Card>
          ) : feed.data.items.length === 0 ? (
            <Card>
              <Empty>No companies match this thesis yet.</Empty>
            </Card>
          ) : (
            <div className="space-y-3">
              {feed.data.items.map((item) => (
                <Card key={item.company_id}>
                  <div className="flex gap-5">
                    <div className="w-12 shrink-0 text-center">
                      <p className="display text-[30px] leading-none">{item.rank}</p>
                      <p className="mt-1 text-[11px] tabular-nums text-faint">{item.final_score.toFixed(2)}</p>
                    </div>
                    <div className="min-w-0 flex-1 space-y-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-[17px] font-semibold">
                          <EntityLink type="company" id={item.company_id}>
                            {item.name}
                          </EntityLink>
                        </span>
                        {item.new_this_week && <Badge tone="brand">new this week</Badge>}
                        {item.stage && <Badge>{item.stage}</Badge>}
                        {item.country && <Badge tone="info">{item.country}</Badge>}
                        {item.sectors.slice(0, 3).map((s) => (
                          <Badge key={s}>{s}</Badge>
                        ))}
                        {item.last_round_usd && <span className="text-xs text-faint">last round {usd(item.last_round_usd)}</span>}
                        {item.deal_stage && <Badge tone="good">in pipeline: {STAGE_LABEL[item.deal_stage] ?? item.deal_stage}</Badge>}
                      </div>
                      {item.description && <p className="text-sm text-muted">{item.description}</p>}
                      <Rationale item={item} />
                      <FeatureBars f={item.features} />
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-2">
                      <div className="flex gap-1">
                        <button
                          onClick={() => vote(item, 1)}
                          aria-label="Good fit"
                          className={`rounded-full p-2 transition ${item.my_vote === 1 ? "bg-ink text-white" : "bg-[#f4f1ed] text-muted hover:text-ink"}`}
                        >
                          <ThumbsUp size={15} />
                        </button>
                        <button
                          onClick={() => vote(item, -1)}
                          aria-label="Not a fit"
                          className={`rounded-full p-2 transition ${item.my_vote === -1 ? "bg-ink text-white" : "bg-[#f4f1ed] text-muted hover:text-ink"}`}
                        >
                          <ThumbsDown size={15} />
                        </button>
                      </div>
                      {item.team_votes !== 0 && <span className="text-[11px] text-faint">team {item.team_votes > 0 ? `+${item.team_votes}` : item.team_votes}</span>}
                      {item.deal_stage ? (
                        <span className="inline-flex items-center gap-1 text-xs text-faint">
                          <Check size={12} /> in pipeline
                        </span>
                      ) : (
                        <Button variant="secondary" onClick={() => addToPipeline(item)}>
                          Add to pipeline
                        </Button>
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {editing && (
        <ThesisEditor
          thesis={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={async (id) => {
            setEditing(null);
            setSelected(id);
            setNote("Saved. Re-ranking against the new version is queued.");
            await theses.reload();
          }}
        />
      )}
    </>
  );
}
