"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { Attempt, Subject, Topic } from "@/lib/types";
import Spinner from "@/components/Spinner";
import ErrorMessage from "@/components/ErrorMessage";
import EmptyState from "@/components/EmptyState";

export default function TopicPracticePage() {
  const router = useRouter();
  const [subjects, setSubjects] = useState<Subject[] | null>(null);
  const [topics, setTopics] = useState<Topic[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [subjectId, setSubjectId] = useState<number | null>(null);
  const [topicId, setTopicId] = useState<number | null>(null);
  const [questionCount, setQuestionCount] = useState(10);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function load() {
    setLoadError(null);
    setSubjects(null);
    setTopics(null);
    try {
      const [subjectsData, topicsData] = await Promise.all([
        api.get<Subject[]>("/api/v1/subjects"),
        api.get<Topic[]>("/api/v1/topics"),
      ]);
      setSubjects(subjectsData);
      setTopics(topicsData);
      if (subjectsData.length > 0) setSubjectId(subjectsData[0].id);
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Failed to load subjects and topics");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const topicsForSubject = useMemo(
    () => (topics ?? []).filter((t) => t.subject_id === subjectId),
    [topics, subjectId]
  );

  useEffect(() => {
    if (topicsForSubject.length > 0 && !topicsForSubject.some((t) => t.id === topicId)) {
      setTopicId(topicsForSubject[0].id);
    }
    if (topicsForSubject.length === 0) setTopicId(null);
  }, [topicsForSubject, topicId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!topicId) return;
    setFormError(null);
    setSubmitting(true);
    try {
      const attempt = await api.post<Attempt>("/api/v1/attempts/topic-practice", {
        topic_id: topicId,
        question_count: questionCount,
      });
      router.push(`/attempts/${attempt.id}`);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Failed to start practice session");
      setSubmitting(false);
    }
  }

  if (loadError) return <ErrorMessage message={loadError} onRetry={load} />;
  if (subjects === null || topics === null) return <Spinner label="Loading topics..." />;

  if (subjects.length === 0) {
    return <EmptyState title="No subjects available yet" description="Check back once content has been added." />;
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Topic-wise Practice</h1>

      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-4 rounded-lg border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900"
      >
        {formError && <ErrorMessage message={formError} />}

        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Subject
          <select
            value={subjectId ?? ""}
            onChange={(e) => setSubjectId(Number(e.target.value))}
            className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          >
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Topic
          {topicsForSubject.length === 0 ? (
            <p className="mt-1 text-sm text-zinc-500">No topics under this subject yet.</p>
          ) : (
            <select
              value={topicId ?? ""}
              onChange={(e) => setTopicId(Number(e.target.value))}
              className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
            >
              {topicsForSubject.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          )}
        </label>

        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Number of questions
          <input
            type="number"
            min={1}
            max={100}
            value={questionCount}
            onChange={(e) => setQuestionCount(Number(e.target.value))}
            className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </label>

        <button
          type="submit"
          disabled={submitting || !topicId}
          className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {submitting ? "Starting..." : "Start Practice"}
        </button>
      </form>
    </div>
  );
}
