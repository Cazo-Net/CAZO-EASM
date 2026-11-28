"use client";

import { usePathname } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { ToastProvider } from "@/components/Toast";

const PUBLIC_ROUTES = [
  "/",
  "/login",
  "/register",
  "/pricing",
  "/forgot-password",
  "/auth/verify-email",
  "/auth/reset-password",
];

export function ClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  // Onboarding is a focused setup flow, so it runs without the app sidebar.
  const isPublic = PUBLIC_ROUTES.includes(pathname) || pathname.startsWith("/onboarding");

  return (
    <ToastProvider>
      {isPublic ? (
        <>{children}</>
      ) : (
        <AppShell>{children}</AppShell>
      )}
    </ToastProvider>
  );
}
