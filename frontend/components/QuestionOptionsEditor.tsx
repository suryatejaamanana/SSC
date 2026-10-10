"use client";

import { resolveMediaUrl } from "@/lib/format";

export type OptionSlots = Record<"A" | "B" | "C" | "D", { text: string; image_url: string }>;

export const EMPTY_OPTION_SLOTS: OptionSlots = {
  A: { text: "", image_url: "" },
  B: { text: "", image_url: "" },
  C: { text: "", image_url: "" },
  D: { text: "", image_url: "" },
};

/** The backend accepts 0-4 options at create/update time (only /publish
 * requires exactly 4) and rejects an option with neither text nor an
 * image_url - so an empty slot here is simply omitted from the payload
 * rather than sent as a blank, invalid option. */
export function buildOptionsPayload(slots: OptionSlots) {
  return (["A", "B", "C", "D"] as const)
    .filter((label) => slots[label].text.trim() || slots[label].image_url.trim())
    .map((label) => ({
      label,
      text: slots[label].text.trim() || null,
      image_url: slots[label].image_url.trim() || null,
    }));
}

const LABELS: Array<keyof OptionSlots> = ["A", "B", "C", "D"];

export default function QuestionOptionsEditor({
  value,
  onChange,
}: {
  value: OptionSlots;
  onChange: (next: OptionSlots) => void;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {LABELS.map((label) => (
        <div key={label} className="rounded-md border border-zinc-200 p-3 dark:border-zinc-800">
          <p className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Option {label}</p>
          <input
            placeholder="Text"
            value={value[label].text}
            onChange={(e) =>
              onChange({ ...value, [label]: { ...value[label], text: e.target.value } })
            }
            className="mt-2 w-full rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
          <input
            placeholder="Image URL (optional)"
            value={value[label].image_url}
            onChange={(e) =>
              onChange({ ...value, [label]: { ...value[label], image_url: e.target.value } })
            }
            className="mt-2 w-full rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
          {value[label].image_url && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={resolveMediaUrl(value[label].image_url) ?? undefined}
              alt={`Option ${label} preview`}
              className="mt-2 max-h-20"
            />
          )}
        </div>
      ))}
    </div>
  );
}
