import { getValidationErrors } from "@/lib/api";
import ErrorMessage from "./ErrorMessage";

/** Renders a bulleted list when the error is the backend's {errors: [...]}
 * publish-validation shape, otherwise falls back to a plain ErrorMessage. */
export default function ErrorDisplay({ error, title }: { error: unknown; title?: string }) {
  const errors = getValidationErrors(error);
  if (errors) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
        {title && <p className="font-medium">{title}</p>}
        <ul className="list-disc space-y-0.5 pl-5">
          {errors.map((e, i) => (
            <li key={i}>{e}</li>
          ))}
        </ul>
      </div>
    );
  }
  return <ErrorMessage message={error instanceof Error ? error.message : "Something went wrong"} />;
}
