"use client";

import { cn } from "@/lib/utils";

interface ErrorIllustrationProps {
  className?: string;
  glowColor?: string;
  size?: "sm" | "md" | "lg";
}

const sizeMap = {
  sm: { w: 120, h: 140, glow: 60 },
  md: { w: 180, h: 210, glow: 90 },
  lg: { w: 240, h: 280, glow: 120 },
};

export function ErrorIllustration({
  className,
  glowColor = "rgba(56,189,248,0.15)",
  size = "lg",
}: ErrorIllustrationProps) {
  const s = sizeMap[size];

  return (
    <div
      className={cn("relative flex items-center justify-center", className)}
      role="img"
      aria-label="CAZO EASM security illustration"
    >
      <div
        className="absolute rounded-full blur-3xl animate-pulse"
        style={{
          width: s.glow * 2,
          height: s.glow * 2,
          background: `radial-gradient(circle, ${glowColor} 0%, transparent 70%)`,
        }}
      />

      <svg
        width={s.w}
        height={s.h}
        viewBox="0 0 240 280"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="relative z-10 drop-shadow-2xl"
      >
        {/* Hood shadow */}
        <ellipse cx="120" cy="265" rx="55" ry="8" fill="rgba(0,0,0,0.3)" />

        {/* Body / Cloak */}
        <path
          d="M70 160 C70 160 60 200 55 250 L185 250 C180 200 170 160 170 160
             C170 140 160 120 120 115 C80 120 70 140 70 160Z"
          fill="url(#cloakGrad)"
          stroke="rgba(56,189,248,0.15)"
          strokeWidth="0.5"
        />

        {/* Cloak folds */}
        <path
          d="M90 160 C90 180 85 220 82 250"
          stroke="rgba(56,189,248,0.08)"
          strokeWidth="1"
          fill="none"
        />
        <path
          d="M150 160 C150 180 155 220 158 250"
          stroke="rgba(56,189,248,0.08)"
          strokeWidth="1"
          fill="none"
        />

        {/* Hood */}
        <path
          d="M75 155 C75 90 85 55 120 40 C155 55 165 90 165 155
             C155 150 140 145 120 143 C100 145 85 150 75 155Z"
          fill="url(#hoodGrad)"
          stroke="rgba(56,189,248,0.2)"
          strokeWidth="0.5"
        />

        {/* Hood inner shadow */}
        <path
          d="M85 150 C85 105 95 75 120 62 C145 75 155 105 155 150
             C148 146 135 142 120 140 C105 142 92 146 85 150Z"
          fill="url(#hoodInner)"
        />

        {/* Face shadow area */}
        <ellipse cx="120" cy="115" rx="28" ry="25" fill="url(#faceShadow)" />

        {/* Eyes - glowing */}
        <g className="animate-pulse">
          <ellipse cx="108" cy="112" rx="4" ry="2.5" fill="#38BDF8" opacity="0.9" />
          <ellipse cx="132" cy="112" rx="4" ry="2.5" fill="#38BDF8" opacity="0.9" />
          <ellipse cx="108" cy="112" rx="6" ry="4" fill="rgba(56,189,248,0.2)" />
          <ellipse cx="132" cy="112" rx="6" ry="4" fill="rgba(56,189,248,0.2)" />
        </g>

        {/* Shield emblem on chest */}
        <g transform="translate(108, 175)">
          <path
            d="M12 0 L24 6 L24 16 C24 22 18 27 12 30 C6 27 0 22 0 16 L0 6 Z"
            fill="none"
            stroke="rgba(56,189,248,0.4)"
            strokeWidth="1.5"
          />
          <path
            d="M12 4 L20 8 L20 15 C20 19 16 23 12 25 C8 23 4 19 4 15 L4 8 Z"
            fill="rgba(56,189,248,0.1)"
          />
          <path
            d="M9 14 L11 16 L15 11"
            stroke="rgba(56,189,248,0.6)"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
        </g>

        {/* Floating particles */}
        <circle cx="50" cy="80" r="1.5" fill="#38BDF8" opacity="0.3">
          <animate attributeName="cy" values="80;70;80" dur="4s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.3;0.6;0.3" dur="4s" repeatCount="indefinite" />
        </circle>
        <circle cx="190" cy="90" r="1" fill="#38BDF8" opacity="0.2">
          <animate attributeName="cy" values="90;78;90" dur="5s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.2;0.5;0.2" dur="5s" repeatCount="indefinite" />
        </circle>
        <circle cx="45" cy="180" r="1" fill="#06B6D4" opacity="0.25">
          <animate attributeName="cy" values="180;170;180" dur="3.5s" repeatCount="indefinite" />
        </circle>
        <circle cx="195" cy="200" r="1.5" fill="#06B6D4" opacity="0.2">
          <animate attributeName="cy" values="200;188;200" dur="4.5s" repeatCount="indefinite" />
        </circle>

        <defs>
          <linearGradient id="cloakGrad" x1="120" y1="115" x2="120" y2="250" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#222222" />
            <stop offset="100%" stopColor="#141414" />
          </linearGradient>
          <linearGradient id="hoodGrad" x1="120" y1="40" x2="120" y2="155" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#292929" />
            <stop offset="100%" stopColor="#1B1B1B" />
          </linearGradient>
          <radialGradient id="hoodInner" cx="120" cy="100" r="40" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#0B0B0B" />
            <stop offset="100%" stopColor="#1B1B1B" />
          </radialGradient>
          <radialGradient id="faceShadow" cx="120" cy="115" r="28" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#000000" stopOpacity="0.8" />
            <stop offset="100%" stopColor="#000000" stopOpacity="0" />
          </radialGradient>
        </defs>
      </svg>
    </div>
  );
}
