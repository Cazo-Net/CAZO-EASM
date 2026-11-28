import { useId } from "react";

/** CAZO EASM mark: an open perimeter with the asset at its centre. */
export function CazoMark({ className = "h-7 w-7" }: { className?: string }) {
  const id = useId();
  return (
    <svg viewBox="0 0 64 64" fill="none" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={id} x1="8" y1="8" x2="56" y2="56" gradientUnits="userSpaceOnUse">
          <stop stopColor="#5B9BFF" />
          <stop offset="1" stopColor="#2563EB" />
        </linearGradient>
      </defs>
      <path
        d="M52.78 44.00 L32.00 56.00 L11.22 44.00 L11.22 20.00 L32.00 8.00 L52.78 20.00"
        stroke={`url(#${id})`}
        strokeWidth="6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="32" cy="32" r="5.5" fill={`url(#${id})`} />
    </svg>
  );
}
