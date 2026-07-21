"use client";

import { useEffect, useState } from "react";

const SESSION_STORAGE_KEY = "cazo-animated";

/**
 * Returns true if entrance animations should play.
 * First mount in a session → plays animations, then sets flag.
 * Subsequent mounts (navigation back) → returns false immediately.
 */
export function useSessionAnimation() {
  const [shouldAnimate, setShouldAnimate] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const alreadyAnimated = sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (!alreadyAnimated) {
      sessionStorage.setItem(SESSION_STORAGE_KEY, "1");
      setShouldAnimate(true);
    }
    // else: shouldAnimate stays false, no animations play
  }, []);

  return shouldAnimate;
}
