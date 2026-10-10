"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { ReviewItem } from "@/lib/types";
import { resolveMediaUrl } from "@/lib/format";
import Spinner from "@/components/Spinner";
import ErrorMessage from "@/components/ErrorMessage";
import OptionsList from "@/components/OptionsList";

export default function ReviewPage({ params }: { params: Promise<{ attemptId: string }> }) {
  const { attemptId } = use(params);
  const [items, setItems] = useState<ReviewItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notSubmitted, setNotSubmitted] = useState(false);

  async function load() {
    setError(null);
    setNotSubmitted(false);
    try {
      const data = await api.get<ReviewItem[]>(`/api/v1/attempts/${attemptId}/review`);
      setItems(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setNotSubmitted(true);
      } else {
        setError(err instanceof ApiError ? err.message : "Failed to load review");
      }
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attemptId]);

  if (notSubmitted) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-lg border border-zinc-200 p-8 text-center dark:border-zinc-800">
        <p className="text-zinc-700 dark:text-zinc-300">This attempt hasn&apos;t been submitted yet.</p>
        <Link
          href={`/attempts/${attemptId}`}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900"
        >
          Continue attempt
        </Link>
      </div>
    );
  }

  if (error) return <ErrorMessage message={error} onRetry={load} />;
  if (!items) return <Spinner label="Loading review..." />;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Review</h1>
        <Link
          href={`/attempts/${attemptId}/result`}
          className="text-sm font-medium text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
        >
          &larr; Back to result
        </Link>
      </div>

      {items.map((item, index) => (
        <div
          key={item.question_id}
          className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900"
        >
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-zinc-500">Question {index + 1}</p>
            <StatusBadge item={item} />
          </div>

          {item.passage_text && (
            <div className="mt-2 whitespace-pre-wrap rounded-md border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-700 dark:border-zinc-800 dark:bg-zinc-800/50 dark:text-zinc-300">
              {item.passage_text}
            </div>
          )}
          <p className="mt-2 whitespace-pre-wrap text-sm text-zinc-900 dark:text-zinc-50">
            {item.question_text}
          </p>
          {item.question_image_url && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={resolveMediaUrl(item.question_image_url) ?? undefined}
              alt="Question"
              className="mt-3 max-w-full"
            />
          )}

          <div className="mt-4">
            <OptionsList
              options={item.options}
              selected={item.selected_option}
              correctOption={item.correct_option}
            />
          </div>

          {item.solution_text && (
            <div className="mt-4 rounded-md bg-zinc-100 p-3 text-sm text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
              <p className="font-medium text-zinc-900 dark:text-zinc-50">Solution</p>
              <p className="mt-1 whitespace-pre-wrap">{item.solution_text}</p>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function StatusBadge({ item }: { item: ReviewItem }) {
  if (item.is_correct === null) {
    return <span className="text-xs font-medium text-zinc-500">Unanswered</span>;
  }
  return item.is_correct ? (
    <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">Correct</span>
  ) : (
    <span className="text-xs font-medium text-red-600 dark:text-red-400">Wrong</span>
  );
}
