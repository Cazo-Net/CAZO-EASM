"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Check, Building, Loader2 } from "lucide-react";
import { createOrganization } from "@/lib/api";

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
  { id: "welcome", title: "Welcome to CAZO", description: "Let's get your attack surface monitoring set up." },
  { id: "organization", title: "Create Your Organization", description: "Set up your team workspace to enable scanning and collaboration." },
  { id: "scope", title: "Add Your First Scope", description: "Tell us what to monitor — a domain, IP, or CIDR range." },
  { id: "security", title: "Secure Your Account", description: "Enable MFA and review your security settings." },
  { id: "done", title: "You're All Set", description: "Your workspace is ready. Start your first scan!" },
];

export function OnboardingWizard({ onComplete, onSkip, onOrgCreated }: OnboardingWizardProps) {
  const [currentStep, setCurrentStep] = React.useState(0);
  const [scope, setScope] = React.useState("");
  const [orgName, setOrgName] = React.useState("");
  const [creatingOrg, setCreatingOrg] = React.useState(false);
  const [orgError, setOrgError] = React.useState("");

  const step = steps[currentStep];
  const isLast = currentStep === steps.length - 1;

  const next = () => {
    if (isLast) {
      onComplete?.();
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
      setOrgError("Failed to create organization. Please try again.");
    } finally {
      setCreatingOrg(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background to-muted/50 p-4">
      <Card className="w-full max-w-2xl">
        <CardContent className="p-8">
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
            <h2 className="text-2xl font-bold text-foreground mb-2">{step.title}</h2>
            <p className="text-muted-foreground">{step.description}</p>
          </div>

          {step.id === "organization" && (
            <div className="mb-6 space-y-4">
              <div className="rounded-lg border border-brand/20 bg-brand/5 p-4 flex items-start gap-3">
                <Building className="h-5 w-5 text-brand mt-0.5 shrink-0" />
                <p className="text-sm text-muted-foreground">
                  Creating an organization gives you the <strong>Owner</strong> role with full permissions to create scans and manage your attack surface.
                </p>
              </div>
              <div>
                <label className="text-sm font-medium text-foreground block mb-2">
                  Organization Name
                </label>
                <input
                  type="text"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCreateOrg()}
                  placeholder="My Security Team"
                  className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                />
              </div>
              {orgError && (
                <p className="text-sm text-destructive">{orgError}</p>
              )}
            </div>
          )}

          {step.id === "scope" && (
            <div className="mb-6">
              <label className="text-sm font-medium text-foreground block mb-2">
                Domain or IP to monitor
              </label>
              <input
                type="text"
                value={scope}
                onChange={(e) => setScope(e.target.value)}
                placeholder="example.com"
                className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
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
                  {creatingOrg ? "Creating..." : "Create Organization"}
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
