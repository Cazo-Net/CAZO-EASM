"use client";

import { usePathname } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { ToastProvider } from "@/components/Toast";

const PUBLIC_ROUTES = [
  "/",
  "/home",
  "/login",
  "/register",
  "/forgot-password",
  "/auth/verify-email",
  "/auth/reset-password",
];

export function ClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublic = PUBLIC_ROUTES.includes(pathname);

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
