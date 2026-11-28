"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

export default function SsoCallbackPage() {
  const router = useRouter();
  const { loginWithSso } = useAuth();
  const [error, setError] = useState("");

  useEffect(() => {
    // The one-time code arrives in the URL fragment, which is never sent to a
    // server. Remove it from the address bar before doing anything else.
    const code = new URLSearchParams(window.location.hash.replace(/^#/, "")).get("code");
    window.history.replaceState(null, "", window.location.pathname);
    if (!code) {
      setError("This sign-in link is not valid. Please sign in again.");
      return;
    }
    loginWithSso(code)
      .then((result) => router.push(result.requires2fa ? "/login?step=2fa" : "/dashboard"))
      .catch((err: any) => {
        setError(err?.response?.data?.detail || "Single sign-on failed. Please try again.");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="w-full max-w-sm space-y-4 rounded-xl border border-border bg-card p-6 text-center shadow-2xl shadow-black/20">
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
          <a href="/login" className="inline-block text-sm font-medium text-brand transition-colors hover:text-brand/80">
            Back to login
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-brand" />
        <p className="text-sm text-muted-foreground">Signing you in...</p>
      </div>
    </div>
  );
}
