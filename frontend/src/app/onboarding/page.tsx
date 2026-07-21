"use client";

import { useRouter } from "next/navigation";
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";

export default function OnboardingPage() {
  const router = useRouter();

  const handleComplete = async () => {
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
