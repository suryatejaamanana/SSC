"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { Exam } from "@/lib/types";
import Spinner from "@/components/Spinner";
import ErrorMessage from "@/components/ErrorMessage";
import EmptyState from "@/components/EmptyState";

// Student workflow: Select Year -> Select Exam Day -> Select Shift. Exam
// granularity on the backend is already one row per shift (year+tier+
// shift), so this page just groups the flat list the API already returns
// into that drill-down instead of needing new endpoints.
export default function ExamsPage() {
  const [exams, setExams] = useState<Exam[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openYear, setOpenYear] = useState<number | null>(null);
  const [openDate, setOpenDate] = useState<string | null>(null);

  async function load() {
    setError(null);
    setExams(null);
    try {
      const data = await api.get<Exam[]>("/api/v1/exams");
      setExams(data);
      if (data.length > 0) setOpenYear(data[0].year);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load exams");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const byYear = useMemo(() => {
    const map = new Map<number, Exam[]>();
    for (const exam of exams ?? []) {
      const list = map.get(exam.year) ?? [];
      list.push(exam);
      map.set(exam.year, list);
    }
    return [...map.entries()].sort((a, b) => b[0] - a[0]);
  }, [exams]);

  if (error) return <ErrorMessage message={error} onRetry={load} />;
  if (exams === null) return <Spinner label="Loading exams..." />;

  if (exams.length === 0) {
    return <EmptyState title="No exams available yet" description="Check back once papers have been published." />;
  }

  return (
    <div className="flex flex-col gap-3">
      <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Previous-Year Papers</h1>
      <p className="text-sm text-zinc-500">Select a year, then an exam day, then a shift.</p>

      {byYear.map(([year, yearExams]) => {
        const isYearOpen = openYear === year;
        const byDate = groupByDate(yearExams);
        return (
          <div key={year} className="rounded-lg border border-zinc-200 dark:border-zinc-800">
            <button
              type="button"
              onClick={() => setOpenYear(isYearOpen ? null : year)}
              className="flex w-full items-center justify-between p-3 text-left"
            >
              <span className="font-medium text-zinc-900 dark:text-zinc-50">{year}</span>
              <span className="text-sm text-zinc-500">{yearExams.length} shift(s) &middot; {isYearOpen ? "hide" : "show"}</span>
            </button>

            {isYearOpen && (
              <div className="flex flex-col gap-2 border-t border-zinc-200 p-3 dark:border-zinc-800">
                {byDate.map(([date, dateExams]) => {
                  const dateKey = `${year}-${date}`;
                  const isDateOpen = openDate === dateKey;
                  return (
                    <div key={dateKey} className="rounded-md border border-zinc-200 dark:border-zinc-800">
                      <button
                        type="button"
                        onClick={() => setOpenDate(isDateOpen ? null : dateKey)}
                        className="flex w-full items-center justify-between p-2.5 text-left text-sm"
                      >
                        <span className="font-medium text-zinc-800 dark:text-zinc-200">
                          {date === "unknown" ? "Exam day not set" : date}
                        </span>
                        <span className="text-zinc-500">{dateExams.length} shift(s)</span>
                      </button>
                      {isDateOpen && (
                        <div className="flex flex-col gap-2 border-t border-zinc-200 p-2.5 dark:border-zinc-800">
                          {dateExams
                            .sort((a, b) => a.shift - b.shift)
                            .map((exam) => (
                              <Link
                                key={exam.id}
                                href={`/exams/${exam.id}`}
                                className="flex items-center justify-between rounded-md border border-zinc-200 bg-white p-3 hover:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-600"
                              >
                                <div>
                                  <p className="font-medium text-zinc-900 dark:text-zinc-50">
                                    Shift {exam.shift} &middot; {exam.tier}
                                  </p>
                                  <p className="text-sm text-zinc-500">
                                    {exam.total_questions} questions &middot; {exam.duration_minutes} min &middot;{" "}
                                    {exam.total_marks} marks
                                  </p>
                                </div>
                                <span className="text-sm font-medium text-zinc-600 dark:text-zinc-400">
                                  Choose &rarr;
                                </span>
                              </Link>
                            ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function groupByDate(exams: Exam[]): [string, Exam[]][] {
  const map = new Map<string, Exam[]>();
  for (const exam of exams) {
    const key = exam.exam_date ?? "unknown";
    const list = map.get(key) ?? [];
    list.push(exam);
    map.set(key, list);
  }
  return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}
