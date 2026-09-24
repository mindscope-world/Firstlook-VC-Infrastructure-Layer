"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { useApi } from "@/lib/api";
import { Badge, Card, Empty, EntityLink, Loading, PageHeader } from "@/components/ui";

function Results() {
  const q = useSearchParams().get("q") ?? "";
  const { data, error } = useApi<{ id: string; type: string; name: string }[]>(q ? `/search?q=${encodeURIComponent(q)}` : null);
  return (
    <>
      <PageHeader title={`Search: ${q}`} />
      {!data ? (
        <Loading error={error} />
      ) : (
        <Card>
          {data.length === 0 ? (
            <Empty>No matches.</Empty>
          ) : (
            <ul className="divide-y divide-line text-sm">
              {data.map((r) => (
                <li key={r.id} className="flex items-center gap-2 py-2">
                  <Badge>{r.type}</Badge>
                  {r.type === "deal" ? r.name : <EntityLink type={r.type as "person" | "company"} id={r.id}>{r.name}</EntityLink>}
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<Loading />}>
      <Results />
    </Suspense>
  );
}
