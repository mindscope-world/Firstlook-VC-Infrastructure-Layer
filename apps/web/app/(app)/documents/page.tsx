"use client";

import { useApi } from "@/lib/api";
import { Card, Loading, PageHeader } from "@/components/ui";
import { DocumentList, UploadDocument, type DocumentRow } from "@/components/documents";

export default function DocumentsPage() {
  const { data, error, reload } = useApi<DocumentRow[]>("/documents");
  return (
    <>
      <PageHeader
        title="Documents"
        subtitle="Decks, financial models and memos, from uploads and email attachments. Each one gets a fact sheet with every figure cited to its page."
      />
      <div className="space-y-6">
        <Card title="Upload">
          <p className="mb-3 text-sm text-muted">PDF, PowerPoint (.pptx), Excel (.xlsx) or images, up to 50 MB. Scanned pages are read with OCR.</p>
          <UploadDocument onUploaded={reload} />
        </Card>
        <Card title="All documents">{data ? <DocumentList docs={data} /> : <Loading error={error} />}</Card>
      </div>
    </>
  );
}
