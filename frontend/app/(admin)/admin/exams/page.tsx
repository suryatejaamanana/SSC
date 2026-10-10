"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { Exam, ExamTier } from "@/lib/types";
import { examTitle } from "@/lib/format";
import Spinner from "@/components/Spinner";
import ErrorMessage from "@/components/ErrorMessage";
import EmptyState from "@/components/EmptyState";

interface ExamFormState {
  year: string;
  tier: ExamTier;
  shift: string;
  exam_date: string;
  duration_minutes: string;
  total_questions: string;
  total_marks: string;
  source_pdf_name: string;
}

const EMPTY_FORM: ExamFormState = {
  year: String(new Date().getFullYear()),
  tier: "Tier 1",
  shift: "1",
  exam_date: "",
  duration_minutes: "60",
  total_questions: "100",
  total_marks: "200",
  source_pdf_name: "",
};

export default function ExamsPage() {
  const [exams, setExams] = useState<Exam[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [form, setForm] = useState<ExamFormState>(EMPTY_FORM);
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  async function load() {
    setLoadError(null);
    setExams(null);
    try {
      setExams(await api.get<Exam[]>("/api/v1/admin/exams"));
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Failed to load exams");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreateError(null);
    setCreating(true);
    try {
      await api.post<Exam>("/api/v1/admin/exams", {
        year: Number(form.year),
        tier: form.tier,
        shift: Number(form.shift),
        exam_date: form.exam_date || null,
        duration_minutes: Number(form.duration_minutes),
        total_questions: Number(form.total_questions),
        total_marks: form.total_marks,
        source_pdf_name: form.source_pdf_name || null,
      });
      setForm(EMPTY_FORM);
      await load();
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "Failed to create exam");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Exams</h1>

      <form
        onSubmit={handleCreate}
        className="grid grid-cols-2 gap-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900 sm:grid-cols-4"
      >
        {createError && <div className="col-span-full"><ErrorMessage message={createError} /></div>}

        <Field label="Year">
          <input
            type="number"
            required
            value={form.year}
            onChange={(e) => setForm({ ...form, year: e.target.value })}
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </Field>
        <Field label="Tier">
          <select
            value={form.tier}
            onChange={(e) => setForm({ ...form, tier: e.target.value as ExamTier })}
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          >
            <option value="Tier 1">Tier 1</option>
            <option value="Tier 2">Tier 2</option>
          </select>
        </Field>
        <Field label="Shift">
          <input
            type="number"
            min={1}
            required
            value={form.shift}
            onChange={(e) => setForm({ ...form, shift: e.target.value })}
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </Field>
        <Field label="Exam date (optional)">
          <input
            type="date"
            value={form.exam_date}
            onChange={(e) => setForm({ ...form, exam_date: e.target.value })}
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </Field>
        <Field label="Duration (minutes)">
          <input
            type="number"
            min={1}
            required
            value={form.duration_minutes}
            onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })}
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </Field>
        <Field label="Total questions">
          <input
            type="number"
            min={1}
            required
            value={form.total_questions}
            onChange={(e) => setForm({ ...form, total_questions: e.target.value })}
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </Field>
        <Field label="Total marks">
          <input
            required
            value={form.total_marks}
            onChange={(e) => setForm({ ...form, total_marks: e.target.value })}
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </Field>
        <Field label="Source PDF name (optional)">
          <input
            value={form.source_pdf_name}
            onChange={(e) => setForm({ ...form, source_pdf_name: e.target.value })}
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </Field>

        <div className="col-span-full">
          <button
            type="submit"
            disabled={creating}
            className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
          >
            {creating ? "Creating..." : "Create Exam"}
          </button>
        </div>
      </form>

      {loadError && <ErrorMessage message={loadError} onRetry={load} />}
      {!loadError && exams === null && <Spinner label="Loading exams..." />}
      {exams !== null && exams.length === 0 && (
        <EmptyState title="No exams yet" description="Create one above to get started." />
      )}

      {exams !== null && exams.length > 0 && (
        <div className="flex flex-col gap-2">
          {exams.map((exam) => (
            <Link
              key={exam.id}
              href={`/admin/exams/${exam.id}`}
              className="flex items-center justify-between rounded-lg border border-zinc-200 bg-white p-3 hover:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-600"
            >
              <div>
                <p className="font-medium text-zinc-900 dark:text-zinc-50">{examTitle(exam)}</p>
                <p className="text-sm text-zinc-500">
                  {exam.total_questions} questions &middot; {exam.duration_minutes} min &middot; {exam.total_marks}{" "}
                  marks
                </p>
              </div>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  exam.is_published
                    ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                    : "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                }`}
              >
                {exam.is_published ? "published" : "unpublished"}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
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
