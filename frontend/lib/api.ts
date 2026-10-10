// All auth state lives in httpOnly cookies set by the backend - this client
// never reads or stores a token itself, only ever forwards cookies via
// `credentials: "include"`.

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(formatDetail(detail));
    this.status = status;
    this.detail = detail;
  }
}

function formatDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (
    detail &&
    typeof detail === "object" &&
    "errors" in detail &&
    Array.isArray((detail as { errors: unknown }).errors)
  ) {
    return (detail as { errors: string[] }).errors.join(" ");
  }
  return "Something went wrong. Please try again.";
}

let refreshInFlight: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  // Coalesce concurrent 401s into a single refresh call rather than firing
  // one rotation attempt per failed request.
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then((r) => r.ok)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

async function request<T>(path: string, init: RequestInit = {}, allowRetry = true): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });

  if (response.status === 401 && allowRetry && !path.startsWith("/api/v1/auth/")) {
    // The 15-minute access token can expire mid-exam; a long-lived refresh
    // token cookie is the backend's mechanism for exactly this case. Retry
    // the original request once after a successful refresh - never retried
    // more than once, so a genuinely expired session still surfaces as an
    // error instead of looping.
    const refreshed = await refreshSession();
    if (refreshed) {
      return request<T>(path, init, false);
    }
  }

  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // no JSON body to parse
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function toQueryString(params?: Record<string, string | number | boolean | undefined | null>): string {
  if (!params) return "";
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null);
  if (entries.length === 0) return "";
  const search = new URLSearchParams(entries.map(([k, v]) => [k, String(v)]));
  return `?${search.toString()}`;
}

export const api = {
  get: <T>(path: string, params?: Record<string, string | number | boolean | undefined | null>) =>
    request<T>(`${path}${toQueryString(params)}`),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  // Multipart upload (PDF import) - deliberately bypasses the JSON
  // Content-Type header `request` sets by default; the browser sets its own
  // multipart boundary header when given a FormData body.
  postForm: <T>(path: string, formData: FormData) =>
    fetch(`${API_URL}${path}`, { method: "POST", credentials: "include", body: formData }).then(
      async (response) => {
        if (!response.ok) {
          let detail: unknown = response.statusText;
          try {
            detail = (await response.json()).detail ?? detail;
          } catch {
            // no JSON body to parse
          }
          throw new ApiError(response.status, detail);
        }
        return (await response.json()) as T;
      }
    ),
};

/** Publish-validation errors come back as detail: {errors: string[]} rather
 * than a plain string - extract the list for a bulleted display, or null if
 * this wasn't that shape (caller falls back to err.message). */
export function getValidationErrors(err: unknown): string[] | null {
  if (
    err instanceof ApiError &&
    err.detail &&
    typeof err.detail === "object" &&
    "errors" in err.detail &&
    Array.isArray((err.detail as { errors: unknown }).errors)
  ) {
    return (err.detail as { errors: string[] }).errors;
  }
  return null;
}
