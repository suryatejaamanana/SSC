"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { Exam, ExamTier } from "@/lib/types";
import { examTitle } from "@/lib/format";
import Spinner from "@/components/Spinner";
import ErrorMessage from "@/components/ErrorMessage";
import ErrorDisplay from "@/components/ErrorDisplay";
import ConfirmModal from "@/components/ConfirmModal";

export default function ExamDetailPage({ params }: { params: Promise<{ examId: string }> }) {
  const { examId } = use(params);
  const router = useRouter();

  const [exam, setExam] = useState<Exam | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [form, setForm] = useState<{
    year: string;
    tier: ExamTier;
    shift: string;
    exam_date: string;
    duration_minutes: string;
    total_questions: string;
    total_marks: string;
    source_pdf_name: string;
  } | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [publishError, setPublishError] = useState<unknown>(null);
  const [publishing, setPublishing] = useState(false);

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function load() {
    setLoadError(null);
    setExam(null);
    try {
      const data = await api.get<Exam>(`/api/v1/admin/exams/${examId}`);
      setExam(data);
      setForm({
        year: String(data.year),
        tier: data.tier,
        shift: String(data.shift),
        exam_date: data.exam_date ?? "",
        duration_minutes: String(data.duration_minutes),
        total_questions: String(data.total_questions),
        total_marks: data.total_marks,
        source_pdf_name: data.source_pdf_name ?? "",
      });
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Failed to load exam");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [examId]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setSaveError(null);
    setSaved(false);
    setSaving(true);
    try {
      const updated = await api.patch<Exam>(`/api/v1/admin/exams/${examId}`, {
        year: Number(form.year),
        tier: form.tier,
        shift: Number(form.shift),
        exam_date: form.exam_date || null,
        duration_minutes: Number(form.duration_minutes),
        total_questions: Number(form.total_questions),
        total_marks: form.total_marks,
        source_pdf_name: form.source_pdf_name || null,
      });
      setExam(updated);
      setSaved(true);
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Failed to save changes");
    } finally {
      setSaving(false);
    }
  }

  async function handlePublish() {
    setPublishError(null);
    setPublishing(true);
    try {
      const updated = await api.post<Exam>(`/api/v1/admin/exams/${examId}/publish`);
      setExam(updated);
    } catch (err) {
      setPublishError(err);
    } finally {
      setPublishing(false);
    }
  }

  async function handleDelete() {
    setDeleteError(null);
    setDeleting(true);
    try {
      await api.delete(`/api/v1/admin/exams/${examId}`);
      router.push("/admin/exams");
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : "Failed to delete exam");
      setDeleting(false);
    }
  }

  if (loadError) return <ErrorMessage message={loadError} onRetry={load} />;
  if (!exam || !form) return <Spinner label="Loading exam..." />;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">{examTitle(exam)}</h1>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            exam.is_published
              ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
              : "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
          }`}
        >
          {exam.is_published ? "published" : "unpublished"}
        </span>
      </div>

      <Link
        href={`/admin/questions?exam_id=${exam.id}`}
        className="self-start text-sm font-medium text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
      >
        View questions for this exam &rarr;
      </Link>

      {!exam.is_published && (
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Publishing requires exactly {exam.total_questions} published questions totalling{" "}
            {exam.total_marks} marks for this exam.
          </p>
          {publishError !== null && (
            <div className="mt-2">
              <ErrorDisplay error={publishError} title="Cannot publish this exam:" />
            </div>
          )}
          <button
            type="button"
            onClick={handlePublish}
            disabled={publishing}
            className="mt-3 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {publishing ? "Publishing..." : "Publish Exam"}
          </button>
        </div>
      )}

      <form
        onSubmit={handleSave}
        className="grid grid-cols-2 gap-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900 sm:grid-cols-4"
      >
        {saveError && <div className="col-span-full"><ErrorMessage message={saveError} /></div>}
        {saved && (
          <p className="col-span-full text-sm text-emerald-600 dark:text-emerald-400">Saved.</p>
        )}

        <Field label="Year">
          <input
            type="number"
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
            value={form.shift}
            onChange={(e) => setForm({ ...form, shift: e.target.value })}
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </Field>
        <Field label="Exam date">
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
            value={form.duration_minutes}
            onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })}
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </Field>
        <Field label="Total questions">
          <input
            type="number"
            min={1}
            value={form.total_questions}
            onChange={(e) => setForm({ ...form, total_questions: e.target.value })}
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </Field>
        <Field label="Total marks">
          <input
            value={form.total_marks}
            onChange={(e) => setForm({ ...form, total_marks: e.target.value })}
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </Field>
        <Field label="Source PDF name">
          <input
            value={form.source_pdf_name}
            onChange={(e) => setForm({ ...form, source_pdf_name: e.target.value })}
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </Field>

        <div className="col-span-full flex items-center justify-between">
          <button
            type="submit"
            disabled={saving}
            className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
          >
            {saving ? "Saving..." : "Save Changes"}
          </button>
          <button
            type="button"
            onClick={() => setDeleteOpen(true)}
            className="rounded-md border border-red-300 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950"
          >
            Delete Exam
          </button>
        </div>
      </form>

      {deleteError && <ErrorMessage message={deleteError} />}

      <ConfirmModal
        open={deleteOpen}
        title="Delete exam?"
        description="This will permanently delete this exam. Exams that still have questions cannot be deleted."
        confirmLabel="Delete"
        busy={deleting}
        onConfirm={handleDelete}
        onCancel={() => setDeleteOpen(false)}
      />
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
