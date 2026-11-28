"use client";

import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useRouter } from "next/navigation";
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard";
import { useAuth } from "@/contexts/AuthContext";

function OnboardingContent() {
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

export default function OnboardingPage() {
  return (
    <ProtectedRoute>
      <OnboardingContent />
    </ProtectedRoute>
  );
}
