import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Optimistic, edge-only check: presence of the access_token cookie, nothing
// more. It cannot verify the JWT's signature or expiry (the backend remains
// the sole source of truth for that), but it stops an unauthenticated
// browser from ever rendering a protected page, avoiding a flash of
// protected content before the client-side auth check redirects. An expired
// or otherwise invalid cookie still gets caught by AuthProvider's
// client-side /auth/me check and the (student) layout's redirect.
export function proxy(request: NextRequest) {
  const hasAccessToken = request.cookies.has("access_token");
  if (!hasAccessToken) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/exams/:path*",
    "/practice/:path*",
    "/attempts/:path*",
    "/history/:path*",
    "/admin/:path*",
  ],
};
