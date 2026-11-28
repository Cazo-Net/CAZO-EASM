import Link from "next/link";

/**
 * CAZO EASM logo mark: an open perimeter. A hexagon with one edge missing
 * reads as a "C"; the dot is the asset inside it. The gap is the exposure
 * the product exists to find.
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
        <linearGradient id="cazo-gradient" x1="8" y1="6" x2="56" y2="58" gradientUnits="userSpaceOnUse">
          <stop stopColor="#5B9BFF" />
          <stop offset="1" stopColor="#2563EB" />
        </linearGradient>
      </defs>
      <path
        d="M52.78 44.00 L32.00 56.00 L11.22 44.00 L11.22 20.00 L32.00 8.00 L52.78 20.00"
        stroke="url(#cazo-gradient)"
        strokeWidth="6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="32" cy="32" r="5.5" fill="url(#cazo-gradient)" />
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
    <Link href={href} className="flex items-center gap-2" aria-label="CAZO EASM home">
      <CazoMark className={markClassName} />
      {showWord && (
        <span className={wordClassName}>
          CAZO <span className="font-medium text-muted-foreground">EASM</span>
        </span>
      )}
    </Link>
  );
}
