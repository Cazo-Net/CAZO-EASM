"use client";

import { Suspense, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { resetPassword } from "@/lib/api";

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
      setError(err.response?.data?.detail || "Failed to reset password.");
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen bg-[#09090B] flex items-center justify-center p-4">
        <div className="bg-[#111827] rounded-xl border border-[#1F2937] p-8 text-center max-w-md">
          <h1 className="text-xl font-semibold text-white mb-2">Invalid Link</h1>
          <p className="text-[#9CA3AF] mb-4">This password reset link is invalid or missing a token.</p>
          <Link href="/forgot-password" className="text-[#2563EB] hover:underline">Request a new link</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#09090B] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-white">Reset Password</h1>
          <p className="text-[#9CA3AF] mt-2">Enter your new password below.</p>
        </div>

        <div className="bg-[#111827] rounded-xl border border-[#1F2937] p-8">
          {success ? (
            <div className="text-center flex flex-col items-center gap-4">
              <div className="w-16 h-16 rounded-full bg-[#059669]/10 flex items-center justify-center">
                <svg className="w-8 h-8 text-[#059669]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="text-lg font-semibold text-white">Password Reset!</h2>
              <p className="text-[#9CA3AF]">Redirecting to login...</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="p-3 bg-[#EF4444]/10 border border-[#EF4444]/30 rounded-lg text-[#FCA5A5] text-sm">
                  {error}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-[#D1D5DB] mb-1">New Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-4 py-3 bg-[#09090B] border border-[#1F2937] rounded-lg text-white focus:border-[#2563EB] focus:outline-none"
                  placeholder="••••••••"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-[#D1D5DB] mb-1">Confirm Password</label>
                <input
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  className="w-full px-4 py-3 bg-[#09090B] border border-[#1F2937] rounded-lg text-white focus:border-[#2563EB] focus:outline-none"
                  placeholder="••••••••"
                  required
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 bg-[#2563EB] hover:bg-[#1D4ED8] disabled:opacity-50 text-white rounded-lg transition font-medium"
              >
                {loading ? "Resetting..." : "Reset Password"}
              </button>
            </form>
          )}
        </div>

        <p className="text-center mt-4 text-[#9CA3AF] text-sm">
          <Link href="/login" className="text-[#2563EB] hover:underline">Back to Login</Link>
        </p>
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#09090B] flex items-center justify-center">
        <div className="w-12 h-12 border-4 border-[#2563EB] border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <ResetPasswordContent />
    </Suspense>
  );
}
