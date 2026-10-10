"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { Exam, OptionLabel, Question, Subject, Topic } from "@/lib/types";
import { examTitle } from "@/lib/format";
import Spinner from "@/components/Spinner";
import ErrorMessage from "@/components/ErrorMessage";
import QuestionOptionsEditor, {
  EMPTY_OPTION_SLOTS,
  buildOptionsPayload,
  type OptionSlots,
} from "@/components/QuestionOptionsEditor";

export default function NewQuestionPage() {
  const router = useRouter();

  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [exams, setExams] = useState<Exam[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [examId, setExamId] = useState<number | "">("");
  const [subjectId, setSubjectId] = useState<number | "">("");
  const [topicId, setTopicId] = useState<number | "">("");
  const [questionNumber, setQuestionNumber] = useState("");
  const [questionText, setQuestionText] = useState("");
  const [questionImageUrl, setQuestionImageUrl] = useState("");
  const [correctOption, setCorrectOption] = useState<OptionLabel | "">("");
  const [positiveMarks, setPositiveMarks] = useState("2.00");
  const [negativeMarks, setNegativeMarks] = useState("0.50");
  const [solutionText, setSolutionText] = useState("");
  const [options, setOptions] = useState<OptionSlots>(EMPTY_OPTION_SLOTS);

  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [subjectsData, topicsData, examsData] = await Promise.all([
          api.get<Subject[]>("/api/v1/admin/subjects"),
          api.get<Topic[]>("/api/v1/admin/topics"),
          api.get<Exam[]>("/api/v1/admin/exams"),
        ]);
        setSubjects(subjectsData);
        setTopics(topicsData);
        setExams(examsData);
      } catch (err) {
        setLoadError(err instanceof ApiError ? err.message : "Failed to load form data");
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  const topicsForSubject = useMemo(
    () => (subjectId === "" ? topics : topics.filter((t) => t.subject_id === subjectId)),
    [topics, subjectId]
  );

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    setSubmitting(true);
    try {
      const created = await api.post<Question>("/api/v1/admin/questions", {
        exam_id: examId === "" ? null : examId,
        subject_id: subjectId === "" ? null : subjectId,
        topic_id: topicId === "" ? null : topicId,
        question_number: questionNumber ? Number(questionNumber) : null,
        question_text: questionText,
        question_image_url: questionImageUrl || null,
        correct_option: correctOption || null,
        positive_marks: positiveMarks,
        negative_marks: negativeMarks,
        solution_text: solutionText || null,
        options: buildOptionsPayload(options),
      });
      router.push(`/admin/questions/${created.id}`);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Failed to create question");
      setSubmitting(false);
    }
  }

  if (loadError) return <ErrorMessage message={loadError} />;
  if (!loaded) return <Spinner label="Loading form..." />;

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">New Question</h1>

      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-4 rounded-lg border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900"
      >
        {submitError && <ErrorMessage message={submitError} />}

        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Exam (optional)">
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
          <Field label="Subject (optional)">
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
          <Field label="Topic (optional)">
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
        </div>

        <Field label="Question number (optional)">
          <input
            type="number"
            min={1}
            value={questionNumber}
            onChange={(e) => setQuestionNumber(e.target.value)}
            className="w-full max-w-xs rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
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

        <Field label="Question image URL (optional)">
          <input
            value={questionImageUrl}
            onChange={(e) => setQuestionImageUrl(e.target.value)}
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
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

        <Field label="Solution (optional)">
          <textarea
            rows={3}
            value={solutionText}
            onChange={(e) => setSolutionText(e.target.value)}
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </Field>

        <button
          type="submit"
          disabled={submitting}
          className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {submitting ? "Creating..." : "Create Question"}
        </button>
      </form>
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
