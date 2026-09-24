"use client";

import Link from "next/link";
import { use } from "react";
import { useApi } from "@/lib/api";
import { date } from "@/lib/format";
import { Badge, Card, CitedText, EntityLink, Loading, PageHeader } from "@/components/ui";

interface Detail {
  id: string;
  kind: string;
  subject: string | null;
  occurred_at: string;
  direction: string;
  visibility: string;
  body_text: string | null;
  signature: string | null;
  participants: { role: string; email: string | null; display_name: string | null; person_id: string | null; full_name: string | null; title: string | null; is_internal: boolean }[];
  attachments: { id: string; filename: string; content_type: string; size_bytes: number }[];
  extractions: { id: string; kind: string; payload: Record<string, unknown>; citations: { quote: string; start: number; end: number }[]; status: string; model: string }[];
  thread: { id: string; subject: string; occurred_at: string }[];
}

export default function InteractionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, error } = useApi<Detail>(`/interactions/${id}`);
  if (!data) return <Loading error={error} />;
  const spans = data.extractions.flatMap((x) => x.citations);

  return (
    <>
      <PageHeader
        title={data.subject || "(no subject)"}
        subtitle={
          <span className="flex flex-wrap items-center gap-2">
            <Badge tone="info">{data.kind}</Badge> {data.direction && <Badge>{data.direction}</Badge>}
            {data.visibility === "private" && <Badge tone="warn">private</Badge>}
            {date(data.occurred_at)}
          </span>
        }
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Content" actions={<span className="text-xs text-muted">quoted history and signature removed; highlights are citations</span>}>
            {data.body_text ? <CitedText text={data.body_text} spans={spans} /> : <p className="text-sm text-muted">No text.</p>}
            {data.signature && <pre className="mt-4 whitespace-pre-wrap border-t border-line pt-3 text-xs text-muted">{data.signature}</pre>}
          </Card>
          {data.extractions.length > 0 && (
            <Card title="Found in this interaction">
              <ul className="space-y-3 text-sm">
                {data.extractions.map((x) => (
                  <li key={x.id} className="flex items-start gap-2">
                    <Badge tone={x.status === "accepted" ? "good" : x.status === "rejected" ? "bad" : "neutral"}>{x.kind.replace("_", " ")}</Badge>
                    <div>
                      <a href={`#cite-${x.citations[0]?.start}`} className="hover:underline">
                        “{x.citations[0]?.quote}”
                      </a>
                      <p className="text-xs text-muted">
                        {x.status} · {x.model}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
        <div className="space-y-6">
          <Card title="Participants">
            <ul className="space-y-2 text-sm">
              {data.participants.map((p, i) => (
                <li key={i}>
                  <span className="mr-1 text-xs uppercase text-muted">{p.role}</span>
                  <EntityLink type="person" id={p.person_id}>
                    {p.full_name ?? p.display_name ?? p.email}
                  </EntityLink>
                  {p.is_internal && <Badge tone="brand">team</Badge>}
                  <p className="text-xs text-muted">{p.email}</p>
                </li>
              ))}
            </ul>
          </Card>
          {data.attachments.length > 0 && (
            <Card title="Attachments">
              <ul className="space-y-1 text-sm">
                {data.attachments.map((a) => (
                  <li key={a.id}>
                    {a.filename} <span className="text-xs text-muted">({Math.ceil(a.size_bytes / 1024)} KB)</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          {data.thread.length > 1 && (
            <Card title="Thread">
              <ul className="space-y-1 text-sm">
                {data.thread.map((t) => (
                  <li key={t.id} className={t.id === data.id ? "font-medium" : ""}>
                    <Link href={`/interactions/${t.id}`} className="hover:underline">
                      {date(t.occurred_at)}
                    </Link>
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
