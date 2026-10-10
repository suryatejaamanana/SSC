"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { AttemptHistoryItem, AttemptHistoryPage, AttemptHistorySummary } from "@/lib/types";
import { formatDateTime, formatScore } from "@/lib/format";
import { useAuth } from "@/lib/auth-context";
import Spinner from "@/components/Spinner";
import ErrorMessage from "@/components/ErrorMessage";
import StatTile from "@/components/StatTile";

const RECENT_LIMIT = 5;

// Landing page after login: Login -> Dashboard -> Select Exam -> ... Built
// entirely from existing endpoints already used elsewhere (history summary,
// history list, exams) - no new backend work for this phase.
export default function DashboardPage() {
  const { user } = useAuth();

  const [summary, setSummary] = useState<AttemptHistorySummary | null>(null);
  const [recent, setRecent] = useState<AttemptHistoryPage | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const [summaryData, recentData] = await Promise.all([
        api.get<AttemptHistorySummary>("/api/v1/attempts/history/summary"),
        api.get<AttemptHistoryPage>("/api/v1/attempts/history", { limit: RECENT_LIMIT, offset: 0 }),
      ]);
      setSummary(summaryData);
      setRecent(recentData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load dashboard");
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (error) return <ErrorMessage message={error} onRetry={load} />;
  if (summary === null || recent === null) return <Spinner label="Loading dashboard..." />;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
          Welcome{user ? `, ${user.name}` : ""}
        </h1>
        <p className="text-sm text-zinc-500">Pick up where you left off, or start something new.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Link
          href="/exams"
          className="rounded-lg border border-zinc-200 bg-white p-4 hover:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-600"
        >
          <p className="font-medium text-zinc-900 dark:text-zinc-50">Previous-Year Papers</p>
          <p className="mt-1 text-sm text-zinc-500">Full paper or section practice by year/shift</p>
        </Link>
        <Link
          href="/practice"
          className="rounded-lg border border-zinc-200 bg-white p-4 hover:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-600"
        >
          <p className="font-medium text-zinc-900 dark:text-zinc-50">Topic Practice</p>
          <p className="mt-1 text-sm text-zinc-500">Practice a subject/topic at your own pace</p>
        </Link>
        <Link
          href="/history"
          className="rounded-lg border border-zinc-200 bg-white p-4 hover:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-600"
        >
          <p className="font-medium text-zinc-900 dark:text-zinc-50">Attempt History</p>
          <p className="mt-1 text-sm text-zinc-500">Every past attempt, with filters</p>
        </Link>
      </div>

      {summary.total_attempts > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Your performance</h2>
          <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile label="Attempts completed" value={summary.total_attempts} />
            <StatTile label="Average score" value={formatScore(summary.average_score)} />
            <StatTile label="Accuracy" value={`${summary.accuracy}%`} />
            <StatTile label="Total questions" value={summary.total_questions} />
          </div>
        </div>
      )}

      <div>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Recent activity</h2>
          {recent.total > RECENT_LIMIT && (
            <Link
              href="/history"
              className="text-sm font-medium text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
            >
              View all &rarr;
            </Link>
          )}
        </div>

        {recent.items.length === 0 ? (
          <p className="mt-2 text-sm text-zinc-500">
            No attempts yet - start a paper or topic practice above to see it here.
          </p>
        ) : (
          <div className="mt-2 flex flex-col gap-2">
            {recent.items.map((item) => (
              <RecentAttemptRow key={item.attempt_id} item={item} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function attemptLabel(item: AttemptHistoryItem): string {
  if (item.attempt_type === "full_paper") {
    return `SSC CGL ${item.exam_year} ${item.exam_tier} Shift ${item.exam_shift}`;
  }
  if (item.attempt_type === "section_practice") {
    return `${item.subject_name ?? "Section practice"} (Shift ${item.exam_shift ?? "?"})`;
  }
  return `${item.subject_name ?? ""}${item.topic_name ? ` / ${item.topic_name}` : ""}`;
}

function attemptTypeLabel(type: AttemptHistoryItem["attempt_type"]): string {
  if (type === "full_paper") return "Full paper";
  if (type === "section_practice") return "Section practice";
  return "Topic practice";
}

function RecentAttemptRow({ item }: { item: AttemptHistoryItem }) {
  const href =
    item.status === "in_progress" ? `/attempts/${item.attempt_id}` : `/attempts/${item.attempt_id}/result`;

  return (
    <Link
      href={href}
      className="flex items-center justify-between rounded-lg border border-zinc-200 bg-white p-3 hover:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-600"
    >
      <div>
        <p className="font-medium text-zinc-900 dark:text-zinc-50">{attemptLabel(item)}</p>
        <p className="text-xs text-zinc-500">
          {attemptTypeLabel(item.attempt_type)} &middot; {item.status} &middot;{" "}
          {formatDateTime(item.started_at)}
        </p>
      </div>
      <p className="font-semibold text-zinc-900 dark:text-zinc-50">
        {item.score !== null ? formatScore(item.score) : item.status === "in_progress" ? "Resume" : "-"}
      </p>
    </Link>
  );
}
