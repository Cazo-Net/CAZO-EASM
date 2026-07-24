"use client";

import { useRouter } from "next/navigation";
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";
import { useAuth } from "@/contexts/AuthContext";

export default function OnboardingPage() {
  const router = useRouter();
  const { refreshUser } = useAuth();

  const handleComplete = async () => {
    router.push("/dashboard");
  };

  const handleSkip = () => {
    router.push("/dashboard");
  };

  const handleOrgCreated = async () => {
    await refreshUser();
  };

  return (
    <OnboardingWizard
      onComplete={handleComplete}
      onSkip={handleSkip}
      onOrgCreated={handleOrgCreated}
    />
  );
}
