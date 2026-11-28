/* eslint-disable @next/next/no-img-element */
/** CAZO EASM mark. The artwork lives in `public/logo.svg`. */
export function CazoMark({ className = "h-7 w-7" }: { className?: string }) {
  return <img src="/logo.svg" alt="" aria-hidden="true" draggable={false} className={`select-none ${className}`} />;
}
