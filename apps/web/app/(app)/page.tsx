"use client";

import Link from "next/link";
import { useApi } from "@/lib/api";
import { relative } from "@/lib/format";
import { Badge, Card, EntityLink, Loading, PageHeader, Strength } from "@/components/ui";

interface Dashboard {
  counts: Record<string, number>;
  recent: { id: string; kind: string; subject: string; occurred_at: string; direction: string; from_names: string | null }[];
  strongest: { person_id: string; full_name: string; company: string | null; strength: number }[];
}

const STATS: [string, string, string][] = [
  ["interactions_30d", "Interactions (30 days)", "/interactions"],
  ["people", "People", "/people"],
  ["companies", "Companies", "/companies"],
  ["deals", "Deals", "/deals"],
  ["extractions_proposed", "To review in inbox", "/inbox"],
  ["review_pending", "Possible duplicates", "/review"],
];

export default function Overview() {
  const { data, error } = useApi<Dashboard>("/dashboard");
  if (!data) return <Loading error={error} />;
  return (
    <>
      <PageHeader title="Overview" subtitle="Everything captured from your team's email, calendar and calls." />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        {STATS.map(([key, label, href]) => (
          <Link key={key} href={href} className="rounded-3xl bg-white/90 p-5 shadow-[0_12px_40px_rgba(16,19,26,0.06),0_1px_2px_rgba(16,19,26,0.04)] transition hover:-translate-y-0.5">
            <p className="display text-[32px] leading-none tabular-nums">{data.counts[key] ?? 0}</p>
            <p className="mt-1 text-xs text-muted">{label}</p>
          </Link>
        ))}
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="Latest interactions">
          <ul className="divide-y divide-line">
            {data.recent.map((i) => (
              <li key={i.id} className="flex items-center gap-3 py-2 text-sm">
                <Badge tone={i.kind === "email" ? "neutral" : "info"}>{i.kind}</Badge>
                <Link href={`/interactions/${i.id}`} className="min-w-0 flex-1 truncate hover:underline">
                  {i.subject || "(no subject)"}
                </Link>
                <span className="shrink-0 text-xs text-muted">{relative(i.occurred_at)}</span>
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Strongest relationships">
          <ul className="divide-y divide-line">
            {data.strongest.map((p) => (
              <li key={p.person_id} className="flex items-center gap-3 py-2 text-sm">
                <span className="min-w-0 flex-1 truncate">
                  <EntityLink type="person" id={p.person_id}>
                    {p.full_name}
                  </EntityLink>
                  {p.company && <span className="text-muted"> · {p.company}</span>}
                </span>
                <Strength value={p.strength} />
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  );
}
