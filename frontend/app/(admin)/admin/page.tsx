"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { Exam, ImportBatchSummary, Question, Subject, Topic, User } from "@/lib/types";
import Spinner from "@/components/Spinner";
import ErrorMessage from "@/components/ErrorMessage";
import StatTile from "@/components/StatTile";

export default function AdminDashboardPage() {
  const [counts, setCounts] = useState<{
    subjects: number;
    topics: number;
    exams: number;
    publishedExams: number;
    questions: number;
    publishedQuestions: number;
    importBatches: number;
    importBatchesNeedingAttention: number;
    users: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    setCounts(null);
    try {
      const [subjects, topics, exams, questions, imports, users] = await Promise.all([
        api.get<Subject[]>("/api/v1/admin/subjects"),
        api.get<Topic[]>("/api/v1/admin/topics"),
        api.get<Exam[]>("/api/v1/admin/exams"),
        api.get<Question[]>("/api/v1/admin/questions"),
        api.get<ImportBatchSummary[]>("/api/v1/admin/imports"),
        api.get<User[]>("/api/v1/admin/users"),
      ]);
      setCounts({
        subjects: subjects.length,
        topics: topics.length,
        exams: exams.length,
        publishedExams: exams.filter((e) => e.is_published).length,
        questions: questions.length,
        publishedQuestions: questions.filter((q) => q.status === "published").length,
        importBatches: imports.length,
        importBatchesNeedingAttention: imports.filter(
          (b) => b.status === "failed" || b.status === "pending_review"
        ).length,
        users: users.length,
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load dashboard");
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (error) return <ErrorMessage message={error} onRetry={load} />;
  if (!counts) return <Spinner label="Loading dashboard..." />;

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Admin Dashboard</h1>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <StatTile label="Exams" value={`${counts.publishedExams} / ${counts.exams} published`} />
        <StatTile label="Questions" value={`${counts.publishedQuestions} / ${counts.questions} published`} />
        <StatTile
          label="PDF imports"
          value={
            counts.importBatchesNeedingAttention > 0
              ? `${counts.importBatchesNeedingAttention} / ${counts.importBatches} need attention`
              : `${counts.importBatches} total`
          }
        />
        <StatTile label="Subjects" value={counts.subjects} />
        <StatTile label="Topics" value={counts.topics} />
        <StatTile label="Users" value={counts.users} />
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <DashboardLink href="/admin/imports" label="Upload PDF" />
        <DashboardLink href="/admin/exams" label="Manage Exams" />
        <DashboardLink href="/admin/questions" label="Manage Questions" />
        <DashboardLink href="/admin/users" label="Manage Users" />
        <DashboardLink href="/admin/subjects" label="Manage Subjects" />
        <DashboardLink href="/admin/topics" label="Manage Topics" />
      </div>
    </div>
  );
}

function DashboardLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="flex items-center justify-center rounded-lg border border-zinc-200 bg-white p-4 text-center text-sm font-medium text-zinc-700 hover:border-zinc-400 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:border-zinc-600"
    >
      {label}
    </Link>
  );
}
