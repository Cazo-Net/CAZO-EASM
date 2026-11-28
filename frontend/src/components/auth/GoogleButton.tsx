"use client";

import { useEffect, useRef, useState } from "react";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: any) => void;
          renderButton: (element: HTMLElement, config: any) => void;
          prompt: (callback?: (notification: any) => void) => void;
        };
      };
    };
  }
}

interface GoogleButtonProps {
  mode?: "login" | "register";
  onError?: (error: string) => void;
}

const GSI_SRC = "https://accounts.google.com/gsi/client";

/**
 * Which Google client ID to use, or null when Google sign-in is off.
 * The backend is asked first, so setting GOOGLE_CLIENT_ID there is enough.
 * NEXT_PUBLIC_GOOGLE_CLIENT_ID is the fallback when the backend cannot say.
 */
async function resolveClientId(): Promise<string | null> {
  try {
    const res = await fetch("/api/v1/auth/google/config");
    if (res.ok) {
      const data = await res.json();
      if (data?.enabled && data.client_id) return data.client_id as string;
      if (data && data.enabled === false) return null;
    }
  } catch {
    // Fall through to the build-time value.
  }
  return process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || null;
}

function loadGsi(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) return resolve();
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GSI_SRC}"]`);
    const script = existing ?? document.createElement("script");
    script.addEventListener("load", () => resolve(), { once: true });
    script.addEventListener("error", () => reject(new Error("load")), { once: true });
    if (!existing) {
      script.src = GSI_SRC;
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }
  });
}

/**
 * "Sign in with Google", using Google's own rendered button. Renders nothing
 * until a client ID is configured, so the feature stays off by default.
 */
export function GoogleButton({ mode = "login", onError }: GoogleButtonProps) {
  const slot = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"checking" | "off" | "ready" | "failed">("checking");

  useEffect(() => {
    let cancelled = false;

    (async () => {
      const clientId = await resolveClientId();
      if (cancelled) return;
      if (!clientId) {
        setState("off");
        return;
      }
      try {
        await loadGsi();
      } catch {
        if (!cancelled) {
          setState("failed");
          onError?.("Google sign-in could not be loaded. Check your connection or ad blocker.");
        }
        return;
      }
      if (cancelled || !slot.current || !window.google?.accounts?.id) return;

      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: (response: { credential?: string }) => {
          if (!response?.credential) {
            onError?.("Google did not return a sign-in. Please try again.");
            return;
          }
          // Kept in sessionStorage for the hop to the callback page, so the
          // token never appears in the address bar or browser history.
          try {
            sessionStorage.setItem("_g_credential", response.credential);
          } catch {}
          window.location.href = "/auth/callback/google";
        },
        auto_select: false,
        ux_mode: "popup",
      });
      window.google.accounts.id.renderButton(slot.current, {
        type: "standard",
        theme: document.documentElement.classList.contains("dark") ? "filled_black" : "outline",
        size: "large",
        shape: "rectangular",
        text: mode === "login" ? "signin_with" : "signup_with",
        logo_alignment: "center",
        width: Math.min(400, Math.max(200, Math.floor(slot.current.offsetWidth))),
      });
      setState("ready");
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  if (state === "off") return null;

  return (
    <div className="mt-6" hidden={state === "checking"}>
      <div className="relative">
        <div className="absolute inset-0 flex items-center" aria-hidden="true">
          <div className="w-full border-t border-border" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-background px-2 text-muted-foreground">or</span>
        </div>
      </div>
      {/* Google draws its button into this element. */}
      <div ref={slot} className="mt-4 flex min-h-[44px] w-full justify-center" />
      {state === "failed" && (
        <p className="mt-2 text-center text-xs text-muted-foreground">
          Google sign-in is unavailable right now. Use your email and password instead.
        </p>
      )}
    </div>
  );
}
