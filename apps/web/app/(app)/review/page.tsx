"use client";

import { useState } from "react";
import { api, useApi } from "@/lib/api";
import { Badge, Button, Card, Empty, EntityLink, Loading, PageHeader } from "@/components/ui";

interface Side {
  id: string;
  name: string;
  title: string | null;
  company: string | null;
  identifiers: string[] | null;
  interactions: number;
}
interface Candidate {
  id: string;
  entity_type: string;
  mention: { name?: string; email?: string; context?: string };
  score: number;
  features: { name_sim?: number; embed_sim?: number; same_org?: boolean };
  provisional: Side;
  candidate: Side;
  source: string | null;
}

function SideCard({ side, label }: { side: Side; label: string }) {
  return (
    <div className="flex-1 rounded-2xl border border-line p-4">
      <p className="text-xs uppercase text-muted">{label}</p>
      <p className="mt-1 font-medium">
        <EntityLink type="person" id={side.id}>
          {side.name}
        </EntityLink>
      </p>
      <p className="text-xs text-muted">{[side.title, side.company].filter(Boolean).join(" · ") || "—"}</p>
      <ul className="mt-2 space-y-0.5 text-xs">
        {(side.identifiers ?? []).map((i) => (
          <li key={i}>{i}</li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-muted">{side.interactions} interactions</p>
    </div>
  );
}

export default function ReviewPage() {
  const { data, error, reload } = useApi<Candidate[]>("/review");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function decide(id: string, decision: "merged" | "distinct") {
    setBusy(id);
    setErr(null);
    try {
      await api(`/review/${id}`, { method: "POST", json: { decision } });
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <PageHeader
        title="Review queue"
        subtitle="Possible duplicates that entity resolution wasn't confident enough to merge on its own."
      />
      {err && <p className="mb-4 rounded-2xl bg-[#fbe3df] px-4 py-2.5 text-sm text-[#a33a2c]">{err}</p>}
      {!data ? (
        <Loading error={error} />
      ) : data.length === 0 ? (
        <Card>
          <Empty>Nothing to review.</Empty>
        </Card>
      ) : (
        <div className="space-y-4">
          {data.map((c) => (
            <Card
              key={c.id}
              title={
                <span className="flex items-center gap-2">
                  Same {c.entity_type}? <Badge tone={c.score >= 0.85 ? "warn" : "neutral"}>match {Math.round(c.score * 100)}%</Badge>
                </span>
              }
              actions={
                <span className="text-xs text-muted">
                  name {c.features.name_sim?.toFixed(2)} · embedding {c.features.embed_sim?.toFixed(2)} · {c.features.same_org ? "same organisation" : "different organisation"}
                </span>
              }
            >
              <div className="flex flex-col gap-3 md:flex-row">
                <SideCard side={c.provisional} label="New mention" />
                <SideCard side={c.candidate} label="Existing record" />
              </div>
              {c.mention.context && <p className="mt-3 text-xs text-muted">Seen in: {c.mention.context}</p>}
              <div className="mt-3 flex gap-2">
                <Button disabled={busy === c.id} onClick={() => decide(c.id, "merged")}>
                  Same person, merge
                </Button>
                <Button variant="secondary" disabled={busy === c.id} onClick={() => decide(c.id, "distinct")}>
                  Different people
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
