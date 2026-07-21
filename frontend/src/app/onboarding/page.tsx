"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";
import { useAuth } from "@/contexts/AuthContext";
import { startTrial, listPlans } from "@/lib/api";

export default function OnboardingPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [planId, setPlanId] = useState<string>("free_trial");

  const handleComplete = async () => {
    try {
      if (planId === "free_trial") {
        await startTrial();
      }
    } catch {
      // ignore — trial may already be active
    }
    router.push("/dashboard");
  };

  const handleSkip = () => {
    router.push("/dashboard");
  };

  return (
    <OnboardingWizard
      onComplete={handleComplete}
      onSkip={handleSkip}
    />
  );
}
