"use client";

import { useState } from "react";
import { useApi } from "@/lib/api";
import { relative } from "@/lib/format";
import { Badge, Card, EntityLink, Loading, PageHeader, Strength } from "@/components/ui";

interface Person {
  id: string;
  full_name: string;
  primary_email: string | null;
  title: string | null;
  is_internal: boolean;
  company_id: string | null;
  company: string | null;
  strength: number | null;
  last_interaction_at: string | null;
}

export default function PeoplePage() {
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const { data, error } = useApi<Person[]>(`/people?limit=200${search ? `&q=${encodeURIComponent(search)}` : ""}`);
  return (
    <>
      <PageHeader
        title="People"
        subtitle="Everyone your team has interacted with, ranked by relationship strength."
        actions={
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setSearch(q);
            }}
          >
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, email or company" className="w-64 rounded-full border border-line bg-white px-4 py-2 text-sm outline-none focus:border-brand" />
          </form>
        }
      />
      {!data ? (
        <Loading error={error} />
      ) : (
        <Card>
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted">
              <tr>
                <th className="pb-2 font-medium">Name</th>
                <th className="pb-2 font-medium">Company</th>
                <th className="pb-2 font-medium">Strongest tie</th>
                <th className="pb-2 font-medium">Last contact</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.map((p) => (
                <tr key={p.id}>
                  <td className="py-2">
                    <EntityLink type="person" id={p.id}>
                      {p.full_name}
                    </EntityLink>{" "}
                    {p.is_internal && <Badge tone="brand">team</Badge>}
                    <p className="text-xs text-muted">{p.title ?? p.primary_email}</p>
                  </td>
                  <td className="py-2">
                    <EntityLink type="company" id={p.company_id}>
                      {p.company ?? "—"}
                    </EntityLink>
                  </td>
                  <td className="py-2">{p.is_internal ? "" : <Strength value={p.strength} />}</td>
                  <td className="py-2 text-muted">{relative(p.last_interaction_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}
