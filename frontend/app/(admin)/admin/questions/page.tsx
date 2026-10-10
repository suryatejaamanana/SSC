"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { Exam, Question, QuestionStatus, Subject, Topic } from "@/lib/types";
import { examTitle } from "@/lib/format";
import Spinner from "@/components/Spinner";
import ErrorMessage from "@/components/ErrorMessage";
import EmptyState from "@/components/EmptyState";
import StatusBadge from "@/components/StatusBadge";
import ConfirmModal from "@/components/ConfirmModal";

export default function QuestionsPage() {
  const searchParams = useSearchParams();

  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [exams, setExams] = useState<Exam[]>([]);
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [examFilter, setExamFilter] = useState<number | "all">(() => {
    const raw = searchParams.get("exam_id");
    return raw ? Number(raw) : "all";
  });
  const [subjectFilter, setSubjectFilter] = useState<number | "all">("all");
  const [topicFilter, setTopicFilter] = useState<number | "all">("all");
  const [statusFilter, setStatusFilter] = useState<QuestionStatus | "all">("all");

  const [deleteTarget, setDeleteTarget] = useState<Question | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const [publishingId, setPublishingId] = useState<number | null>(null);
  const [publishErrorFor, setPublishErrorFor] = useState<{ id: number; message: string } | null>(null);

  const [archivingId, setArchivingId] = useState<number | null>(null);
  const [archiveErrorFor, setArchiveErrorFor] = useState<{ id: number; message: string } | null>(null);

  async function load() {
    setLoadError(null);
    setQuestions(null);
    try {
      const [subjectsData, topicsData, examsData, questionsData] = await Promise.all([
        api.get<Subject[]>("/api/v1/admin/subjects"),
        api.get<Topic[]>("/api/v1/admin/topics"),
        api.get<Exam[]>("/api/v1/admin/exams"),
        api.get<Question[]>("/api/v1/admin/questions"),
      ]);
      setSubjects(subjectsData);
      setTopics(topicsData);
      setExams(examsData);
      setQuestions(questionsData);
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Failed to load questions");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const subjectName = useMemo(() => {
    const map = new Map(subjects.map((s) => [s.id, s.name]));
    return (id: number | null) => (id !== null ? map.get(id) : undefined);
  }, [subjects]);
  const topicName = useMemo(() => {
    const map = new Map(topics.map((t) => [t.id, t.name]));
    return (id: number | null) => (id !== null ? map.get(id) : undefined);
  }, [topics]);
  const examLabel = useMemo(() => {
    const map = new Map(exams.map((e) => [e.id, examTitle(e)]));
    return (id: number | null) => (id !== null ? map.get(id) : undefined);
  }, [exams]);

  const visibleQuestions = useMemo(() => {
    return (questions ?? []).filter(
      (q) =>
        (examFilter === "all" || q.exam_id === examFilter) &&
        (subjectFilter === "all" || q.subject_id === subjectFilter) &&
        (topicFilter === "all" || q.topic_id === topicFilter) &&
        (statusFilter === "all" || q.status === statusFilter)
    );
  }, [questions, examFilter, subjectFilter, topicFilter, statusFilter]);

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleteError(null);
    setDeleting(true);
    try {
      await api.delete(`/api/v1/admin/questions/${deleteTarget.id}`);
      setDeleteTarget(null);
      await load();
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : "Failed to delete question");
      setDeleting(false);
    }
  }

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

  async function handleArchive(question: Question) {
    setArchiveErrorFor(null);
    setArchivingId(question.id);
    try {
      await api.patch<Question>(`/api/v1/admin/questions/${question.id}`, { status: "archived" });
      await load();
    } catch (err) {
      setArchiveErrorFor({
        id: question.id,
        message: err instanceof ApiError ? err.message : "Failed to archive question",
      });
    } finally {
      setArchivingId(null);
    }
  }

  if (loadError) return <ErrorMessage message={loadError} onRetry={load} />;
  if (questions === null) return <Spinner label="Loading questions..." />;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Questions</h1>
        <Link
          href="/admin/questions/new"
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900"
        >
          New Question
        </Link>
      </div>

      <div className="flex flex-wrap gap-3">
        <FilterSelect
          label="Exam"
          value={examFilter}
          onChange={setExamFilter}
          options={exams.map((e) => ({ value: e.id, label: examTitle(e) }))}
        />
        <FilterSelect
          label="Subject"
          value={subjectFilter}
          onChange={setSubjectFilter}
          options={subjects.map((s) => ({ value: s.id, label: s.name }))}
        />
        <FilterSelect
          label="Topic"
          value={topicFilter}
          onChange={setTopicFilter}
          options={topics.map((t) => ({ value: t.id, label: t.name }))}
        />
        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Status
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as QuestionStatus | "all")}
            className="ml-2 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          >
            <option value="all">All</option>
            <option value="draft">Draft</option>
            <option value="pending_review">Pending review</option>
            <option value="published">Published</option>
            <option value="archived">Archived</option>
          </select>
        </label>
      </div>

      {visibleQuestions.length === 0 && (
        <EmptyState title="No questions match these filters" />
      )}

      {visibleQuestions.length > 0 && (
        <div className="flex flex-col gap-2">
          {visibleQuestions.map((q) => (
            <div
              key={q.id}
              className="flex flex-col gap-2 rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <StatusBadge status={q.status} />
                    <span className="text-xs text-zinc-500">
                      {[examLabel(q.exam_id), subjectName(q.subject_id), topicName(q.topic_id)]
                        .filter(Boolean)
                        .join(" / ") || "Uncategorized"}
                    </span>
                  </div>
                  <p className="mt-1 line-clamp-2 text-sm text-zinc-900 dark:text-zinc-50">
                    {q.question_number ? `${q.question_number}. ` : ""}
                    {q.question_text}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Link
                    href={`/admin/questions/${q.id}`}
                    className="rounded-md border border-zinc-300 px-3 py-1 text-sm font-medium dark:border-zinc-700"
                  >
                    Edit
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
                  {q.status !== "archived" && (
                    <button
                      type="button"
                      onClick={() => handleArchive(q)}
                      disabled={archivingId === q.id}
                      className="rounded-md border border-zinc-300 px-3 py-1 text-sm font-medium disabled:opacity-50 dark:border-zinc-700"
                    >
                      {archivingId === q.id ? "Archiving..." : "Archive"}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setDeleteTarget(q)}
                    className="rounded-md border border-red-300 px-3 py-1 text-sm font-medium text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950"
                  >
                    Delete
                  </button>
                </div>
              </div>
              {publishErrorFor?.id === q.id && (
                <p className="text-sm text-red-700 dark:text-red-400">{publishErrorFor.message}</p>
              )}
              {archiveErrorFor?.id === q.id && (
                <p className="text-sm text-red-700 dark:text-red-400">{archiveErrorFor.message}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {deleteError && <ErrorMessage message={deleteError} />}

      <ConfirmModal
        open={deleteTarget !== null}
        title="Delete question?"
        description="This will permanently delete this question and its options."
        confirmLabel="Delete"
        busy={deleting}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: number | "all";
  onChange: (v: number | "all") => void;
  options: { value: number; label: string }[];
}) {
  return (
    <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value === "all" ? "all" : Number(e.target.value))}
        className="ml-2 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800"
      >
        <option value="all">All</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
