"use client";

import Link from "next/link";
import { use, useState } from "react";
import { api, useApi } from "@/lib/api";
import { date, usd } from "@/lib/format";
import { Badge, Button, Card, CitedText, Empty, EntityLink, Loading, PageHeader } from "@/components/ui";

interface Citation {
  page: number;
  quote: string;
  start: number;
  end: number;
}
interface Field {
  value: string | number;
  confidence: number;
  citation: Citation;
  number_in_quote?: boolean;
}
interface Metric extends Field {
  metric: string;
  label: string;
  unit: string;
  currency: string;
  period: string;
}
interface Person {
  name: string;
  role: string;
  background: string;
  confidence: number;
  citation: Citation;
}
interface FactSheet {
  id: string;
  status: string;
  coverage: number;
  dropped_uncited: number;
  model: string;
  created_at: string;
  fields: {
    company: Record<string, Field | null>;
    round: Record<string, Field | null>;
    team: Person[];
    metrics: Metric[];
  };
}
interface Page {
  page_no: number;
  kind: string;
  title: string | null;
  text: string;
  ocr: boolean;
}
interface DocumentDetail {
  id: string;
  filename: string;
  format: string | null;
  origin: string;
  status: string;
  error: string | null;
  warnings: string[];
  ocr_pages: number;
  created_at: string;
  interaction_id: string | null;
  uploaded_by: string | null;
  company: { id: string; name: string } | null;
  pages: Page[];
  fact_sheets: FactSheet[];
}

const COMPANY_LABELS: Record<string, string> = {
  name: "Name",
  one_liner: "What it does",
  sector: "Sector",
  hq_country: "Headquarters",
  founded_year: "Founded",
  headcount: "Headcount",
};
const ROUND_LABELS: Record<string, string> = {
  stage: "Stage",
  instrument: "Instrument",
  raise_usd: "Raising",
  pre_money_usd: "Pre-money",
  post_money_usd: "Post-money",
  committed_usd: "Committed",
  use_of_funds: "Use of funds",
};

function display(key: string, f: Field | Metric): string {
  if (typeof f.value !== "number") return f.value;
  const unit = "unit" in f ? f.unit : key.endsWith("_usd") ? "usd" : "count";
  if (unit === "usd") return usd(f.value);
  if (unit === "percent") return `${f.value}%`;
  if (unit === "months") return `${f.value} months`;
  if (unit === "local_currency") return `${f.value.toLocaleString()} ${"currency" in f ? f.currency : ""}`;
  return f.value.toLocaleString();
}

/** A value with its confidence and a link to the cited passage. Numbers that
 * can't be read off their quote are highlighted for a human to check. */
function Value({ label, f, k, onCite }: { label: string; f: Field | null; k: string; onCite: (c: Citation) => void }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5">
      <dt className="shrink-0 text-muted">{label}</dt>
      {f ? (
        <dd className="text-right">
          <span className={f.number_in_quote === false ? "rounded bg-[#fdf0dc] px-1" : ""} title={f.number_in_quote === false ? "This number could not be found in its quote: check it" : undefined}>
            {display(k, f)}
          </span>
          <button onClick={() => onCite(f.citation)} className="ml-2 text-xs text-brand-deep hover:underline">
            p.{f.citation.page}
          </button>
          {f.confidence < 0.6 && <span className="ml-1.5 text-xs text-[#9a5b12]">low confidence</span>}
        </dd>
      ) : (
        <dd className="text-faint">not stated</dd>
      )}
    </div>
  );
}

function FactSheetView({ sheet, onCite, onDecided }: { sheet: FactSheet; onCite: (c: Citation) => void; onDecided: () => void }) {
  const [error, setError] = useState<string | null>(null);
  async function decide(decision: "accepted" | "rejected") {
    try {
      await api(`/fact-sheets/${sheet.id}`, { method: "POST", json: { decision } });
      onDecided();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }
  const f = sheet.fields;
  return (
    <Card
      title={
        <span className="flex items-center gap-2">
          Fact sheet <Badge tone={sheet.status === "accepted" ? "good" : sheet.status === "proposed" ? "brand" : "neutral"}>{sheet.status}</Badge>
        </span>
      }
      actions={
        sheet.status === "proposed" ? (
          <span className="flex gap-2">
            <Button variant="secondary" onClick={() => decide("accepted")}>
              Accept
            </Button>
            <Button variant="danger" onClick={() => decide("rejected")}>
              Reject
            </Button>
          </span>
        ) : undefined
      }
    >
      {error && <p className="mb-3 text-sm text-[#a33a2c]">{error}</p>}
      <p className="mb-4 text-xs text-muted">
        {Math.round(sheet.coverage * 100)}% of fields found · {sheet.dropped_uncited} uncited value(s) discarded · {sheet.model}
      </p>
      <div className="grid gap-6 md:grid-cols-2">
        <section>
          <h3 className="mb-1 text-sm font-semibold">Company</h3>
          <dl className="divide-y divide-line text-sm">
            {Object.entries(COMPANY_LABELS).map(([k, label]) => (
              <Value key={k} k={k} label={label} f={f.company[k] ?? null} onCite={onCite} />
            ))}
          </dl>
        </section>
        <section>
          <h3 className="mb-1 text-sm font-semibold">Round</h3>
          <dl className="divide-y divide-line text-sm">
            {Object.entries(ROUND_LABELS).map(([k, label]) => (
              <Value key={k} k={k} label={label} f={f.round[k] ?? null} onCite={onCite} />
            ))}
          </dl>
        </section>
        <section>
          <h3 className="mb-1 text-sm font-semibold">Traction and unit economics</h3>
          {f.metrics.length === 0 ? (
            <Empty>No figures stated.</Empty>
          ) : (
            <dl className="divide-y divide-line text-sm">
              {f.metrics.map((m, i) => (
                <Value key={i} k={m.metric} label={m.period ? `${m.label} (${m.period})` : m.label} f={m} onCite={onCite} />
              ))}
            </dl>
          )}
        </section>
        <section>
          <h3 className="mb-1 text-sm font-semibold">Team</h3>
          {f.team.length === 0 ? (
            <Empty>No one named.</Empty>
          ) : (
            <ul className="space-y-2 text-sm">
              {f.team.map((p) => (
                <li key={p.name}>
                  <span className="font-medium">{p.name}</span>
                  {p.role && <span className="text-muted">, {p.role}</span>}
                  <button onClick={() => onCite(p.citation)} className="ml-2 text-xs text-brand-deep hover:underline">
                    p.{p.citation.page}
                  </button>
                  {p.background && <p className="text-xs text-muted">{p.background}</p>}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </Card>
  );
}

export default function DocumentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, error, reload } = useApi<DocumentDetail>(`/documents/${id}`);
  const [cite, setCite] = useState<Citation | null>(null);
  if (!data) return <Loading error={error} />;

  const sheet = data.fact_sheets[0];
  const page = cite ? data.pages.find((p) => p.page_no === cite.page) : data.pages[0];
  const pageLabel = data.format === "xlsx" ? "Sheet" : data.format === "pptx" ? "Slide" : "Page";

  return (
    <>
      <PageHeader
        title={data.filename}
        subtitle={
          <>
            {data.company && (
              <>
                <EntityLink type="company" id={data.company.id}>
                  {data.company.name}
                </EntityLink>{" "}
                ·{" "}
              </>
            )}
            {data.origin === "email_attachment" && data.interaction_id ? (
              <Link href={`/interactions/${data.interaction_id}`} className="hover:underline">
                email attachment
              </Link>
            ) : (
              `uploaded by ${data.uploaded_by ?? "someone"}`
            )}{" "}
            · {date(data.created_at)}
          </>
        }
        actions={
          <a href={`/api/ingest/documents/${data.id}/file`} className="text-sm font-medium text-brand-deep hover:underline">
            Download original
          </a>
        }
      />
      {data.status !== "parsed" && (
        <p className="mb-4 rounded-2xl bg-[#fdf0dc] px-4 py-2.5 text-sm text-[#9a5b12]">
          {data.status === "pending" ? "Still being read. Refresh in a moment." : `Could not be read: ${data.error ?? data.status}`}
        </p>
      )}
      {data.warnings.length > 0 && (
        <ul className="mb-4 space-y-1 rounded-2xl bg-[#fdf0dc] px-4 py-2.5 text-sm text-[#9a5b12]">
          {data.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
      <div className="space-y-6">
        {sheet ? (
          <FactSheetView sheet={sheet} onCite={setCite} onDecided={reload} />
        ) : (
          data.status === "parsed" && <Card title="Fact sheet"><Empty>Being extracted. Refresh in a moment.</Empty></Card>
        )}
        {data.pages.length > 0 && (
          <Card
            title={`${pageLabel} ${page?.page_no ?? ""}${page?.title ? `: ${page.title}` : ""}${page?.ocr ? " (OCR)" : ""}`}
            actions={
              <span className="flex flex-wrap gap-1">
                {data.pages.map((p) => (
                  <button
                    key={p.page_no}
                    onClick={() => setCite({ page: p.page_no, quote: "", start: 0, end: 0 })}
                    className={`h-7 min-w-7 rounded-full px-2 text-xs ${p.page_no === page?.page_no ? "bg-ink text-white" : "bg-[#f1eeea] text-muted hover:text-ink"}`}
                  >
                    {p.page_no}
                  </button>
                ))}
              </span>
            }
          >
            {page && <CitedText text={page.text} spans={cite && cite.end > cite.start && cite.page === page.page_no ? [cite] : []} />}
          </Card>
        )}
      </div>
    </>
  );
}
