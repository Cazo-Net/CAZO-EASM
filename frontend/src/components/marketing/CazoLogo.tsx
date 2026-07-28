import Link from "next/link";

/**
 * CAZO logo mark.
 *
 * New design: a teal "C" shape (open perimeter ring) with a small
 * scan node circle on the right opening. Clean, minimal, technical.
 */

export function CazoMark({ className = "h-7 w-7" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 64 64"
      fill="none"
      className={className}
      aria-hidden="true"
      role="img"
    >
      <defs>
        <linearGradient id="cazo-gradient" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
          <stop stopColor="#10B981" />
          <stop offset="1" stopColor="#06B6D4" />
        </linearGradient>
      </defs>
      {/* Main "C" shape - open circle */}
      <path
        d="M44.5 12.8A22 22 0 1 0 52 32"
        stroke="url(#cazo-gradient)"
        strokeWidth="7"
        strokeLinecap="round"
      />
      {/* Small circle on the right */}
      <circle cx="50" cy="28" r="5" fill="url(#cazo-gradient)" />
      {/* Tiny inner dot */}
      <circle cx="50" cy="28" r="2" fill="#09090B" />
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
