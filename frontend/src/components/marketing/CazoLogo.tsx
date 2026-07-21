import Link from "next/link";

/**
 * CAZO logo mark.
 *
 * Concept: an open perimeter ring (the external attack surface you can never
 * fully close) that also reads as the "C" in CAZO. A single scan node sits on
 * the ring's opening — the one asset you forgot you own — with a faint radial
 * sweep behind it. Uses phosphor + cyan design tokens.
 */

export function CazoMark({ className = "h-7 w-7" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      aria-hidden="true"
      role="img"
    >
      <defs>
        <linearGradient id="cazo-ring" x1="4" y1="4" x2="28" y2="28" gradientUnits="userSpaceOnUse">
          <stop stopColor="#00FF88" />
          <stop offset="1" stopColor="#00D4FF" />
        </linearGradient>
        <radialGradient id="cazo-sweep" cx="0.5" cy="0.5" r="0.5">
          <stop stopColor="#00FF88" stopOpacity="0.35" />
          <stop offset="1" stopColor="#00FF88" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* faint sweep glow */}
      <circle cx="16" cy="16" r="13" fill="url(#cazo-sweep)" />

      {/* open perimeter ring — the "C" */}
      <path
        d="M23.5 7.6A11 11 0 1 0 27 16"
        stroke="url(#cazo-ring)"
        strokeWidth="2.4"
        strokeLinecap="round"
      />

      {/* inner tick marks — radar bearings */}
      <path d="M16 4.5v2.2" stroke="#00FF88" strokeWidth="1.6" strokeLinecap="round" opacity="0.5" />
      <path d="M27.5 16h-2.2" stroke="#00D4FF" strokeWidth="1.6" strokeLinecap="round" opacity="0.5" />

      {/* the scan node sitting on the ring opening */}
      <circle cx="27" cy="16" r="2.6" fill="#00FF88" />
      <circle cx="27" cy="16" r="4.4" stroke="#00FF88" strokeWidth="1" opacity="0.35" />
    </svg>
  );
}

export function CazoLogo({
  href = "/",
  markClassName = "h-7 w-7",
  wordClassName = "font-display text-lg font-semibold text-foreground",
  showWord = true,
}: {
  href?: string;
  markClassName?: string;
  wordClassName?: string;
  showWord?: boolean;
}) {
  return (
    <Link href={href} className="flex items-center gap-2" aria-label="CAZO home">
      <CazoMark className={markClassName} />
      {showWord && <span className={wordClassName}>CAZO</span>}
    </Link>
  );
}
