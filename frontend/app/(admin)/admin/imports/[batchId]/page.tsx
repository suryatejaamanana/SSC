"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { ImportBatchSummary, Question } from "@/lib/types";
import { formatDateTime, resolveMediaUrl } from "@/lib/format";
import Spinner from "@/components/Spinner";
import ErrorMessage from "@/components/ErrorMessage";
import EmptyState from "@/components/EmptyState";
import StatusBadge from "@/components/StatusBadge";
import StatTile from "@/components/StatTile";

export default function ImportBatchPage({ params }: { params: Promise<{ batchId: string }> }) {
  const { batchId } = use(params);

  const [batch, setBatch] = useState<ImportBatchSummary | null>(null);
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [publishingId, setPublishingId] = useState<number | null>(null);
  const [publishErrorFor, setPublishErrorFor] = useState<{ id: number; message: string } | null>(null);

  async function load() {
    setError(null);
    try {
      const [batchData, questionsData] = await Promise.all([
        api.get<ImportBatchSummary>(`/api/v1/admin/imports/${batchId}`),
        api.get<Question[]>(`/api/v1/admin/imports/${batchId}/questions`),
      ]);
      setBatch(batchData);
      setQuestions(questionsData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load import batch");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchId]);

  async function handlePublish(question: Question) {
    setPublishErrorFor(null);
    setPublishingId(question.id);
    try {
      await api.post<Question>(`/api/v1/admin/questions/${question.id}/publish`);
      await load();
    } catch (err) {
      setPublishErrorFor({
        id: question.id,
        message: err instanceof ApiError ? err.message : "Failed to publish question",
      });
    } finally {
      setPublishingId(null);
    }
  }

  if (error) return <ErrorMessage message={error} onRetry={load} />;
  if (batch === null || questions === null) return <Spinner label="Loading import batch..." />;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">{batch.filename}</h1>
          <p className="text-sm text-zinc-500">Uploaded {formatDateTime(batch.created_at)}</p>
        </div>
        <StatusBadge status={batch.status} />
      </div>

      {batch.status === "failed" && batch.error_log && (
        <ErrorMessage message={batch.error_log} />
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Questions" value={batch.question_count} />
        <StatTile label="Pending review" value={batch.pending_review_count} />
        <StatTile label="Published" value={batch.published_count} />
        <StatTile label="Missing correct answer" value={batch.missing_correct_option_count} />
      </div>

      <p className="text-sm text-zinc-500">
        Subject, correct answer (from the PDF&apos;s own green ✓ / red ✗ marking - never the
        candidate&apos;s chosen option) and publishing all happen automatically; there is no
        per-question approval step. A question only appears here needing action if it couldn&apos;t
        be auto-published - almost always because its correct answer couldn&apos;t be determined
        with confidence.
      </p>

      {batch.missing_correct_option_count > 0 && (
        <ErrorMessage
          message={`${batch.missing_correct_option_count} question(s) could not have a correct answer determined automatically and were left unpublished - fix these manually below.`}
        />
      )}

      {questions.length === 0 && <EmptyState title="No questions in this batch" />}

      {questions.length > 0 && (
        <div className="flex flex-col gap-2">
          {questions.map((q) => (
            <div
              key={q.id}
              className="flex flex-col gap-2 rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <StatusBadge status={q.status} />
                    {q.correct_option === null && (
                      <span className="text-xs font-medium text-amber-700 dark:text-amber-400">
                        correct answer not set
                      </span>
                    )}
                  </div>
                  <p className="mt-1 line-clamp-2 text-sm text-zinc-900 dark:text-zinc-50">
                    {q.question_number ? `${q.question_number}. ` : ""}
                    {q.question_text}
                  </p>
                  {q.question_image_url && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={resolveMediaUrl(q.question_image_url) ?? undefined}
                      alt="Question figure"
                      className="mt-2 max-h-24 max-w-xs"
                    />
                  )}
                </div>
                <div className="flex shrink-0 gap-2">
                  <Link
                    href={`/admin/questions/${q.id}`}
                    className="rounded-md border border-zinc-300 px-3 py-1 text-sm font-medium dark:border-zinc-700"
                  >
                    Review / Edit
                  </Link>
                  {q.status !== "published" && (
                    <button
                      type="button"
                      onClick={() => handlePublish(q)}
                      disabled={publishingId === q.id}
                      className="rounded-md bg-emerald-600 px-3 py-1 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
                    >
                      {publishingId === q.id ? "Publishing..." : "Publish"}
                    </button>
                  )}
                </div>
              </div>
              {publishErrorFor?.id === q.id && (
                <p className="text-sm text-red-700 dark:text-red-400">{publishErrorFor.message}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
