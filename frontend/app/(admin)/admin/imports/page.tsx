"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { ExamTier, ImportBatchSummary } from "@/lib/types";
import { formatDateTime } from "@/lib/format";
import Spinner from "@/components/Spinner";
import ErrorMessage from "@/components/ErrorMessage";
import EmptyState from "@/components/EmptyState";

export default function ImportsPage() {
  const [batches, setBatches] = useState<ImportBatchSummary[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [tier, setTier] = useState<ExamTier>("Tier 1");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  async function load() {
    setLoadError(null);
    setBatches(null);
    try {
      setBatches(await api.get<ImportBatchSummary[]>("/api/v1/admin/imports"));
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Failed to load import batches");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setUploadError(null);
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("year", year);
      formData.append("tier", tier);
      formData.append("file", file);
      const batch = await api.postForm<ImportBatchSummary>("/api/v1/admin/imports", formData);
      setFile(null);
      await load();
      if (batch.status === "failed") {
        setUploadError(batch.error_log ?? "Import failed - see the batch list below for details.");
      }
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : "Failed to upload PDF");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">PDF Imports</h1>
      <p className="text-sm text-zinc-500">
        Upload a previous-year response-sheet PDF. Questions, options, section and the correct
        answer (detected from the PDF&apos;s own green/red marking - never the candidate&apos;s
        chosen option) are extracted and published automatically, so students can start practicing
        right away. A question only needs your attention here if it couldn&apos;t be auto-published
        (shown below after upload).
      </p>

      <form
        onSubmit={handleUpload}
        className="flex flex-col gap-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900 sm:flex-row sm:items-end"
      >
        <Field label="Year">
          <input
            type="number"
            required
            value={year}
            onChange={(e) => setYear(e.target.value)}
            className="w-24 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </Field>
        <Field label="Tier">
          <select
            value={tier}
            onChange={(e) => setTier(e.target.value as ExamTier)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          >
            <option value="Tier 1">Tier 1</option>
            <option value="Tier 2">Tier 2</option>
          </select>
        </Field>
        <Field label="PDF file">
          <input
            type="file"
            accept="application/pdf"
            required
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-sm"
          />
        </Field>
        <button
          type="submit"
          disabled={uploading || !file}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {uploading ? "Uploading..." : "Upload"}
        </button>
      </form>

      {uploadError && <ErrorMessage message={uploadError} />}

      {loadError && <ErrorMessage message={loadError} onRetry={load} />}
      {!loadError && batches === null && <Spinner label="Loading import batches..." />}
      {batches !== null && batches.length === 0 && (
        <EmptyState title="No imports yet" description="Upload a PDF above to get started." />
      )}

      {batches !== null && batches.length > 0 && (
        <div className="flex flex-col gap-2">
          {batches.map((batch) => (
            <Link
              key={batch.id}
              href={`/admin/imports/${batch.id}`}
              className="flex items-center justify-between rounded-lg border border-zinc-200 bg-white p-3 hover:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-600"
            >
              <div>
                <p className="font-medium text-zinc-900 dark:text-zinc-50">{batch.filename}</p>
                <p className="text-sm text-zinc-500">
                  {batch.question_count} questions &middot; {batch.pending_review_count} pending
                  review &middot; {batch.published_count} published &middot; uploaded{" "}
                  {formatDateTime(batch.created_at)}
                </p>
              </div>
              <StatusBadge status={batch.status} />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: ImportBatchSummary["status"] }) {
  const styles: Record<ImportBatchSummary["status"], string> = {
    processing: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
    pending_review: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
    published: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
    failed: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${styles[status]}`}>
      {status.replace("_", " ")}
    </span>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
      {label}
      <div className="mt-1">{children}</div>
    </label>
  );
}
