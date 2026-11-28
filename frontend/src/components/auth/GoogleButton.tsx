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

  if (state === "off") {
    // Production: nothing is shown until Google sign-in is configured.
    // Development: show where the button will sit and how to turn it on.
    if (process.env.NODE_ENV === "production") return null;
    return (
      <div className="mt-6">
        <Divider />
        <button
          type="button"
          disabled
          title="Set GOOGLE_CLIENT_ID on the backend to enable"
          className="mt-4 flex h-10 w-full cursor-not-allowed items-center justify-center gap-3 rounded-md border border-border bg-[#131314] text-sm font-medium text-[#E3E3E3]"
        >
          <GoogleG />
          {mode === "login" ? "Sign in with Google" : "Sign up with Google"}
        </button>
        <p className="mt-2 text-center text-xs text-muted-foreground">
          Preview only. Set <code className="font-mono">GOOGLE_CLIENT_ID</code> on the backend to turn this on.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-6" hidden={state === "checking"}>
      <Divider />
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

function Divider() {
  return (
    <div className="relative">
      <div className="absolute inset-0 flex items-center" aria-hidden="true">
        <div className="w-full border-t border-border" />
      </div>
      <div className="relative flex justify-center text-xs uppercase">
        <span className="bg-background px-2 text-muted-foreground">or</span>
      </div>
    </div>
  );
}

function GoogleG() {
  return (
    <svg className="h-[18px] w-[18px]" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
    </svg>
  );
}
