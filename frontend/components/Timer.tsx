"use client";

import { useEffect, useRef, useState } from "react";
import { formatDuration } from "@/lib/format";

/**
 * Pure display countdown. `expiresAt` comes from the server and is never
 * extended or recomputed client-side - this component only diffs it against
 * the browser clock to decide what to *show*. Actual expiry enforcement
 * happens server-side on every attempt endpoint regardless of whether
 * `onExpire` fires or the tab is even open; this is a best-effort UX nudge
 * to auto-submit, not the authority.
 */
export default function Timer({
  expiresAt,
  onExpire,
}: {
  expiresAt: string;
  onExpire: () => void;
}) {
  const expiresAtMs = new Date(expiresAt).getTime();
  const [remainingMs, setRemainingMs] = useState(() => expiresAtMs - Date.now());
  const firedRef = useRef(false);

  useEffect(() => {
    firedRef.current = false;
    const interval = setInterval(() => {
      const remaining = expiresAtMs - Date.now();
      setRemainingMs(remaining);
      if (remaining <= 0 && !firedRef.current) {
        firedRef.current = true;
        onExpire();
      }
    }, 1000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expiresAtMs]);

  const isLow = remainingMs <= 5 * 60 * 1000;

  return (
    <div
      className={`rounded-md px-3 py-1.5 font-mono text-sm font-semibold ${
        isLow
          ? "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300"
          : "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200"
      }`}
    >
      {formatDuration(remainingMs / 1000)}
    </div>
  );
}
