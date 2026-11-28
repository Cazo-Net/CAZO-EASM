/**
 * Illustration for the sign-in pages: a known inventory inside an open
 * perimeter (the shape of the CAZO mark), and three forgotten assets sitting
 * outside it. Decorative only; the parent marks the panel aria-hidden.
 *
 * Colours come from the theme tokens, so it follows a re-brand.
 */

const CENTER = { x: 210, y: 180 };

// Assets the organization knows about: inside the perimeter.
const KNOWN = [
  { x: 165, y: 132 },
  { x: 252, y: 122 },
  { x: 150, y: 190 },
  { x: 176, y: 236 },
  { x: 250, y: 240 },
];

// Assets nobody remembers: outside, reached through the open side.
const FORGOTTEN = [
  { x: 372, y: 118, label: "staging.acme-corp.com", note: "open :8080" },
  { x: 396, y: 186, label: "old-vpn.acme-corp.com", note: "cert expired" },
  { x: 366, y: 252, label: "jenkins.acme-corp.com", note: "login exposed" },
];

export function AttackSurfaceArt({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 600 360"
      fill="none"
      className={className}
      role="presentation"
      focusable="false"
    >
      <defs>
        <radialGradient id="asa-glow" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(380 186) scale(170)">
          <stop stopColor="hsl(var(--primary))" stopOpacity="0.22" />
          <stop offset="1" stopColor="hsl(var(--primary))" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="asa-perimeter" x1="100" y1="70" x2="320" y2="290" gradientUnits="userSpaceOnUse">
          <stop stopColor="hsl(var(--foreground))" stopOpacity="0.55" />
          <stop offset="1" stopColor="hsl(var(--foreground))" stopOpacity="0.18" />
        </linearGradient>
      </defs>

      {/* Glow behind the forgotten assets */}
      <rect x="210" y="16" width="340" height="340" fill="url(#asa-glow)" />

      {/* Range rings */}
      {[62, 124, 186].map((r) => (
        <circle key={r} cx={CENTER.x} cy={CENTER.y} r={r} stroke="hsl(var(--border))" strokeWidth="1" strokeDasharray="2 6" />
      ))}

      {/* Links to known assets */}
      {KNOWN.map((n, i) => (
        <line key={i} x1={CENTER.x} y1={CENTER.y} x2={n.x} y2={n.y} stroke="hsl(var(--foreground))" strokeOpacity="0.16" strokeWidth="1" />
      ))}

      {/* Links to forgotten assets, through the gap */}
      {FORGOTTEN.map((n, i) => (
        <line key={i} x1={CENTER.x} y1={CENTER.y} x2={n.x} y2={n.y} stroke="hsl(var(--primary))" strokeOpacity="0.55" strokeWidth="1.25" strokeDasharray="4 5" />
      ))}

      {/* The perimeter: a hexagon with its right edge missing */}
      <path
        d="M305.3 235 L210 290 L114.7 235 L114.7 125 L210 70 L305.3 125"
        stroke="url(#asa-perimeter)"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Known assets */}
      {KNOWN.map((n, i) => (
        <g key={i}>
          <circle cx={n.x} cy={n.y} r="9" fill="hsl(var(--card))" stroke="hsl(var(--border))" strokeWidth="1" />
          <circle cx={n.x} cy={n.y} r="3.5" fill="hsl(var(--muted-foreground))" />
        </g>
      ))}

      {/* The organization */}
      <circle cx={CENTER.x} cy={CENTER.y} r="17" fill="hsl(var(--card))" stroke="hsl(var(--foreground))" strokeOpacity="0.35" strokeWidth="1.25" />
      <circle cx={CENTER.x} cy={CENTER.y} r="6" fill="hsl(var(--foreground))" />
      <text x={CENTER.x} y="318" textAnchor="middle" fontSize="11" fill="hsl(var(--muted-foreground))" style={{ letterSpacing: "0.08em" }}>
        KNOWN INVENTORY
      </text>

      {/* Forgotten assets */}
      {FORGOTTEN.map((n, i) => (
        <g key={i}>
          <circle cx={n.x} cy={n.y} r="16" fill="hsl(var(--primary))" fillOpacity="0.12" className="motion-safe:animate-pulse" />
          <circle cx={n.x} cy={n.y} r="9" fill="hsl(var(--card))" stroke="hsl(var(--primary))" strokeWidth="1.5" />
          <circle cx={n.x} cy={n.y} r="3.5" fill="hsl(var(--primary))" />
          <text x={n.x + 22} y={n.y - 2} fontSize="11.5" fill="hsl(var(--foreground))" style={{ fontFamily: "var(--font-mono), ui-monospace, monospace" }}>
            {n.label}
          </text>
          <text x={n.x + 22} y={n.y + 13} fontSize="10.5" fill="hsl(var(--primary))">
            {n.note}
          </text>
        </g>
      ))}

      {/* Count badge */}
      <g>
        <rect x="352" y="40" width="158" height="26" rx="13" fill="hsl(var(--primary))" fillOpacity="0.12" stroke="hsl(var(--primary))" strokeOpacity="0.4" />
        <circle cx="368" cy="53" r="3" fill="hsl(var(--primary))" />
        <text x="379" y="57" fontSize="11.5" fontWeight="600" fill="hsl(var(--primary))">
          3 forgotten assets
        </text>
      </g>
    </svg>
  );
}
