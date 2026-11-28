"use client";

import { Suspense, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { verifyEmail, getErrorMessage } from "@/lib/api";
import { AuthShell } from "@/components/auth/AuthShell";
import { Button } from "@/components/ui/button";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("No verification token provided.");
      return;
    }
    verifyEmail(token)
      .then(() => {
        setStatus("success");
        setMessage("Email verified successfully!");
      })
      .catch((err) => {
        setStatus("error");
        setMessage(getErrorMessage(err, "Invalid or expired token."));
      });
  }, [token]);

  if (status === "loading") {
    return (
      <AuthShell title="Verifying your email" subtitle="This only takes a moment.">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </AuthShell>
    );
  }

  const ok = status === "success";
  return (
    <AuthShell
      title={ok ? "Email verified" : "Verification failed"}
      subtitle={ok ? "You can now sign in to your account." : message}
    >
      <div className="mb-5 flex items-center gap-2 text-sm">
        {ok ? (
          <CheckCircle2 className="h-5 w-5 text-success" />
        ) : (
          <XCircle className="h-5 w-5 text-destructive" />
        )}
        <span className="text-muted-foreground">{ok ? message : "The link may have expired or already been used."}</span>
      </div>
      <Link href="/login">
        <Button className="h-10 w-full">Go to sign in</Button>
      </Link>
    </AuthShell>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={
      <div className="h-full overflow-y-auto bg-background flex items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    }>
      <VerifyEmailContent />
    </Suspense>
  );
}
