"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import AdminNavbar from "@/components/AdminNavbar";
import Spinner from "@/components/Spinner";

// Requires role === "admin" specifically, not just any authenticated user -
// a student session fails this check and is redirected away, same as the
// backend's require_role("admin") rejects it with 403 if it ever tried the
// API directly.
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
    } else if (user.role !== "admin") {
      router.replace("/exams");
    }
  }, [loading, user, router]);

  if (loading) return <Spinner />;
  if (!user || user.role !== "admin") return null; // redirect effect is in flight

  return (
    <div className="flex min-h-full flex-1 flex-col">
      <AdminNavbar />
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6">{children}</main>
    </div>
  );
}
