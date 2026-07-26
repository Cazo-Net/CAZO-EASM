"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Loader2, Mail, Lock, Eye, EyeOff } from "lucide-react";
import { motion } from "framer-motion";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { getErrorMessage } from "@/lib/api";
import { GoogleButton } from "@/components/auth/GoogleButton";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password, rememberMe);
      router.push("/dashboard");
    } catch (err: any) {
      setError(getErrorMessage(err, "Invalid email or password"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative h-full flex items-center justify-center bg-[#09090B] px-4 overflow-y-auto">
      {/* Background effects */}
      <div className="absolute inset-0">
        <div className="absolute inset-0 bg-[linear-gradient(rgba(0,212,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(0,212,255,0.03)_1px,transparent_1px)] bg-[size:64px_64px]" />
        <div className="absolute top-1/4 left-1/4 h-96 w-96 rounded-full bg-brand/5 blur-[128px]" />
        <div className="absolute bottom-1/4 right-1/4 h-96 w-96 rounded-full bg-cyan-400/5 blur-[128px]" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="relative w-full max-w-sm"
      >
        {/* Brand */}
        <div className="flex flex-col items-center mb-8">
          <div className="relative mb-5">
            <div className="absolute inset-0 rounded-2xl gradient-brand opacity-60 blur-lg" />
            <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-[#09090B] border border-border/50 shadow-xl overflow-hidden">
              <img src="/icon.ico" alt="CAZO EASM" className="h-11 w-11 object-contain" />
            </div>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground font-display">
            CAZO EASM
          </h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            Welcome back
          </p>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-border/50 bg-card/80 backdrop-blur-xl p-6 shadow-2xl shadow-black/20">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400"
              >
                {error}
              </motion.div>
            )}

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Email
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                  className="h-11 pl-10 bg-muted/30 border-border/50 focus:border-brand/50 focus:ring-brand/20"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  className="h-11 pl-10 pr-10 bg-muted/30 border-border/50 focus:border-brand/50 focus:ring-brand/20"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="h-4 w-4 rounded border-border bg-muted/30 text-brand focus:ring-brand/30"
                />
                <span className="text-sm text-muted-foreground">
                  Remember me
                </span>
              </label>
            </div>

            <Button
              type="submit"
              className="w-full h-11 gradient-brand hover:opacity-90 text-primary-foreground font-medium shadow-lg shadow-brand/25 transition-all"
              disabled={loading}
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Sign In"
              )}
            </Button>
          </form>

          <GoogleButton />
        </div>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          Don&apos;t have an account?{" "}
          <Link
            href="/register"
            className="font-medium text-brand hover:text-brand/80 transition-colors"
          >
            Register
          </Link>
        </p>
        <p className="mt-2 text-center text-sm text-muted-foreground">
          <Link
            href="/forgot-password"
            className="font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            Forgot your password?
          </Link>
        </p>
      </motion.div>
    </div>
  );
}
