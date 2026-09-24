"use client";

import Link from "next/link";
import { useState } from "react";
import { api, useApi } from "@/lib/api";
import { date, usd } from "@/lib/format";
import { Badge, Button, Card, Empty, Loading, PageHeader } from "@/components/ui";

interface Person {
  name: string;
  email: string;
  company: string;
}
interface Extraction {
  id: string;
  kind: "intro" | "next_step" | "deal_mention";
  payload: Record<string, unknown>;
  citations: { quote: string; start: number }[];
  confidence: number;
  status: string;
  interaction_id: string;
  subject: string;
  occurred_at: string;
}

const TABS = [
  { key: "proposed", label: "To review" },
  { key: "accepted", label: "Open next steps", kind: "next_step" },
  { key: "done", label: "Done" },
  { key: "rejected", label: "Dismissed" },
];

function describe(x: Extraction) {
  const p = x.payload;
  if (x.kind === "intro") {
    const introducer = p.introducer as Person;
    const introduced = (p.introduced as Person[]).map((i) => i.name).join(" and ");
    const verb = p.status === "made" ? "introduced" : p.status === "offered" ? "offered to introduce" : "was asked to introduce";
    return (
      <>
        <b>{introducer.name}</b> {verb} {introduced}
        {p.context ? <span className="text-muted"> — {String(p.context)}</span> : null}
      </>
    );
  }
  if (x.kind === "next_step") {
    const owner = p.owner as Person;
    return (
      <>
        <b>{owner.name || "Someone"}</b>
        {p.owner_side === "us" ? <Badge tone="brand">our team</Badge> : null}: {String(p.action)}
        {p.due ? <span className="text-muted"> (due {String(p.due)})</span> : null}
      </>
    );
  }
  return (
    <>
      <b>{String(p.company_name)}</b>
      {p.stage ? ` · ${String(p.stage)}` : ""}
      {p.round_size_usd ? ` · ${usd(Number(p.round_size_usd))} round` : ""}
      {p.summary ? <span className="text-muted"> — {String(p.summary)}</span> : null}
    </>
  );
}

const KIND_LABEL = { intro: "Intro", next_step: "Next step", deal_mention: "Deal" };

export default function InboxPage() {
  const [tab, setTab] = useState(TABS[0]!);
  const query = `/extractions?status=${tab.key}${tab.kind ? `&kind=${tab.kind}` : ""}`;
  const { data, error, reload } = useApi<Extraction[]>(query);
  const [busy, setBusy] = useState<string | null>(null);

  async function decide(id: string, decision: string) {
    setBusy(id);
    try {
      await api(`/extractions/${id}`, { method: "POST", json: { decision } });
      await reload();
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <PageHeader
        title="Inbox"
        subtitle="Intros, next steps and deal mentions found in your team's communications. Nothing is written to the CRM until you accept it."
      />
      <div className="mb-4 flex gap-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t)}
            className={`rounded-lg px-3 py-1.5 text-sm ${tab.key === t.key ? "bg-ink text-white" : "text-slate-600 hover:bg-slate-100"}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {!data ? (
        <Loading error={error} />
      ) : data.length === 0 ? (
        <Card>
          <Empty>Nothing here.</Empty>
        </Card>
      ) : (
        <div className="space-y-3">
          {data.map((x) => (
            <Card key={x.id}>
              <div className="flex items-start gap-3">
                <Badge tone={x.kind === "deal_mention" ? "good" : x.kind === "intro" ? "info" : "neutral"}>{KIND_LABEL[x.kind]}</Badge>
                <div className="min-w-0 flex-1">
                  <p className="text-sm">{describe(x)}</p>
                  <blockquote className="mt-2 border-l-2 border-amber-300 pl-3 text-sm text-slate-600">“{x.citations[0]?.quote}”</blockquote>
                  <p className="mt-2 text-xs text-muted">
                    From{" "}
                    <Link href={`/interactions/${x.interaction_id}#cite-${x.citations[0]?.start}`} className="underline">
                      {x.subject || "an interaction"}
                    </Link>{" "}
                    · {date(x.occurred_at)} · confidence {Math.round(x.confidence * 100)}%
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  {x.status === "proposed" && (
                    <>
                      <Button disabled={busy === x.id} onClick={() => decide(x.id, "accepted")}>
                        {x.kind === "deal_mention" ? "Add to pipeline" : "Accept"}
                      </Button>
                      <Button variant="secondary" disabled={busy === x.id} onClick={() => decide(x.id, "rejected")}>
                        Dismiss
                      </Button>
                    </>
                  )}
                  {x.status === "accepted" && x.kind === "next_step" && (
                    <Button variant="secondary" disabled={busy === x.id} onClick={() => decide(x.id, "done")}>
                      Mark done
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
