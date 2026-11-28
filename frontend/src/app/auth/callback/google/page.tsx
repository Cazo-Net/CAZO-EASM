"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { authFetch } from "@/lib/api";

function GoogleCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { loginWithGoogle } = useAuth();
  const [error, setError] = useState("");

  useEffect(() => {
    // Accept credential from query (legacy) or from hidden form POST
    let credential = searchParams.get("credential");

    // If no query param, check for form-posted credential in session
    if (!credential) {
      try {
        const pending = sessionStorage.getItem("_g_credential");
        if (pending) {
          credential = pending;
          sessionStorage.removeItem("_g_credential");
        }
      } catch {}
    }

    if (!credential) {
      setError("No credential received from Google");
      return;
    }

    loginWithGoogle(credential)
      .then(async (result) => {
        if (result.requires2fa) {
          router.push("/login?step=2fa");
          return;
        }
        // A first-time Google user has no organization yet: send them to setup.
        let hasOrg = true;
        try {
          const res = await authFetch("/api/v1/auth/me");
          if (res.ok) hasOrg = !!(await res.json())?.organization_id;
        } catch {}
        router.push(hasOrg ? "/dashboard" : "/onboarding");
      })
      .catch((err: any) => {
        setError(err?.response?.data?.detail || "Google sign-in failed. Please try again.");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="rounded-xl border border-border bg-card p-6 shadow-2xl shadow-black/20 max-w-sm w-full text-center space-y-4">
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
          <a
            href="/login"
            className="inline-block text-sm font-medium text-brand hover:text-brand/80 transition-colors"
          >
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
        <p className="text-sm text-muted-foreground">Signing in with Google...</p>
      </div>
    </div>
  );
}

export default function GoogleCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-background px-4">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-brand" />
            <p className="text-sm text-muted-foreground">Loading...</p>
          </div>
        </div>
      }
    >
      <GoogleCallbackContent />
    </Suspense>
  );
}
