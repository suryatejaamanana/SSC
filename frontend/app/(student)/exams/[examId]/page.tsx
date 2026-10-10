"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { Attempt, Exam, Subject } from "@/lib/types";
import { examTitle } from "@/lib/format";
import Spinner from "@/components/Spinner";
import ErrorMessage from "@/components/ErrorMessage";

type Mode = "full" | "section";

export default function ExamDetailPage({ params }: { params: Promise<{ examId: string }> }) {
  const { examId } = use(params);
  const router = useRouter();
  const [exam, setExam] = useState<Exam | null>(null);
  const [subjects, setSubjects] = useState<Subject[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [mode, setMode] = useState<Mode>("full");
  const [subjectId, setSubjectId] = useState<number | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  async function load() {
    setError(null);
    setExam(null);
    try {
      const [examData, subjectsData] = await Promise.all([
        api.get<Exam>(`/api/v1/exams/${examId}`),
        api.get<Subject[]>("/api/v1/subjects"),
      ]);
      setExam(examData);
      setSubjects(subjectsData);
      if (subjectsData.length > 0) setSubjectId(subjectsData[0].id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load exam");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [examId]);

  async function handleStart() {
    setStartError(null);
    setStarting(true);
    try {
      const attempt =
        mode === "full"
          ? await api.post<Attempt>("/api/v1/attempts", { exam_id: Number(examId) })
          : await api.post<Attempt>("/api/v1/attempts/section-practice", {
              exam_id: Number(examId),
              subject_id: subjectId,
            });
      router.push(`/attempts/${attempt.id}`);
    } catch (err) {
      setStartError(err instanceof ApiError ? err.message : "Failed to start attempt");
      setStarting(false);
    }
  }

  if (error) return <ErrorMessage message={error} onRetry={load} />;
  if (exam === null || subjects === null) return <Spinner label="Loading exam..." />;

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">{examTitle(exam)}</h1>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Detail label="Questions" value={exam.total_questions} />
        <Detail label="Duration" value={`${exam.duration_minutes} min`} />
        <Detail label="Total marks" value={exam.total_marks} />
      </div>

      <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">How do you want to practice?</p>
        <div className="mt-2 flex gap-2">
          <button
            type="button"
            onClick={() => setMode("full")}
            className={`rounded-md border px-3 py-1.5 text-sm font-medium ${
              mode === "full"
                ? "border-zinc-900 bg-zinc-900 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900"
                : "border-zinc-300 text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
            }`}
          >
            Full Paper
          </button>
          <button
            type="button"
            onClick={() => setMode("section")}
            disabled={subjects.length === 0}
            className={`rounded-md border px-3 py-1.5 text-sm font-medium disabled:opacity-40 ${
              mode === "section"
                ? "border-zinc-900 bg-zinc-900 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900"
                : "border-zinc-300 text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
            }`}
          >
            Section Practice
          </button>
        </div>

        {mode === "section" && (
          <label className="mt-3 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Section
            <select
              value={subjectId ?? ""}
              onChange={(e) => setSubjectId(Number(e.target.value))}
              className="mt-1 w-full max-w-xs rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
            >
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
        Once you start, a timer begins immediately and is tracked by the server. Closing the tab
        will not pause it.
      </div>

      {startError && <ErrorMessage message={startError} />}

      <button
        type="button"
        onClick={handleStart}
        disabled={starting || (mode === "section" && !subjectId)}
        className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
      >
        {starting ? "Starting..." : mode === "full" ? "Start Full Paper" : "Start Section Practice"}
      </button>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-zinc-200 p-3 dark:border-zinc-800">
      <p className="text-xs uppercase text-zinc-500">{label}</p>
      <p className="text-base font-semibold text-zinc-900 dark:text-zinc-50">{value}</p>
    </div>
  );
}
