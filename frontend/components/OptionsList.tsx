"use client";

import type { OptionForAttempt } from "@/lib/types";
import { resolveMediaUrl } from "@/lib/format";

/**
 * `reveal` only ever receives real data on the review page (post-submission).
 * During an active attempt, callers simply don't pass correctOption, so
 * there is nothing here that could leak it even by mistake.
 */
export default function OptionsList({
  options,
  selected,
  onSelect,
  disabled = false,
  correctOption = null,
}: {
  options: OptionForAttempt[];
  selected: string | null;
  onSelect?: (label: string) => void;
  disabled?: boolean;
  correctOption?: string | null;
}) {
  return (
    <div className="flex flex-col gap-2">
      {options.map((option) => {
        const isSelected = selected === option.label;
        const isCorrect = correctOption === option.label;
        const isWrongSelection = correctOption !== null && isSelected && !isCorrect;

        let classes = "flex items-start gap-3 rounded-md border p-3 text-left text-sm transition-colors ";
        if (correctOption !== null) {
          if (isCorrect) {
            classes += "border-emerald-400 bg-emerald-50 dark:border-emerald-700 dark:bg-emerald-950";
          } else if (isWrongSelection) {
            classes += "border-red-400 bg-red-50 dark:border-red-700 dark:bg-red-950";
          } else {
            classes += "border-zinc-200 dark:border-zinc-800";
          }
        } else if (isSelected) {
          classes += "border-zinc-900 bg-zinc-50 dark:border-zinc-100 dark:bg-zinc-800";
        } else {
          classes += "border-zinc-200 hover:border-zinc-400 dark:border-zinc-800 dark:hover:border-zinc-600";
        }

        return (
          <button
            key={option.label}
            type="button"
            disabled={disabled || !onSelect}
            onClick={() => onSelect?.(option.label)}
            className={classes}
          >
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-current text-xs font-semibold">
              {option.label}
            </span>
            <span className="flex-1">
              {option.text}
              {option.image_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={resolveMediaUrl(option.image_url) ?? undefined}
                  alt={`Option ${option.label}`}
                  className="mt-2 max-w-xs"
                />
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
}
