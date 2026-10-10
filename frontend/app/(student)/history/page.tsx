"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { AttemptHistoryItem, AttemptHistoryPage, AttemptStatus, AttemptType } from "@/lib/types";
import { formatDateTime, formatDuration, formatScore } from "@/lib/format";
import Spinner from "@/components/Spinner";
import ErrorMessage from "@/components/ErrorMessage";
import EmptyState from "@/components/EmptyState";

const PAGE_SIZE = 10;

export default function HistoryPage() {
  const [page, setPage] = useState<AttemptHistoryPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [attemptType, setAttemptType] = useState<AttemptType | "">("");
  const [status, setStatus] = useState<AttemptStatus | "">("");

  async function load() {
    setError(null);
    try {
      const data = await api.get<AttemptHistoryPage>("/api/v1/attempts/history", {
        limit: PAGE_SIZE,
        offset,
        attempt_type: attemptType || undefined,
        status: status || undefined,
      });
      setPage(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load history");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offset, attemptType, status]);

  function label(item: AttemptHistoryItem): string {
    if (item.attempt_type === "full_paper") {
      return `SSC CGL ${item.exam_year} ${item.exam_tier} Shift ${item.exam_shift}`;
    }
    if (item.attempt_type === "section_practice") {
      return `${item.subject_name ?? "Section practice"} (Shift ${item.exam_shift ?? "?"})`;
    }
    return `${item.subject_name ?? ""}${item.topic_name ? ` / ${item.topic_name}` : ""}`;
  }

  function typeLabel(type: AttemptHistoryItem["attempt_type"]): string {
    if (type === "full_paper") return "Full paper";
    if (type === "section_practice") return "Section practice";
    return "Topic practice";
  }

  function timeTaken(item: AttemptHistoryItem): string | null {
    if (!item.submitted_at) return null;
    const seconds = (new Date(item.submitted_at).getTime() - new Date(item.started_at).getTime()) / 1000;
    return formatDuration(seconds);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Attempt History</h1>
        <Link
          href="/history/summary"
          className="text-sm font-medium text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
        >
          View performance summary &rarr;
        </Link>
      </div>

      <div className="flex gap-3">
        <select
          aria-label="Filter by attempt type"
          value={attemptType}
          onChange={(e) => {
            setOffset(0);
            setAttemptType(e.target.value as AttemptType | "");
          }}
          className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800"
        >
          <option value="">All types</option>
          <option value="full_paper">Full paper</option>
          <option value="section_practice">Section practice</option>
          <option value="topic_practice">Topic practice</option>
        </select>

        <select
          aria-label="Filter by status"
          value={status}
          onChange={(e) => {
            setOffset(0);
            setStatus(e.target.value as AttemptStatus | "");
          }}
          className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800"
        >
          <option value="">All statuses</option>
          <option value="in_progress">In progress</option>
          <option value="submitted">Submitted</option>
          <option value="expired">Expired</option>
        </select>
      </div>

      {error && <ErrorMessage message={error} onRetry={load} />}
      {!error && page === null && <Spinner label="Loading history..." />}

      {page !== null && page.items.length === 0 && (
        <EmptyState title="No attempts yet" description="Start a paper or topic practice to see it here." />
      )}

      {page !== null && page.items.length > 0 && (
        <>
          <div className="flex flex-col gap-2">
            {page.items.map((item) => (
              <div
                key={item.attempt_id}
                className="flex items-center justify-between gap-3 rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900"
              >
                <div className="min-w-0">
                  <p className="break-words font-medium text-zinc-900 dark:text-zinc-50">{label(item)}</p>
                  <p className="text-xs text-zinc-500">
                    {typeLabel(item.attempt_type)} &middot; {item.status} &middot;{" "}
                    {formatDateTime(item.started_at)}
                    {timeTaken(item) && <> &middot; {timeTaken(item)}</>}
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="font-semibold text-zinc-900 dark:text-zinc-50">
                    {item.score !== null ? formatScore(item.score) : "-"}
                  </p>
                  {item.status !== "in_progress" && (
                    <Link
                      href={`/attempts/${item.attempt_id}/result`}
                      className="text-xs font-medium text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
                    >
                      View result
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between text-sm text-zinc-500">
            <button
              type="button"
              disabled={offset === 0}
              onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
              className="rounded-md border border-zinc-300 px-3 py-1 font-medium disabled:opacity-40 dark:border-zinc-700"
            >
              Previous
            </button>
            <span>
              {offset + 1}-{Math.min(offset + PAGE_SIZE, page.total)} of {page.total}
            </span>
            <button
              type="button"
              disabled={offset + PAGE_SIZE >= page.total}
              onClick={() => setOffset((o) => o + PAGE_SIZE)}
              className="rounded-md border border-zinc-300 px-3 py-1 font-medium disabled:opacity-40 dark:border-zinc-700"
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}
