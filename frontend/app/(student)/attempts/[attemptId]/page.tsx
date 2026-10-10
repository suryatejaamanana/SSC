"use client";

import { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { Attempt, QuestionForAttempt } from "@/lib/types";
import { resolveMediaUrl } from "@/lib/format";
import Spinner from "@/components/Spinner";
import ErrorMessage from "@/components/ErrorMessage";
import Timer from "@/components/Timer";
import OptionsList from "@/components/OptionsList";
import QuestionPalette, { type PaletteItem } from "@/components/QuestionPalette";
import ConfirmModal from "@/components/ConfirmModal";

// Serves BOTH full-paper and topic-practice attempts - the backend unified
// these behind the same attempt endpoints (Phase 5), and from here they are
// indistinguishable: same timer, same questions/answers/submit shape.
export default function AttemptPage({ params }: { params: Promise<{ attemptId: string }> }) {
  const { attemptId } = use(params);
  const router = useRouter();

  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [questions, setQuestions] = useState<QuestionForAttempt[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const attemptData = await api.get<Attempt>(`/api/v1/attempts/${attemptId}`);
      if (attemptData.status !== "in_progress") {
        router.replace(`/attempts/${attemptId}/result`);
        return;
      }
      const questionsData = await api.get<QuestionForAttempt[]>(
        `/api/v1/attempts/${attemptId}/questions`
      );
      setAttempt(attemptData);
      setQuestions(questionsData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load attempt");
    }
  }, [attemptId, router]);

  useEffect(() => {
    load();
  }, [load]);

  // The backend's /answers endpoint replaces selected_option AND
  // marked_for_review together (it is not a partial update) - every call
  // here must send both fields reflecting the full desired state, or the
  // one not being changed would silently get reset to its default.
  async function persistAnswer(
    questionId: number,
    next: { selected_option: string | null; marked_for_review: boolean }
  ) {
    setSaveError(null);
    setQuestions((prev) =>
      prev ? prev.map((q) => (q.question_id === questionId ? { ...q, ...next } : q)) : prev
    );
    try {
      await api.post(`/api/v1/attempts/${attemptId}/answers`, {
        question_id: questionId,
        ...next,
      });
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Failed to save your answer");
      await load(); // resync with the server's actual state
    }
  }

  async function handleSubmit() {
    setSubmitting(true);
    try {
      await api.post(`/api/v1/attempts/${attemptId}/submit`);
      router.push(`/attempts/${attemptId}/result`);
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Failed to submit");
      setSubmitting(false);
      setConfirmOpen(false);
    }
  }

  if (error) return <ErrorMessage message={error} onRetry={load} />;
  if (!attempt || !questions || questions.length === 0) {
    return <Spinner label="Loading your attempt..." />;
  }

  const current = questions[currentIndex];
  const answeredCount = questions.filter((q) => q.selected_option !== null).length;
  const paletteItems: PaletteItem[] = questions.map((q) => ({
    questionId: q.question_id,
    answered: q.selected_option !== null,
    markedForReview: q.marked_for_review,
  }));

  return (
    <div className="flex flex-col gap-4">
      <div className="sticky top-0 z-10 -mx-4 flex items-center justify-between border-b border-zinc-200 bg-zinc-50/95 px-4 py-2 dark:border-zinc-800 dark:bg-zinc-950/95">
        <p className="text-sm text-zinc-500">
          Question {currentIndex + 1} of {questions.length}
        </p>
        <Timer expiresAt={attempt.expires_at} onExpire={handleSubmit} />
      </div>

      <h1 className="sr-only">Exam attempt</h1>

      {saveError && <ErrorMessage message={saveError} />}

      <div className="grid gap-4 sm:grid-cols-[1fr_200px]">
        <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
          {current.passage_text && (
            <div className="mb-4 whitespace-pre-wrap rounded-md border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-700 dark:border-zinc-800 dark:bg-zinc-800/50 dark:text-zinc-300">
              {current.passage_text}
            </div>
          )}
          <p className="whitespace-pre-wrap text-sm text-zinc-900 dark:text-zinc-50">
            {current.question_number ? `${current.question_number}. ` : ""}
            {current.question_text}
          </p>
          {current.question_image_url && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={resolveMediaUrl(current.question_image_url) ?? undefined}
              alt="Question"
              className="mt-3 max-w-full"
            />
          )}

          <div className="mt-4">
            <OptionsList
              options={current.options}
              selected={current.selected_option}
              onSelect={(label) =>
                persistAnswer(current.question_id, {
                  selected_option: label === current.selected_option ? null : label,
                  marked_for_review: current.marked_for_review,
                })
              }
            />
          </div>

          <div className="mt-4 flex items-center justify-between">
            <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
              <input
                type="checkbox"
                checked={current.marked_for_review}
                onChange={(e) =>
                  persistAnswer(current.question_id, {
                    selected_option: current.selected_option,
                    marked_for_review: e.target.checked,
                  })
                }
              />
              Mark for review
            </label>

            <button
              type="button"
              onClick={() =>
                persistAnswer(current.question_id, {
                  selected_option: null,
                  marked_for_review: current.marked_for_review,
                })
              }
              className="text-sm text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
            >
              Clear response
            </button>
          </div>

          <div className="mt-6 flex justify-between">
            <button
              type="button"
              disabled={currentIndex === 0}
              onClick={() => setCurrentIndex((i) => Math.max(0, i - 1))}
              className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium disabled:opacity-40 dark:border-zinc-700"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={currentIndex === questions.length - 1}
              onClick={() => setCurrentIndex((i) => Math.min(questions.length - 1, i + 1))}
              className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium disabled:opacity-40 dark:border-zinc-700"
            >
              Next
            </button>
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <p className="text-sm text-zinc-500">
            {answeredCount} of {questions.length} answered
          </p>
          <QuestionPalette items={paletteItems} currentIndex={currentIndex} onSelect={setCurrentIndex} />
          <button
            type="button"
            onClick={() => setConfirmOpen(true)}
            className="mt-2 rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900"
          >
            Submit
          </button>
        </div>
      </div>

      <ConfirmModal
        open={confirmOpen}
        title="Submit attempt?"
        description={`You have answered ${answeredCount} of ${questions.length} questions. Once submitted, you cannot change your answers.`}
        confirmLabel="Submit"
        busy={submitting}
        onConfirm={handleSubmit}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}
