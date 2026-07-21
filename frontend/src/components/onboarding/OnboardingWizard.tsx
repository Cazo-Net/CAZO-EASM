"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Check } from "lucide-react";

interface Step {
  id: string;
  title: string;
  description: string;
}

interface OnboardingWizardProps {
  onComplete?: () => void;
  onSkip?: () => void;
}

const steps: Step[] = [
  { id: "welcome", title: "Welcome to CAZO", description: "Let's get your attack surface monitoring set up." },
  { id: "plan", title: "Choose a Plan", description: "Start with a free trial or pick a plan that fits your team." },
  { id: "scope", title: "Add Your First Scope", description: "Tell us what to monitor — a domain, IP, or CIDR range." },
  { id: "security", title: "Secure Your Account", description: "Enable MFA and review your security settings." },
  { id: "done", title: "You're All Set", description: "Your workspace is ready. Start your first scan!" },
];

export function OnboardingWizard({ onComplete, onSkip }: OnboardingWizardProps) {
  const [currentStep, setCurrentStep] = React.useState(0);
  const [selectedPlan, setSelectedPlan] = React.useState<string>("free_trial");
  const [scope, setScope] = React.useState("");

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

          {step.id === "plan" && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
              {["free_trial", "starter", "professional"].map((plan) => (
                <button
                  key={plan}
                  onClick={() => setSelectedPlan(plan)}
                  className={cn(
                    "p-4 rounded-lg border text-left transition-all",
                    selectedPlan === plan
                      ? "border-brand bg-brand/5 ring-2 ring-brand/20"
                      : "border-border hover:border-brand/50"
                  )}
                >
                  <p className="font-semibold text-foreground capitalize">
                    {plan.replace("_", " ")}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {plan === "free_trial"
                      ? "14-day trial"
                      : plan === "starter"
                      ? "$49/mo"
                      : "$199/mo"}
                  </p>
                </button>
              ))}
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
              <Button onClick={next}>
                {isLast ? "Go to Dashboard" : "Continue"}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
