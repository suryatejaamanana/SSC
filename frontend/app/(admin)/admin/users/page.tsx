"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { User, UserRole } from "@/lib/types";
import { formatDateTime } from "@/lib/format";
import { useAuth } from "@/lib/auth-context";
import Spinner from "@/components/Spinner";
import ErrorMessage from "@/components/ErrorMessage";
import EmptyState from "@/components/EmptyState";

export default function UsersPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [busyId, setBusyId] = useState<number | null>(null);
  const [errorFor, setErrorFor] = useState<{ id: number; message: string } | null>(null);

  async function load() {
    setLoadError(null);
    try {
      setUsers(await api.get<User[]>("/api/v1/admin/users"));
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Failed to load users");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function updateUser(id: number, payload: { role?: UserRole; is_active?: boolean }) {
    setErrorFor(null);
    setBusyId(id);
    try {
      const updated = await api.patch<User>(`/api/v1/admin/users/${id}`, payload);
      setUsers((prev) => (prev ? prev.map((u) => (u.id === id ? updated : u)) : prev));
    } catch (err) {
      setErrorFor({ id, message: err instanceof ApiError ? err.message : "Failed to update user" });
    } finally {
      setBusyId(null);
    }
  }

  if (loadError) return <ErrorMessage message={loadError} onRetry={load} />;
  if (users === null) return <Spinner label="Loading users..." />;

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Users</h1>

      {users.length === 0 && <EmptyState title="No users yet" />}

      {users.length > 0 && (
        <div className="flex flex-col gap-2">
          {users.map((u) => {
            const isSelf = currentUser?.id === u.id;
            return (
              <div
                key={u.id}
                className="flex flex-col gap-2 rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900"
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
                  <div className="min-w-0">
                    <p className="font-medium text-zinc-900 dark:text-zinc-50">
                      {u.name} {isSelf && <span className="text-xs text-zinc-500">(you)</span>}
                    </p>
                    <p className="break-words text-sm text-zinc-500">
                      {u.email} &middot; joined {formatDateTime(u.created_at)}
                    </p>
                  </div>

                  <div className="flex shrink-0 items-center gap-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        u.is_active
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                          : "bg-zinc-200 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
                      }`}
                    >
                      {u.is_active ? "active" : "inactive"}
                    </span>

                    <select
                      aria-label={`Role for ${u.name}`}
                      value={u.role}
                      disabled={isSelf || busyId === u.id}
                      onChange={(e) => updateUser(u.id, { role: e.target.value as UserRole })}
                      className="rounded-md border border-zinc-300 px-2 py-1 text-sm disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800"
                    >
                      <option value="student">student</option>
                      <option value="admin">admin</option>
                    </select>

                    <button
                      type="button"
                      disabled={isSelf || busyId === u.id}
                      onClick={() => updateUser(u.id, { is_active: !u.is_active })}
                      className="rounded-md border border-zinc-300 px-3 py-1 text-sm font-medium disabled:opacity-50 dark:border-zinc-700"
                    >
                      {busyId === u.id ? "..." : u.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </div>
                </div>
                {errorFor?.id === u.id && (
                  <p className="text-sm text-red-700 dark:text-red-400">{errorFor.message}</p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
