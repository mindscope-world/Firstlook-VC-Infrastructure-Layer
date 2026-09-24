"use client";

import Link from "next/link";
import { useState } from "react";
import { useApi } from "@/lib/api";
import { date } from "@/lib/format";
import { Badge, Card, Empty, Loading, PageHeader } from "@/components/ui";

interface Row {
  id: string;
  kind: string;
  subject: string | null;
  occurred_at: string;
  direction: string;
  visibility: string;
  snippet: string | null;
  participants: { name: string; role: string }[] | null;
  extraction_count: number;
}

const KINDS = ["", "email", "meeting", "transcript", "note"];

export default function InteractionsPage() {
  const [kind, setKind] = useState("");
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const params = new URLSearchParams({ limit: "100", ...(kind && { kind }), ...(search && { q: search }) });
  const { data, error } = useApi<Row[]>(`/interactions?${params}`);

  return (
    <>
      <PageHeader title="Interactions" subtitle="Emails, meetings, call transcripts and CRM notes, newest first." />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {KINDS.map((k) => (
          <button
            key={k || "all"}
            onClick={() => setKind(k)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium ${kind === k ? "bg-ink text-white" : "text-muted hover:bg-[#f4f1ed]"}`}
          >
            {k || "all"}
          </button>
        ))}
        <form
          className="ml-auto"
          onSubmit={(e) => {
            e.preventDefault();
            setSearch(q);
          }}
        >
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search subject and body"
            className="w-64 rounded-full border border-line bg-white px-4 py-2 text-sm outline-none focus:border-brand"
          />
        </form>
      </div>
      {!data ? (
        <Loading error={error} />
      ) : (
        <Card>
          {data.length === 0 ? (
            <Empty>No interactions match.</Empty>
          ) : (
            <ul className="divide-y divide-line">
              {data.map((i) => (
                <li key={i.id} className="py-3">
                  <div className="flex items-center gap-2">
                    <Badge tone={i.kind === "email" ? "neutral" : "info"}>{i.kind}</Badge>
                    {i.direction && i.kind === "email" && <Badge>{i.direction}</Badge>}
                    {i.visibility === "private" && <Badge tone="warn">private</Badge>}
                    <Link href={`/interactions/${i.id}`} className="min-w-0 flex-1 truncate text-sm font-medium hover:underline">
                      {i.subject || "(no subject)"}
                    </Link>
                    {i.extraction_count > 0 && <Badge tone="brand">{i.extraction_count} found</Badge>}
                    <span className="text-xs text-muted">{date(i.occurred_at)}</span>
                  </div>
                  <p className="mt-1 truncate text-xs text-muted">
                    {(i.participants ?? []).map((p) => p.name).join(", ")}
                    {i.snippet ? ` — ${i.snippet}` : ""}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </>
  );
}
