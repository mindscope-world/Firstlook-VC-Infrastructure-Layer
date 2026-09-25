"use client";

import Link from "next/link";
import { use } from "react";
import { useApi } from "@/lib/api";
import { date, STAGE_LABEL, usd } from "@/lib/format";
import { Badge, Card, Empty, EntityLink, Loading, PageHeader, Strength, WarmPaths, type WarmPath } from "@/components/ui";

interface CompanyDetail {
  id: string;
  name: string;
  domain: string | null;
  country: string | null;
  description: string | null;
  people: { id: string; full_name: string; title: string | null; primary_email: string | null; strength: number | null }[];
  deals: { id: string; name: string; stage: string; restricted: boolean; round_size_usd: number | null }[];
  interactions: { id: string; kind: string; subject: string; occurred_at: string }[];
  warm_paths: WarmPath[];
}

interface Signal {
  signal: string;
  value: number;
  source: string;
  url: string;
  detail: { title?: string };
  observed_at: string;
}

const SIGNAL_LABEL: Record<string, string> = {
  funding_round_usd: "Funding round",
  headcount: "Headcount",
  open_roles: "Open roles",
  open_engineering_roles: "Engineering roles",
  github_stars: "GitHub stars",
  github_active_repos_30d: "Active repos (30d)",
  github_public_repos: "Public repos",
  web_visits_monthly: "Monthly web visits",
  news_mention: "News",
  incorporated: "Incorporated",
};

function Signals({ id }: { id: string }) {
  const { data } = useApi<Signal[]>(`/companies/${id}/signals`);
  if (!data || data.length === 0) return <Empty>No signals collected yet.</Empty>;
  const latest = new Map<string, Signal>();
  for (const s of data) if (s.signal !== "news_mention" && !latest.has(s.signal)) latest.set(s.signal, s);
  const news = data.filter((s) => s.signal === "news_mention").slice(0, 5);
  return (
    <div className="space-y-3 text-sm">
      <ul className="space-y-1.5">
        {[...latest.values()].map((s) => (
          <li key={s.signal} className="flex justify-between gap-2">
            <span className="text-muted">{SIGNAL_LABEL[s.signal] ?? s.signal}</span>
            <span className="text-right tabular-nums">
              {s.signal === "funding_round_usd" ? usd(s.value) : s.signal === "incorporated" ? date(s.observed_at) : s.value.toLocaleString()}
              <span className="ml-1.5 text-xs text-faint">{s.source}</span>
            </span>
          </li>
        ))}
      </ul>
      {news.length > 0 && (
        <ul className="space-y-1 border-t border-line pt-3">
          {news.map((n) => (
            <li key={n.url}>
              <a href={n.url} target="_blank" rel="noreferrer" className="hover:underline">
                {n.detail.title ?? n.url}
              </a>{" "}
              <span className="text-xs text-faint">{date(n.observed_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function CompanyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, error } = useApi<CompanyDetail>(`/companies/${id}`);
  if (!data) return <Loading error={error} />;
  return (
    <>
      <PageHeader
        title={data.name}
        subtitle={[data.domain, data.country, data.description].filter(Boolean).join(" · ")}
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Warm paths from your team">
            <WarmPaths paths={data.warm_paths} />
          </Card>
          <Card title="Interactions">
            {data.interactions.length === 0 ? (
              <Empty>None yet.</Empty>
            ) : (
              <ul className="divide-y divide-line text-sm">
                {data.interactions.map((i) => (
                  <li key={i.id} className="flex items-center gap-2 py-2">
                    <Badge tone={i.kind === "email" ? "neutral" : "info"}>{i.kind}</Badge>
                    <Link href={`/interactions/${i.id}`} className="min-w-0 flex-1 truncate hover:underline">
                      {i.subject || "(no subject)"}
                    </Link>
                    <span className="text-xs text-muted">{date(i.occurred_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
        <div className="space-y-6">
          <Card title="Signals">
            <Signals id={data.id} />
          </Card>
          <Card title="Deals">
            {data.deals.length === 0 ? (
              <Empty>Not in the pipeline.</Empty>
            ) : (
              <ul className="space-y-2 text-sm">
                {data.deals.map((d) => (
                  <li key={d.id} className="flex items-center justify-between">
                    <span>
                      {d.name} {d.restricted && <Badge tone="warn">restricted</Badge>}
                    </span>
                    <span className="flex items-center gap-2">
                      <span className="text-xs text-muted">{usd(d.round_size_usd)}</span>
                      <Badge tone="good">{STAGE_LABEL[d.stage] ?? d.stage}</Badge>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card title="People">
            {data.people.length === 0 ? (
              <Empty>No one yet.</Empty>
            ) : (
              <ul className="space-y-2 text-sm">
                {data.people.map((p) => (
                  <li key={p.id} className="flex items-center justify-between gap-2">
                    <span className="min-w-0">
                      <EntityLink type="person" id={p.id}>
                        {p.full_name}
                      </EntityLink>
                      <p className="truncate text-xs text-muted">{p.title ?? p.primary_email}</p>
                    </span>
                    <Strength value={p.strength} />
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
