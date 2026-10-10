"use client";

export interface PaletteItem {
  questionId: number;
  answered: boolean;
  markedForReview: boolean;
}

export default function QuestionPalette({
  items,
  currentIndex,
  onSelect,
}: {
  items: PaletteItem[];
  currentIndex: number;
  onSelect: (index: number) => void;
}) {
  return (
    <div className="grid grid-cols-5 gap-2 sm:grid-cols-4">
      {items.map((item, index) => {
        const isCurrent = index === currentIndex;
        let classes =
          "flex h-9 w-9 items-center justify-center rounded-md text-sm font-medium border transition-colors ";
        if (item.markedForReview) {
          classes += "bg-amber-100 border-amber-400 text-amber-800 dark:bg-amber-950 dark:border-amber-700 dark:text-amber-300";
        } else if (item.answered) {
          classes += "bg-emerald-100 border-emerald-400 text-emerald-800 dark:bg-emerald-950 dark:border-emerald-700 dark:text-emerald-300";
        } else {
          classes += "bg-zinc-100 border-zinc-300 text-zinc-700 dark:bg-zinc-800 dark:border-zinc-700 dark:text-zinc-300";
        }
        if (isCurrent) {
          classes += " ring-2 ring-offset-1 ring-zinc-900 dark:ring-zinc-100";
        }

        return (
          <button
            key={item.questionId}
            type="button"
            onClick={() => onSelect(index)}
            aria-label={`Question ${index + 1}`}
            aria-current={isCurrent ? "true" : undefined}
            className={classes}
          >
            {index + 1}
          </button>
        );
      })}
    </div>
  );
}
