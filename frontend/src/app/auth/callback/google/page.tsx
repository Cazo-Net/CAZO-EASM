"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

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
      .then((result) => {
        router.push(result.requires2fa ? "/login?step=2fa" : "/dashboard");
      })
      .catch((err: any) => {
        setError(err?.response?.data?.detail || "Google sign-in failed. Please try again.");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) {
    return (
      <div className="relative h-full flex items-center justify-center bg-[#09090B] px-4">
        <div className="rounded-2xl border border-border/50 bg-card/80 backdrop-blur-xl p-6 shadow-2xl shadow-black/20 max-w-sm w-full text-center space-y-4">
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
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
    <div className="relative h-full flex items-center justify-center bg-[#09090B] px-4">
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
        <div className="relative h-full flex items-center justify-center bg-[#09090B] px-4">
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
