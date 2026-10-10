"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { AttemptHistorySummary, SectionPerformance } from "@/lib/types";
import { formatDuration, formatScore } from "@/lib/format";
import Spinner from "@/components/Spinner";
import ErrorMessage from "@/components/ErrorMessage";
import StatTile from "@/components/StatTile";

export default function HistorySummaryPage() {
  const [summary, setSummary] = useState<AttemptHistorySummary | null>(null);
  const [sections, setSections] = useState<SectionPerformance[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const [summaryData, sectionsData] = await Promise.all([
        api.get<AttemptHistorySummary>("/api/v1/attempts/history/summary"),
        api.get<SectionPerformance[]>("/api/v1/attempts/history/section-performance"),
      ]);
      setSummary(summaryData);
      setSections(sectionsData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load summary");
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (error) return <ErrorMessage message={error} onRetry={load} />;
  if (!summary || !sections) return <Spinner label="Loading summary..." />;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Performance Summary</h1>
        <Link
          href="/history"
          className="text-sm font-medium text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
        >
          &larr; Back to history
        </Link>
      </div>

      {summary.total_attempts === 0 ? (
        <p className="text-sm text-zinc-500">
          No completed attempts yet - stats will show up here once you submit your first paper or
          practice session.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile label="Attempts completed" value={summary.total_attempts} />
            <StatTile label="Average score" value={formatScore(summary.average_score)} />
            <StatTile label="Accuracy" value={`${summary.accuracy}%`} />
            <StatTile label="Time taken" value={formatDuration(summary.total_time_seconds)} />
            <StatTile label="Total questions" value={summary.total_questions} />
            <StatTile label="Correct" value={summary.total_correct} />
            <StatTile label="Wrong" value={summary.total_wrong} />
            <StatTile label="Unanswered" value={summary.total_unanswered} />
          </div>

          <div>
            <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
              Section-wise performance
            </h2>
            {sections.length === 0 ? (
              <p className="mt-2 text-sm text-zinc-500">
                No section-attributed questions answered yet.
              </p>
            ) : (
              <div className="mt-2 overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
                <table className="w-full text-left text-sm">
                  <thead className="bg-zinc-50 text-xs uppercase text-zinc-500 dark:bg-zinc-800/50">
                    <tr>
                      <th className="px-3 py-2 font-medium">Section</th>
                      <th className="px-3 py-2 font-medium">Questions</th>
                      <th className="px-3 py-2 font-medium">Correct</th>
                      <th className="px-3 py-2 font-medium">Wrong</th>
                      <th className="px-3 py-2 font-medium">Unanswered</th>
                      <th className="px-3 py-2 font-medium">Accuracy</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                    {sections.map((s) => (
                      <tr key={s.subject_id} className="bg-white dark:bg-zinc-900">
                        <td className="px-3 py-2 font-medium text-zinc-900 dark:text-zinc-50">
                          {s.subject_name}
                        </td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{s.total_questions}</td>
                        <td className="px-3 py-2 text-emerald-700 dark:text-emerald-400">
                          {s.correct_count}
                        </td>
                        <td className="px-3 py-2 text-red-700 dark:text-red-400">{s.wrong_count}</td>
                        <td className="px-3 py-2 text-zinc-500">{s.unanswered_count}</td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{s.accuracy}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
