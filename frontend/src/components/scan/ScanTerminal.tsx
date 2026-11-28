"use client";

import { useEffect, useRef, useState } from "react";

/**
 * A very small "live terminal" shown while a scan runs.
 *
 * Two layers move across each other: lines of scanner output scroll upward,
 * and a band of hex digits drifts sideways behind them. The output lines use
 * the hosts and ports the scan has actually found so far, mixed with generic
 * probe chatter, so it feels alive without inventing results. It is purely
 * decorative (aria-hidden) and stops moving for people who prefer reduced
 * motion.
 */

type Props = {
  hosts?: { name: string; ip?: string | null }[];
  ports?: { host?: string; port: number; service?: string | null }[];
  queued?: boolean;
  className?: string;
};

const HEX = "0123456789abcdef";
const rand = (n: number) => Math.floor(Math.random() * n);
const hex = (len: number) => Array.from({ length: len }, () => HEX[rand(16)]).join("");

function nextLine(hosts: NonNullable<Props["hosts"]>, ports: Props["ports"], queued: boolean): string {
  if (queued) {
    const q = ["queue: waiting for worker", `job ${hex(8)} pending`, "heartbeat ok", `slot check ${rand(9) + 1}/10`];
    return q[rand(q.length)];
  }
  // Show only the first label (staging, api, ...) so lines fit the tiny window.
  const short = (name: string) => name.split(".")[0];
  const h = hosts.length ? hosts[rand(hosts.length)] : null;
  const host = h ? short(h.name) : hex(4);
  const p = ports && ports.length ? ports[rand(ports.length)] : null;
  const options = [
    // Real hosts and IPs found so far; otherwise generic probe chatter.
    h?.ip ? `dns A ${host} -> ${h.ip}` : `dns query ${host}`,
    p && p.host ? `tcp ${short(p.host)}:${p.port} open` : `tcp probe :${[22, 80, 443, 8080, 8443][rand(5)]}`,
    `tls ${host} sha256:${hex(10)}`,
    `http ${host} ${[200, 301, 302, 403][rand(4)]} ${rand(900) + 80}ms`,
    `ct-log ${hex(12)} match`,
    `sni ${host} ok`,
    p ? `svc ${p.port}/${p.service || "tcp"} fingerprint` : `rtt ${rand(90) + 8}ms ttl=${rand(64) + 40}`,
  ];
  return options[rand(options.length)];
}

export function ScanTerminal({ hosts = [], ports = [], queued = false, className = "" }: Props) {
  const [lines, setLines] = useState<string[]>(() => ["$ cazo scan --live", "", ""]);
  const [band, setBand] = useState(() => hex(48));
  const data = useRef({ hosts, ports, queued });
  data.current = { hosts, ports, queued };

  useEffect(() => {
    if (typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const t1 = setInterval(() => {
      const d = data.current;
      setLines((prev) => [...prev.slice(-5), nextLine(d.hosts, d.ports, d.queued)]);
    }, 420);
    const t2 = setInterval(() => setBand((b) => b.slice(1) + HEX[rand(16)]), 90);
    return () => {
      clearInterval(t1);
      clearInterval(t2);
    };
  }, []);

  return (
    <div
      aria-hidden="true"
      className={
        "relative h-12 w-52 shrink-0 overflow-hidden rounded-lg border border-primary/25 bg-black/80 font-mono text-[8.5px] leading-[11px] " +
        className
      }
    >
      {/* hex band drifting sideways behind the output */}
      <div className="pointer-events-none absolute inset-x-0 top-1/2 -translate-y-1/2 whitespace-nowrap px-1 text-[10px] tracking-[0.18em] text-primary/15">
        {band}
      </div>
      {/* output scrolling upward; newest line at the bottom */}
      <div className="absolute inset-x-0 bottom-0 px-1.5 pb-1">
        {lines.slice(-4).map((l, i, arr) => (
          <div
            key={`${lines.length}-${i}`}
            className={
              "truncate " +
              (i === arr.length - 1 ? "text-primary" : i === arr.length - 2 ? "text-foreground/70" : "text-foreground/35")
            }
          >
            {i === arr.length - 1 ? "> " : "  "}
            {l}
            {i === arr.length - 1 && <span className="ml-0.5 inline-block h-[8px] w-[4px] translate-y-[1px] animate-pulse bg-primary" />}
          </div>
        ))}
      </div>
      {/* soft fade at the top so lines appear to scroll away */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-4 bg-gradient-to-b from-black/90 to-transparent" />
    </div>
  );
}
