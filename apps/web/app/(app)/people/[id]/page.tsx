"use client";

import Link from "next/link";
import { use } from "react";
import { useApi } from "@/lib/api";
import { date, relative } from "@/lib/format";
import { Badge, Card, Empty, EntityLink, Loading, PageHeader, Strength, WarmPaths, type WarmPath } from "@/components/ui";

interface Props {
  strength: number;
  recency: number;
  frequency: number;
  reciprocity: number;
  last_interaction_at: string;
  interactions_window: number;
  outbound: number;
  inbound: number;
}
interface PersonDetail {
  id: string;
  full_name: string;
  primary_email: string | null;
  title: string | null;
  is_internal: boolean;
  company_id: string | null;
  company: string | null;
  identifiers: { kind: string; value: string }[];
  relationships: { team_person_id: string; team_member: string; props: Props }[];
  related: { person_id: string; full_name: string; type: string; props: { strength?: number } }[];
  interactions: { id: string; kind: string; subject: string; occurred_at: string; direction: string }[];
  pending_review: { id: string; score: number }[];
  warm_paths: WarmPath[];
}

export default function PersonPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, error } = useApi<PersonDetail>(`/people/${id}`);
  if (!data) return <Loading error={error} />;
  return (
    <>
      <PageHeader
        title={data.full_name}
        subtitle={
          <>
            {data.title && `${data.title} · `}
            {data.company_id ? (
              <EntityLink type="company" id={data.company_id}>
                {data.company}
              </EntityLink>
            ) : (
              "No company"
            )}
            {data.is_internal && (
              <>
                {" "}
                <Badge tone="brand">team</Badge>
              </>
            )}
          </>
        }
      />
      {data.pending_review.length > 0 && (
        <p className="mb-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
          This person may be a duplicate. <Link href="/review" className="underline">Review it</Link>.
        </p>
      )}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {!data.is_internal && (
            <Card title="Relationships with your team">
              {data.relationships.length === 0 ? (
                <Empty>No direct interactions with the team yet.</Empty>
              ) : (
                <table className="w-full text-sm">
                  <thead className="text-left text-xs text-muted">
                    <tr>
                      <th className="pb-2 font-medium">Team member</th>
                      <th className="pb-2 font-medium">Strength</th>
                      <th className="pb-2 font-medium">Recency</th>
                      <th className="pb-2 font-medium">Frequency</th>
                      <th className="pb-2 font-medium">Reciprocity</th>
                      <th className="pb-2 font-medium">Last</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {data.relationships.map((r) => (
                      <tr key={r.team_person_id}>
                        <td className="py-2">
                          <EntityLink type="person" id={r.team_person_id}>
                            {r.team_member}
                          </EntityLink>
                        </td>
                        <td className="py-2">
                          <Strength value={r.props.strength} />
                        </td>
                        <td className="py-2 tabular-nums">{r.props.recency.toFixed(2)}</td>
                        <td className="py-2 tabular-nums">
                          {r.props.frequency.toFixed(2)} <span className="text-xs text-muted">({r.props.interactions_window})</span>
                        </td>
                        <td className="py-2 tabular-nums">
                          {r.props.reciprocity.toFixed(2)}{" "}
                          <span className="text-xs text-muted">
                            ({r.props.outbound} out / {r.props.inbound} in)
                          </span>
                        </td>
                        <td className="py-2 text-muted">{relative(r.props.last_interaction_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          )}
          {!data.is_internal && (
            <Card title="Warm paths">
              <WarmPaths paths={data.warm_paths} />
            </Card>
          )}
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
          <Card title="Identifiers">
            <ul className="space-y-1 text-sm">
              {data.identifiers.map((i) => (
                <li key={`${i.kind}:${i.value}`}>
                  <span className="mr-2 text-xs uppercase text-muted">{i.kind}</span>
                  {i.value}
                </li>
              ))}
            </ul>
          </Card>
          {data.related.length > 0 && (
            <Card title="Also connected to">
              <ul className="space-y-2 text-sm">
                {data.related.map((r) => (
                  <li key={`${r.person_id}-${r.type}`} className="flex items-center justify-between gap-2">
                    <span>
                      <EntityLink type="person" id={r.person_id}>
                        {r.full_name}
                      </EntityLink>{" "}
                      <span className="text-xs text-muted">{r.type === "introduced" ? "intro" : "same threads"}</span>
                    </span>
                    <Strength value={r.props.strength ?? null} />
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
