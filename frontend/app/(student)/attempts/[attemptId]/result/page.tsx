"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { AttemptResult } from "@/lib/types";
import { formatScore } from "@/lib/format";
import Spinner from "@/components/Spinner";
import ErrorMessage from "@/components/ErrorMessage";
import StatTile from "@/components/StatTile";

export default function ResultPage({ params }: { params: Promise<{ attemptId: string }> }) {
  const { attemptId } = use(params);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notSubmitted, setNotSubmitted] = useState(false);

  async function load() {
    setError(null);
    setNotSubmitted(false);
    try {
      const data = await api.get<AttemptResult>(`/api/v1/attempts/${attemptId}/result`);
      setResult(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setNotSubmitted(true);
      } else {
        setError(err instanceof ApiError ? err.message : "Failed to load result");
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
  if (!result) return <Spinner label="Loading result..." />;

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Result</h1>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <StatTile label="Score" value={formatScore(result.score)} />
        <StatTile label="Accuracy" value={`${result.accuracy}%`} />
        <StatTile label="Total questions" value={result.total_questions} />
        <StatTile label="Correct" value={result.correct_count} />
        <StatTile label="Wrong" value={result.wrong_count} />
        <StatTile label="Unanswered" value={result.unanswered_count} />
      </div>

      <Link
        href={`/attempts/${attemptId}/review`}
        className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900"
      >
        Review Answers &amp; Solutions
      </Link>
    </div>
  );
}
