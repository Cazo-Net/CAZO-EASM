"use client";

import { useRouter } from "next/navigation";
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";
import { useAuth } from "@/contexts/AuthContext";

export default function OnboardingPage() {
  const router = useRouter();
  const { refreshUser } = useAuth();

  const handleSkip = () => {
    router.push("/dashboard");
  };

  const handleOrgCreated = async () => {
    await refreshUser();
  };

  return (
    <OnboardingWizard
      onSkip={handleSkip}
      onOrgCreated={handleOrgCreated}
    />
  );
}
