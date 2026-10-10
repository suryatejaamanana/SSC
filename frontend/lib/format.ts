import type { Exam } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Question/option images extracted from a PDF import are served through
 * the authenticated /api/v1/media route and stored as a root-relative path
 * (e.g. "/api/v1/media/imports/3/images/q7_stem.png"), which must be
 * resolved against the backend's own origin - not the frontend's - for the
 * auth cookie to be sent. An admin-typed external image URL (still
 * supported, Phase 8) is already absolute and is returned unchanged. */
export function resolveMediaUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  if (url.startsWith("/")) return `${API_URL}${url}`;
  return url;
}

/** Exam titles are intentionally not stored by the backend - generated here
 * from year/tier/shift, exactly as the architecture calls for. */
export function examTitle(exam: Pick<Exam, "year" | "tier" | "shift">): string {
  return `SSC CGL ${exam.year} ${exam.tier} Shift ${exam.shift}`;
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function formatScore(score: string | number): string {
  return Number(score).toFixed(2);
}

export function formatDuration(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}
