"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Subject, Topic } from "@/lib/types";
import Spinner from "@/components/Spinner";
import ErrorMessage from "@/components/ErrorMessage";
import EmptyState from "@/components/EmptyState";
import ConfirmModal from "@/components/ConfirmModal";

export default function TopicsPage() {
  const [subjects, setSubjects] = useState<Subject[] | null>(null);
  const [topics, setTopics] = useState<Topic[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [filterSubjectId, setFilterSubjectId] = useState<number | "all">("all");

  const [newSubjectId, setNewSubjectId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editSubjectId, setEditSubjectId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editError, setEditError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<Topic | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function load() {
    setLoadError(null);
    setSubjects(null);
    setTopics(null);
    try {
      const [subjectsData, topicsData] = await Promise.all([
        api.get<Subject[]>("/api/v1/admin/subjects"),
        api.get<Topic[]>("/api/v1/admin/topics"),
      ]);
      setSubjects(subjectsData);
      setTopics(topicsData);
      if (subjectsData.length > 0) setNewSubjectId(subjectsData[0].id);
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Failed to load topics");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const subjectName = useMemo(() => {
    const map = new Map((subjects ?? []).map((s) => [s.id, s.name]));
    return (subjectId: number) => map.get(subjectId) ?? `Subject #${subjectId}`;
  }, [subjects]);

  const visibleTopics = useMemo(
    () => (topics ?? []).filter((t) => filterSubjectId === "all" || t.subject_id === filterSubjectId),
    [topics, filterSubjectId]
  );

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newSubjectId) return;
    setCreateError(null);
    setCreating(true);
    try {
      await api.post<Topic>("/api/v1/admin/topics", {
        subject_id: newSubjectId,
        name,
        description: description || null,
      });
      setName("");
      setDescription("");
      await load();
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "Failed to create topic");
    } finally {
      setCreating(false);
    }
  }

  function startEdit(topic: Topic) {
    setEditingId(topic.id);
    setEditSubjectId(topic.subject_id);
    setEditName(topic.name);
    setEditDescription(topic.description ?? "");
    setEditError(null);
  }

  async function handleSaveEdit(id: number) {
    setEditError(null);
    setSaving(true);
    try {
      await api.patch<Topic>(`/api/v1/admin/topics/${id}`, {
        subject_id: editSubjectId,
        name: editName,
        description: editDescription || null,
      });
      setEditingId(null);
      await load();
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : "Failed to save changes");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleteError(null);
    setDeleting(true);
    try {
      await api.delete(`/api/v1/admin/topics/${deleteTarget.id}`);
      setDeleteTarget(null);
      await load();
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : "Failed to delete topic");
      setDeleting(false);
    }
  }

  if (loadError) return <ErrorMessage message={loadError} onRetry={load} />;
  if (subjects === null || topics === null) return <Spinner label="Loading topics..." />;

  if (subjects.length === 0) {
    return <EmptyState title="Create a subject first" description="Topics must belong to a subject." />;
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Topics</h1>

      <form
        onSubmit={handleCreate}
        className="flex flex-col gap-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900 sm:flex-row sm:items-end"
      >
        {createError && <ErrorMessage message={createError} />}
        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Subject
          <select
            value={newSubjectId ?? ""}
            onChange={(e) => setNewSubjectId(Number(e.target.value))}
            className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          >
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex-1 text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Name
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </label>
        <label className="flex-1 text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Description
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </label>
        <button
          type="submit"
          disabled={creating}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {creating ? "Adding..." : "Add Topic"}
        </button>
      </form>

      <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
        Filter by subject
        <select
          value={filterSubjectId}
          onChange={(e) => setFilterSubjectId(e.target.value === "all" ? "all" : Number(e.target.value))}
          className="ml-2 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800"
        >
          <option value="all">All subjects</option>
          {subjects.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>

      {visibleTopics.length === 0 && (
        <EmptyState title="No topics yet" description="Add one above to get started." />
      )}

      {visibleTopics.length > 0 && (
        <div className="flex flex-col gap-2">
          {visibleTopics.map((topic) =>
            editingId === topic.id ? (
              <div
                key={topic.id}
                className="flex flex-col gap-2 rounded-lg border border-zinc-300 bg-white p-3 dark:border-zinc-700 dark:bg-zinc-900 sm:flex-row sm:items-end"
              >
                {editError && <ErrorMessage message={editError} />}
                <select
                  value={editSubjectId ?? ""}
                  onChange={(e) => setEditSubjectId(Number(e.target.value))}
                  className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800"
                >
                  {subjects.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
                <input
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="flex-1 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800"
                />
                <input
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  className="flex-1 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800"
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => handleSaveEdit(topic.id)}
                    disabled={saving}
                    className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
                  >
                    Save
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditingId(null)}
                    className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium dark:border-zinc-700"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div
                key={topic.id}
                className="flex items-center justify-between rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900"
              >
                <div>
                  <p className="font-medium text-zinc-900 dark:text-zinc-50">{topic.name}</p>
                  <p className="text-sm text-zinc-500">{subjectName(topic.subject_id)}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => startEdit(topic)}
                    className="rounded-md border border-zinc-300 px-3 py-1 text-sm font-medium dark:border-zinc-700"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => setDeleteTarget(topic)}
                    className="rounded-md border border-red-300 px-3 py-1 text-sm font-medium text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950"
                  >
                    Delete
                  </button>
                </div>
              </div>
            )
          )}
        </div>
      )}

      {deleteError && <ErrorMessage message={deleteError} />}

      <ConfirmModal
        open={deleteTarget !== null}
        title="Delete topic?"
        description={`This will permanently delete "${deleteTarget?.name}". Topics that still have questions cannot be deleted.`}
        confirmLabel="Delete"
        busy={deleting}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
