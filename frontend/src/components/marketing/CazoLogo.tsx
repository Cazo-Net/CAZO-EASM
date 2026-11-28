/* eslint-disable @next/next/no-img-element */
import Link from "next/link";

/**
 * CAZO EASM logo mark: a fractured hexagon that reads as a "C", with a shield
 * and network nodes on its edge. The artwork lives in `public/logo.svg` (it is
 * too detailed to inline) and is shared with the favicon.
 */

export function CazoMark({ className = "h-9 w-9" }: { className?: string }) {
  return <img src="/logo.svg" alt="" aria-hidden="true" draggable={false} className={`select-none ${className}`} />;
}

export function CazoLogo({
  href = "/",
  markClassName = "h-9 w-9",
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
