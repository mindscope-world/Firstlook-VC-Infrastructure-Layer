"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { date } from "@/lib/format";
import { Badge, Button, Empty, EntityLink } from "@/components/ui";

export interface DocumentRow {
  id: string;
  filename: string;
  format: string | null;
  origin: string;
  status: string;
  error: string | null;
  page_count: number | null;
  ocr_pages: number;
  warnings: string[];
  created_at: string;
  company: { id: string; name: string } | null;
  uploaded_by: string | null;
  fact_sheet: { id: string; status: string; coverage: number; company_name: string | null } | null;
}

const STATUS_TONE: Record<string, "good" | "warn" | "bad" | "neutral" | "info"> = {
  parsed: "good",
  pending: "info",
  failed: "bad",
  unsupported: "warn",
};
const SHEET_TONE: Record<string, "good" | "warn" | "bad" | "neutral" | "brand"> = {
  proposed: "brand",
  accepted: "good",
  rejected: "bad",
  superseded: "neutral",
};

export function DocumentList({ docs }: { docs: DocumentRow[] }) {
  if (docs.length === 0) return <Empty>No documents yet.</Empty>;
  return (
    <ul className="divide-y divide-line text-sm">
      {docs.map((d) => (
        <li key={d.id} className="flex flex-wrap items-center gap-2 py-2.5">
          <Link href={`/documents/${d.id}`} className="min-w-0 flex-1 truncate font-medium hover:underline">
            {d.filename}
          </Link>
          {d.company && (
            <span className="text-xs">
              <EntityLink type="company" id={d.company.id}>
                {d.company.name}
              </EntityLink>
            </span>
          )}
          <Badge tone={STATUS_TONE[d.status] ?? "neutral"}>
            {d.status === "parsed" ? `${d.page_count} ${d.format === "xlsx" ? "sheets" : "pages"}` : d.status}
          </Badge>
          {d.fact_sheet && <Badge tone={SHEET_TONE[d.fact_sheet.status] ?? "neutral"}>fact sheet {d.fact_sheet.status}</Badge>}
          <span className="w-24 text-right text-xs text-muted">{date(d.created_at)}</span>
        </li>
      ))}
    </ul>
  );
}

export function UploadDocument({ companyId, onUploaded }: { companyId?: string; onUploaded: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function upload() {
    if (!file) return;
    const form = new FormData();
    form.set("file", file);
    if (companyId) form.set("company_id", companyId);
    setBusy(true);
    try {
      const r = await api<{ created: boolean; filename: string }>("/ingest/documents", { method: "POST", body: form });
      setMessage(r.created ? `${r.filename} uploaded. A fact sheet will appear once it is parsed.` : "That file is already here.");
      onUploaded();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <input type="file" accept=".pdf,.pptx,.xlsx,.png,.jpg,.jpeg,.txt,.md,.csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <Button onClick={upload} disabled={!file || busy}>
          {busy ? "Uploading…" : "Upload"}
        </Button>
      </div>
      {message && <p className="mt-2 text-sm text-muted">{message}</p>}
    </div>
  );
}
