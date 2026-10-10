"use client";

import { use, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { Exam, OptionLabel, Question, QuestionStatus, Subject, Topic } from "@/lib/types";
import { examTitle, resolveMediaUrl } from "@/lib/format";
import Spinner from "@/components/Spinner";
import ErrorMessage from "@/components/ErrorMessage";
import ErrorDisplay from "@/components/ErrorDisplay";
import StatusBadge from "@/components/StatusBadge";
import ConfirmModal from "@/components/ConfirmModal";
import QuestionOptionsEditor, {
  EMPTY_OPTION_SLOTS,
  buildOptionsPayload,
  type OptionSlots,
} from "@/components/QuestionOptionsEditor";

const EDITABLE_STATUSES: QuestionStatus[] = ["draft", "pending_review", "archived"];

export default function EditQuestionPage({ params }: { params: Promise<{ questionId: string }> }) {
  const { questionId } = use(params);
  const router = useRouter();

  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [exams, setExams] = useState<Exam[]>([]);
  const [question, setQuestion] = useState<Question | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [examId, setExamId] = useState<number | "">("");
  const [subjectId, setSubjectId] = useState<number | "">("");
  const [topicId, setTopicId] = useState<number | "">("");
  const [questionNumber, setQuestionNumber] = useState("");
  const [questionText, setQuestionText] = useState("");
  const [questionImageUrl, setQuestionImageUrl] = useState("");
  const [passageText, setPassageText] = useState("");
  const [correctOption, setCorrectOption] = useState<OptionLabel | "">("");
  const [positiveMarks, setPositiveMarks] = useState("2.00");
  const [negativeMarks, setNegativeMarks] = useState("0.50");
  const [solutionText, setSolutionText] = useState("");
  const [status, setStatus] = useState<QuestionStatus>("draft");
  const [options, setOptions] = useState<OptionSlots>(EMPTY_OPTION_SLOTS);

  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [publishError, setPublishError] = useState<unknown>(null);
  const [publishing, setPublishing] = useState(false);

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  function applyQuestion(data: Question) {
    setQuestion(data);
    setExamId(data.exam_id ?? "");
    setSubjectId(data.subject_id ?? "");
    setTopicId(data.topic_id ?? "");
    setQuestionNumber(data.question_number ? String(data.question_number) : "");
    setQuestionText(data.question_text);
    setQuestionImageUrl(data.question_image_url ?? "");
    setPassageText(data.passage_text ?? "");
    setCorrectOption((data.correct_option as OptionLabel | null) ?? "");
    setPositiveMarks(data.positive_marks);
    setNegativeMarks(data.negative_marks);
    setSolutionText(data.solution_text ?? "");
    setStatus(data.status === "published" ? "draft" : data.status);
    const slots: OptionSlots = { ...EMPTY_OPTION_SLOTS };
    for (const opt of data.options) {
      if (opt.label === "A" || opt.label === "B" || opt.label === "C" || opt.label === "D") {
        slots[opt.label] = { text: opt.text ?? "", image_url: opt.image_url ?? "" };
      }
    }
    setOptions(slots);
  }

  async function load() {
    setLoadError(null);
    setQuestion(null);
    try {
      const [subjectsData, topicsData, examsData, questionData] = await Promise.all([
        api.get<Subject[]>("/api/v1/admin/subjects"),
        api.get<Topic[]>("/api/v1/admin/topics"),
        api.get<Exam[]>("/api/v1/admin/exams"),
        api.get<Question>(`/api/v1/admin/questions/${questionId}`),
      ]);
      setSubjects(subjectsData);
      setTopics(topicsData);
      setExams(examsData);
      applyQuestion(questionData);
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Failed to load question");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [questionId]);

  const topicsForSubject = useMemo(
    () => (subjectId === "" ? topics : topics.filter((t) => t.subject_id === subjectId)),
    [topics, subjectId]
  );

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaveError(null);
    setSaved(false);
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        exam_id: examId === "" ? null : examId,
        subject_id: subjectId === "" ? null : subjectId,
        topic_id: topicId === "" ? null : topicId,
        question_number: questionNumber ? Number(questionNumber) : null,
        question_text: questionText,
        question_image_url: questionImageUrl || null,
        passage_text: passageText || null,
        correct_option: correctOption || null,
        positive_marks: positiveMarks,
        negative_marks: negativeMarks,
        solution_text: solutionText || null,
        options: buildOptionsPayload(options),
      };
      // status can only move between draft/pending_review/archived here -
      // "published" is only ever reachable through the dedicated action below.
      if (question?.status !== "published") {
        payload.status = status;
      }
      const updated = await api.patch<Question>(`/api/v1/admin/questions/${questionId}`, payload);
      applyQuestion(updated);
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
      const updated = await api.post<Question>(`/api/v1/admin/questions/${questionId}/publish`);
      applyQuestion(updated);
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
      await api.delete(`/api/v1/admin/questions/${questionId}`);
      router.push("/admin/questions");
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : "Failed to delete question");
      setDeleting(false);
    }
  }

  if (loadError) return <ErrorMessage message={loadError} onRetry={load} />;
  if (!question) return <Spinner label="Loading question..." />;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Edit Question</h1>
        <StatusBadge status={question.status} />
      </div>

      {question.status !== "published" && (
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Publishing requires: question text, a subject, a topic, a correct option, and exactly 4
            options labelled A-D, each with text or an image.
          </p>
          {publishError !== null && (
            <div className="mt-2">
              <ErrorDisplay error={publishError} title="Cannot publish this question:" />
            </div>
          )}
          <button
            type="button"
            onClick={handlePublish}
            disabled={publishing}
            className="mt-3 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {publishing ? "Publishing..." : "Publish Question"}
          </button>
        </div>
      )}

      <form
        onSubmit={handleSave}
        className="flex flex-col gap-4 rounded-lg border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900"
      >
        {saveError && <ErrorMessage message={saveError} />}
        {saved && <p className="text-sm text-emerald-600 dark:text-emerald-400">Saved.</p>}

        <div className="grid gap-3 sm:grid-cols-4">
          <Field label="Exam">
            <select
              value={examId}
              onChange={(e) => setExamId(e.target.value ? Number(e.target.value) : "")}
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
            >
              <option value="">None</option>
              {exams.map((e) => (
                <option key={e.id} value={e.id}>
                  {examTitle(e)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Subject">
            <select
              value={subjectId}
              onChange={(e) => setSubjectId(e.target.value ? Number(e.target.value) : "")}
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
            >
              <option value="">None</option>
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Topic">
            <select
              value={topicId}
              onChange={(e) => setTopicId(e.target.value ? Number(e.target.value) : "")}
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
            >
              <option value="">None</option>
              {topicsForSubject.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Status">
            <select
              value={status}
              disabled={question.status === "published"}
              onChange={(e) => setStatus(e.target.value as QuestionStatus)}
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800"
            >
              {EDITABLE_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s.replace("_", " ")}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <Field label="Question number">
          <input
            type="number"
            min={1}
            value={questionNumber}
            onChange={(e) => setQuestionNumber(e.target.value)}
            className="w-full max-w-xs rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </Field>

        <Field label="Comprehension passage (shared, optional)">
          <textarea
            rows={4}
            value={passageText}
            onChange={(e) => setPassageText(e.target.value)}
            placeholder="Only set for reading-comprehension / cloze questions that share a passage"
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </Field>

        <Field label="Question text">
          <textarea
            required
            rows={3}
            value={questionText}
            onChange={(e) => setQuestionText(e.target.value)}
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </Field>

        <Field label="Question image URL">
          <input
            value={questionImageUrl}
            onChange={(e) => setQuestionImageUrl(e.target.value)}
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
          {questionImageUrl && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={resolveMediaUrl(questionImageUrl) ?? undefined}
              alt="Question figure preview"
              className="mt-2 max-h-40"
            />
          )}
        </Field>

        <QuestionOptionsEditor value={options} onChange={setOptions} />

        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Correct option">
            <select
              value={correctOption}
              onChange={(e) => setCorrectOption(e.target.value as OptionLabel | "")}
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
            >
              <option value="">None</option>
              <option value="A">A</option>
              <option value="B">B</option>
              <option value="C">C</option>
              <option value="D">D</option>
            </select>
          </Field>
          <Field label="Positive marks">
            <input
              value={positiveMarks}
              onChange={(e) => setPositiveMarks(e.target.value)}
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
            />
          </Field>
          <Field label="Negative marks">
            <input
              value={negativeMarks}
              onChange={(e) => setNegativeMarks(e.target.value)}
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
            />
          </Field>
        </div>

        <Field label="Solution">
          <textarea
            rows={3}
            value={solutionText}
            onChange={(e) => setSolutionText(e.target.value)}
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </Field>

        <div className="flex items-center justify-between">
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
            Delete Question
          </button>
        </div>
      </form>

      {deleteError && <ErrorMessage message={deleteError} />}

      <ConfirmModal
        open={deleteOpen}
        title="Delete question?"
        description="This will permanently delete this question and its options."
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
