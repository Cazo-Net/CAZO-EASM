"use client";

import { Suspense, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { verifyEmail } from "@/lib/api";

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
        setMessage(err.response?.data?.detail || "Invalid or expired token.");
      });
  }, [token]);

  return (
    <div className="min-h-screen bg-[#09090B] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-[#111827] rounded-xl border border-[#1F2937] p-8 text-center">
          {status === "loading" && (
            <div className="flex flex-col items-center gap-4">
              <div className="w-12 h-12 border-4 border-[#2563EB] border-t-transparent rounded-full animate-spin" />
              <p className="text-[#9CA3AF]">Verifying your email...</p>
            </div>
          )}

          {status === "success" && (
            <div className="flex flex-col items-center gap-4">
              <div className="w-16 h-16 rounded-full bg-[#059669]/10 flex items-center justify-center">
                <svg className="w-8 h-8 text-[#059669]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h1 className="text-xl font-semibold text-white">{message}</h1>
              <p className="text-[#9CA3AF]">You can now log in to your account.</p>
              <Link
                href="/login"
                className="mt-4 px-6 py-3 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg transition font-medium"
              >
                Go to Login
              </Link>
            </div>
          )}

          {status === "error" && (
            <div className="flex flex-col items-center gap-4">
              <div className="w-16 h-16 rounded-full bg-[#EF4444]/10 flex items-center justify-center">
                <svg className="w-8 h-8 text-[#EF4444]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <h1 className="text-xl font-semibold text-white">Verification Failed</h1>
              <p className="text-[#9CA3AF]">{message}</p>
              <Link
                href="/login"
                className="mt-4 px-6 py-3 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg transition font-medium"
              >
                Go to Login
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#09090B] flex items-center justify-center">
        <div className="w-12 h-12 border-4 border-[#2563EB] border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <VerifyEmailContent />
    </Suspense>
  );
}
