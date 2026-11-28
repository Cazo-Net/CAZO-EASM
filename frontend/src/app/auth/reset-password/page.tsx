"use client";

import { Suspense, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { CheckCircle2, Loader2 } from "lucide-react";
import { resetPassword, getErrorMessage } from "@/lib/api";
import { AuthShell, AuthError } from "@/components/auth/AuthShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

function ResetPasswordContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token");

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const validatePassword = (pw: string) => {
    if (pw.length < 8) return "Password must be at least 8 characters";
    if (!/[A-Z]/.test(pw)) return "Password must contain an uppercase letter";
    if (!/[a-z]/.test(pw)) return "Password must contain a lowercase letter";
    if (!/[0-9]/.test(pw)) return "Password must contain a digit";
    if (!/[^A-Za-z0-9]/.test(pw)) return "Password must contain a special character";
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    const pwError = validatePassword(password);
    if (pwError) { setError(pwError); return; }
    if (password !== confirm) { setError("Passwords do not match"); return; }

    setLoading(true);
    try {
      await resetPassword(token!, password);
      setSuccess(true);
      setTimeout(() => router.push("/login"), 3000);
    } catch (err: any) {
      setError(getErrorMessage(err, "Failed to reset password."));
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <AuthShell
        title="This link isn't valid"
        subtitle="The password reset link is invalid or missing its token."
      >
        <Link href="/forgot-password">
          <Button className="h-10 w-full">Request a new link</Button>
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Choose a new password"
      subtitle="At least 8 characters, with upper and lower case, a digit and a symbol."
      footer={
        <p>
          <Link href="/login" className="font-medium text-primary hover:underline">Back to sign in</Link>
        </p>
      }
    >
      {success ? (
        <div className="flex items-start gap-3 rounded-lg border border-border bg-card p-5">
          <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
          <div>
            <p className="text-sm font-medium">Password updated</p>
            <p className="mt-1 text-sm text-muted-foreground">Taking you to sign in…</p>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && <AuthError>{error}</AuthError>}
          <div className="space-y-1.5">
            <label htmlFor="new-password" className="text-sm font-medium">New password</label>
            <Input
              id="new-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              className="h-10"
              placeholder="••••••••"
              required
            />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="confirm-password" className="text-sm font-medium">Confirm password</label>
            <Input
              id="confirm-password"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="new-password"
              className="h-10"
              placeholder="••••••••"
              required
            />
          </div>
          <Button type="submit" disabled={loading} className="h-10 w-full">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Reset password"}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={
      <div className="h-full overflow-y-auto bg-background flex items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    }>
      <ResetPasswordContent />
    </Suspense>
  );
}
