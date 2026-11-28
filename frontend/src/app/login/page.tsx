"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Loader2, Mail, Lock, Eye, EyeOff, ShieldCheck, KeyRound } from "lucide-react";
import { motion } from "framer-motion";
import { useAuth, hasPendingTwoFactor } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { getErrorMessage, startSso } from "@/lib/api";
import { GoogleButton } from "@/components/auth/GoogleButton";
import { AuthShell } from "@/components/auth/AuthShell";

const SSO_ERRORS: Record<string, string> = {
  expired: "That sign-in attempt expired. Please try again.",
  denied: "Your identity provider did not complete the sign-in.",
  provider:
    "We could not confirm your identity with your provider. Please try again or contact your administrator.",
  domain: "Your identity provider returned an email address that does not belong to this organization.",
  no_account: "You do not have an account in this organization. Ask an administrator to invite you.",
  other_org: "This email address already belongs to a different organization. Contact support to move it.",
  inactive: "Your account is deactivated. Contact your administrator.",
  seats: "Your organization has no free user seats. Contact your administrator.",
  off: "Single sign-on is not available for this organization.",
};

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<"password" | "2fa">("password");
  const [code, setCode] = useState("");
  const { login, verifyTwoFactor, cancelTwoFactor } = useAuth();
  const router = useRouter();

  const [ssoLoading, setSsoLoading] = useState(false);

  // Arriving from Google or single sign-on with 2FA (/login?step=2fa), or
  // from a single sign-on that did not complete (/login?sso_error=...).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("step") === "2fa" && hasPendingTwoFactor()) setStep("2fa");
    const ssoError = params.get("sso_error");
    if (ssoError) {
      setError(SSO_ERRORS[ssoError] || SSO_ERRORS.provider);
      window.history.replaceState(null, "", "/login");
    }
  }, []);

  // Single sign-on needs only the work email; the identity provider does the rest.
  const handleSso = async () => {
    setError("");
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) {
      setError("Enter your work email first, then choose single sign-on.");
      return;
    }
    setSsoLoading(true);
    try {
      window.location.href = await startSso(email.trim());
    } catch (err: any) {
      setError(getErrorMessage(err, "Single sign-on could not be started. Please try again."));
      setSsoLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await login(email, password, rememberMe);
      if (result.requires2fa) {
        setStep("2fa");
        setPassword("");
        return;
      }
      router.push("/dashboard");
    } catch (err: any) {
      setError(getErrorMessage(err, "Invalid email or password"));
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await verifyTwoFactor(code);
      router.push("/dashboard");
    } catch (err: any) {
      const status = err?.response?.status;
      // An expired login step (or a locked account) needs the password again.
      if (status === 401 && /expired/i.test(err?.response?.data?.detail || "")) {
        cancelTwoFactor();
        setStep("password");
      }
      setError(getErrorMessage(err, "Invalid authentication code"));
      setCode("");
    } finally {
      setLoading(false);
    }
  };

  const backToPassword = () => {
    cancelTwoFactor();
    setStep("password");
    setCode("");
    setError("");
  };

  return (
    <AuthShell title="Sign in to CAZO EASM" subtitle="Welcome back. Enter your details to continue.">
        <div>
          {step === "2fa" ? (
            <form onSubmit={handleVerify} className="space-y-4" data-testid="twofa-form">
              {error && (
                <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-sm text-destructive">
                  {error}
                </div>
              )}
              <div className="flex items-start gap-3">
                <ShieldCheck className="mt-0.5 h-5 w-5 text-brand" />
                <div>
                  <p className="text-sm font-medium text-foreground">Two-factor authentication</p>
                  <p className="text-xs text-muted-foreground">
                    Enter the 6-digit code from your authenticator app, or one of your recovery codes.
                  </p>
                </div>
              </div>
              <Input
                type="text"
                inputMode="text"
                autoComplete="one-time-code"
                autoFocus
                placeholder="123456"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
                maxLength={20}
                aria-label="Authentication code"
                className="h-10 text-center font-mono tracking-wide"
              />
              <Button
                type="submit"
                className="h-10 w-full"
                disabled={loading || !code.trim()}
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Verify"}
              </Button>
              <button
                type="button"
                onClick={backToPassword}
                className="w-full text-center text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Use a different account
              </button>
            </form>
          ) : (
          <>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                className="rounded-md border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-sm text-destructive"
              >
                {error}
              </motion.div>
            )}

            <div className="space-y-1.5">
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
                  className="h-10 pl-10"
                />
              </div>
            </div>

            <div className="space-y-1.5">
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
                  className="h-10 pl-10 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label="Show or hide password"
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
              className="h-10 w-full"
              disabled={loading}
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Sign in"
              )}
            </Button>
          </form>

          <Button
            type="button"
            variant="outline"
            className="mt-3 h-10 w-full"
            onClick={handleSso}
            disabled={ssoLoading || loading}
          >
            {ssoLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="mr-2 h-4 w-4" />}
            {!ssoLoading && "Sign in with SSO"}
          </Button>

          <GoogleButton />
          </>
          )}
        </div>

        <p className="mt-6 text-sm text-muted-foreground">
          Don&apos;t have an account?{" "}
          <Link
            href="/register"
            className="font-medium text-primary hover:underline"
          >
            Register
          </Link>
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          <Link
            href="/forgot-password"
            className="font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            Forgot your password?
          </Link>
        </p>
    </AuthShell>
  );
}
