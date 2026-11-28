"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import {
  Check,
  Building,
  Loader2,
  Shield,
  Globe,
  ExternalLink,
} from "lucide-react";
import { createOrganization, createScope } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

interface Step {
  id: string;
  title: string;
  description: string;
}

interface OnboardingWizardProps {
  onComplete?: () => void;
  onSkip?: () => void;
  onOrgCreated?: () => void;
}

const steps: Step[] = [
  { id: "welcome", title: "Welcome to CAZO", description: "Your external footprint, mapped. One domain to start — we'll show you what's out there." },
  { id: "organization", title: "Create Your Organization", description: "Where your scans, findings, and team live. Name it after your team or project." },
  { id: "scope", title: "Add Your First Scope", description: "One domain, IP, or CIDR. You can add more later — start with whatever you're most worried about." },
  { id: "security", title: "Secure Your Account", description: "MFA takes 30 seconds and keeps your findings out of the wrong hands." },
  { id: "done", title: "You're All Set", description: "Your workspace is live. Your first scan will start automatically." },
];

export function OnboardingWizard({ onComplete, onSkip, onOrgCreated }: OnboardingWizardProps) {
  const router = useRouter();
  const { refreshUser, updateOnboardingState } = useAuth();
  const [currentStep, setCurrentStep] = React.useState(0);
  const [scope, setScope] = React.useState("");
  const [scopeAuthConfirmed, setScopeAuthConfirmed] = React.useState(false);
  const [orgName, setOrgName] = React.useState("");
  const [creatingOrg, setCreatingOrg] = React.useState(false);
  const [orgError, setOrgError] = React.useState("");
  const [savingScope, setSavingScope] = React.useState(false);
  const [scopeError, setScopeError] = React.useState("");

  const step = steps[currentStep];
  const isLast = currentStep === steps.length - 1;

  const next = () => {
    if (isLast) {
      router.push("/onboarding/first-scan");
    } else {
      setCurrentStep((s) => s + 1);
    }
  };

  const prev = () => setCurrentStep((s) => Math.max(0, s - 1));

  async function handleCreateOrg() {
    if (!orgName.trim()) return;
    setCreatingOrg(true);
    setOrgError("");
    try {
      await createOrganization({ name: orgName.trim() });
      onOrgCreated?.();
      next();
    } catch {
      setOrgError("Couldn't create organization. Check the name and try again.");
    } finally {
      setCreatingOrg(false);
    }
  }

  async function handleSaveScopeAndContinue() {
    if (!scope.trim() || !scopeAuthConfirmed) return;
    setSavingScope(true);
    setScopeError("");
    try {
      const result = await createScope("domain", scope.trim(), "Added during onboarding");
      await updateOnboardingState({
        first_scan_domain: scope.trim(),
      });
      next();
    } catch (e: any) {
      setScopeError(
        e?.response?.data?.detail || "Couldn't save scope. Check the domain and try again."
      );
    } finally {
      setSavingScope(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="relative w-full max-w-2xl border-border bg-card shadow-2xl shadow-black/20">
        <CardContent className="p-5 sm:p-8">
          {/* Progress */}
          <div className="flex items-center justify-between mb-8">
            {steps.map((s, i) => (
              <React.Fragment key={s.id}>
                <div className="flex flex-col items-center">
                  <div
                    className={cn(
                      "w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-colors",
                      i < currentStep && "bg-brand text-white",
                      i === currentStep && "bg-brand text-white ring-4 ring-brand/20",
                      i > currentStep && "bg-muted text-muted-foreground"
                    )}
                  >
                    {i < currentStep ? <Check className="w-4 h-4" /> : i + 1}
                  </div>
                </div>
                {i < steps.length - 1 && (
                  <div
                    className={cn(
                      "flex-1 h-0.5 mx-2 transition-colors",
                      i < currentStep ? "bg-brand" : "bg-muted"
                    )}
                  />
                )}
              </React.Fragment>
            ))}
          </div>

          {/* Step content */}
          <div className="text-center mb-8">
            <h2 className="text-2xl font-semibold text-foreground mb-2">{step.title}</h2>
            <p className="text-muted-foreground">{step.description}</p>
          </div>

          {step.id === "security" && (
            <div className="mb-6 rounded-lg border border-border bg-muted/40 p-4 flex items-start gap-3">
              <Shield className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" />
              <p className="text-sm text-muted-foreground">
                You can set up MFA from <strong>Settings → Security</strong> after you sign in. It&apos;s quick — we recommend doing it before your first scan.
              </p>
            </div>
          )}

          {step.id === "organization" && (
            <div className="mb-6 space-y-4">
              <div className="rounded-lg border border-border bg-muted/40 p-4 flex items-start gap-3">
                <Building className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" />
                <p className="text-sm text-muted-foreground">
                  You&apos;ll be the <strong>Owner</strong> — full access to scans, settings, and team members.
                </p>
              </div>
              <div>
                <label className="text-sm font-medium text-foreground block mb-2">
                  Organization Name
                </label>
                <Input
                  type="text"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCreateOrg()}
                  placeholder="acme-security"
                  className="h-11 bg-muted/30 border-border focus:border-phosphor/50 focus:ring-phosphor/20"
                />
              </div>
              {orgError && (
                <p className="text-sm text-destructive">{orgError}</p>
              )}
            </div>
          )}

          {step.id === "scope" && (
            <div className="mb-6 space-y-4">
              <div className="rounded-lg border border-border bg-muted/40 p-4 flex items-start gap-3">
                <Globe className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" />
                <p className="text-sm text-muted-foreground">
                  CAZO works from the outside — no agents, no VPNs. Just point it at a domain.
                </p>
              </div>
              <div>
                <label className="text-sm font-medium text-foreground block mb-2">
                  Domain or IP to monitor
                </label>
                <Input
                  type="text"
                  value={scope}
                  onChange={(e) => setScope(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && scopeAuthConfirmed && handleSaveScopeAndContinue()}
                  placeholder="example.com"
                  className="h-11 bg-muted/30 border-border focus:border-phosphor/50 focus:ring-phosphor/20"
                />
              </div>

              <div className="rounded-lg border border-border bg-muted/40 p-3">
                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={scopeAuthConfirmed}
                    onChange={(e) => setScopeAuthConfirmed(e.target.checked)}
                    className="mt-0.5 h-4 w-4 rounded border-border bg-muted/30 text-phosphor focus:ring-phosphor/30"
                  />
                  <span className="text-sm text-muted-foreground">
                    I confirm I have authorization to scan this target and have read
                    the{" "}
                    <a
                      href="/legal/authorized-scanning"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-phosphor hover:underline"
                    >
                      Authorized Scanning Policy
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  </span>
                </label>
              </div>

              {scopeError && (
                <p className="text-sm text-destructive">{scopeError}</p>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-between">
            <div>
              {currentStep > 0 && (
                <Button variant="ghost" onClick={prev}>
                  Back
                </Button>
              )}
            </div>
            <div className="flex items-center gap-2">
              {onSkip && (
                <Button variant="ghost" onClick={onSkip}>
                  Skip
                </Button>
              )}
              {step.id === "organization" ? (
                <Button onClick={handleCreateOrg} disabled={creatingOrg || !orgName.trim()}>
                  {creatingOrg ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                  ) : null}
                  {creatingOrg ? "Creating..." : "Create & Continue"}
                </Button>
              ) : step.id === "scope" ? (
                <Button
                  onClick={handleSaveScopeAndContinue}
                  disabled={savingScope || !scope.trim() || !scopeAuthConfirmed}
                >
                  {savingScope ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                  ) : null}
                  {savingScope ? "Saving..." : isLast ? "Go to Dashboard" : "Save Scope & Continue"}
                </Button>
              ) : (
                <Button onClick={next}>
                  {isLast ? "Go to Dashboard" : "Continue"}
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
