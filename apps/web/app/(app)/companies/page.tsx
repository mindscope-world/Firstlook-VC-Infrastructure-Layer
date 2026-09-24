"use client";

import { useState } from "react";
import { useApi } from "@/lib/api";
import { relative, STAGE_LABEL } from "@/lib/format";
import { Badge, Card, EntityLink, Loading, PageHeader } from "@/components/ui";

interface Company {
  id: string;
  name: string;
  domain: string | null;
  country: string | null;
  people: number;
  deal_stage: string | null;
  last_interaction_at: string | null;
}

export default function CompaniesPage() {
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const { data, error } = useApi<Company[]>(`/companies?limit=200${search ? `&q=${encodeURIComponent(search)}` : ""}`);
  return (
    <>
      <PageHeader
        title="Companies"
        actions={
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setSearch(q);
            }}
          >
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name or domain" className="w-64 rounded-lg border border-line bg-white px-3 py-1.5 text-sm" />
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
                <th className="pb-2 font-medium">Company</th>
                <th className="pb-2 font-medium">Country</th>
                <th className="pb-2 font-medium">People</th>
                <th className="pb-2 font-medium">Deal</th>
                <th className="pb-2 font-medium">Last contact</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.map((c) => (
                <tr key={c.id}>
                  <td className="py-2">
                    <EntityLink type="company" id={c.id}>
                      {c.name}
                    </EntityLink>
                    <p className="text-xs text-muted">{c.domain}</p>
                  </td>
                  <td className="py-2 text-muted">{c.country ?? "—"}</td>
                  <td className="py-2 tabular-nums">{c.people}</td>
                  <td className="py-2">{c.deal_stage ? <Badge tone="good">{STAGE_LABEL[c.deal_stage] ?? c.deal_stage}</Badge> : "—"}</td>
                  <td className="py-2 text-muted">{relative(c.last_interaction_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}
