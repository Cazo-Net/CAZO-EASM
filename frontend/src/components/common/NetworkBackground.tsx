"use client";

import { useEffect, useRef, useCallback, useMemo } from "react";

/* ─── Types ─── */

interface Node {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  baseSize: number;
  opacity: number;
  baseOpacity: number;
  color: string;
  glowIntensity: number;
  blinkPhase: number;
  blinkSpeed: number;
  depth: number;
  active: boolean;
}

interface Connection {
  nodeA: number;
  nodeB: number;
  opacity: number;
  targetOpacity: number;
  width: number;
  active: boolean;
}

interface Pulse {
  connectionIndex: number;
  progress: number;
  speed: number;
  opacity: number;
  active: boolean;
}

interface Ripple {
  x: number;
  y: number;
  radius: number;
  maxRadius: number;
  opacity: number;
  active: boolean;
}

interface MouseState {
  x: number;
  y: number;
  active: boolean;
  clickTime: number;
}

interface QuadtreeBounds {
  x: number;
  y: number;
  w: number;
  h: number;
}

interface AnimState {
  nodes: Node[];
  connections: Connection[];
  pulses: Pulse[];
  ripples: Ripple[];
  mouse: MouseState;
  quadtree: Quadtree;
  width: number;
  height: number;
  dpr: number;
  animId: number;
  paused: boolean;
  lastTime: number;
  drift: { x: number; y: number };
  driftAngle: number;
  initialized: boolean;
}

class Quadtree {
  private bounds: QuadtreeBounds;
  private capacity: number;
  private nodes: number[] = [];
  private divided = false;
  private ne!: Quadtree;
  private nw!: Quadtree;
  private se!: Quadtree;
  private sw!: Quadtree;

  constructor(bounds: QuadtreeBounds, capacity = 8) {
    this.bounds = bounds;
    this.capacity = capacity;
  }

  clear(): void {
    this.nodes.length = 0;
    this.divided = false;
  }

  subdivide(): void {
    const { x, y, w, h } = this.bounds;
    const hw = w / 2;
    const hh = h / 2;
    this.ne = new Quadtree({ x: x + hw, y, w: hw, h: hh }, this.capacity);
    this.nw = new Quadtree({ x, y, w: hw, h: hh }, this.capacity);
    this.se = new Quadtree({ x: x + hw, y: y + hh, w: hw, h: hh }, this.capacity);
    this.sw = new Quadtree({ x, y: y + hh, w: hw, h: hh }, this.capacity);
    this.divided = true;
  }

  insert(index: number, x: number, y: number): boolean {
    const { bounds } = this;
    if (x < bounds.x || x > bounds.x + bounds.w || y < bounds.y || y > bounds.y + bounds.h) {
      return false;
    }
    if (this.nodes.length < this.capacity) {
      this.nodes.push(index);
      return true;
    }
    if (!this.divided) this.subdivide();
    return (
      this.ne.insert(index, x, y) ||
      this.nw.insert(index, x, y) ||
      this.se.insert(index, x, y) ||
      this.sw.insert(index, x, y)
    );
  }

  queryRange(range: QuadtreeBounds, found: number[]): number[] {
    const { bounds } = this;
    if (
      range.x > bounds.x + bounds.w ||
      range.x + range.w < bounds.x ||
      range.y > bounds.y + bounds.h ||
      range.y + range.h < bounds.y
    ) {
      return found;
    }
    for (const i of this.nodes) found.push(i);
    if (this.divided) {
      this.ne.queryRange(range, found);
      this.nw.queryRange(range, found);
      this.se.queryRange(range, found);
      this.sw.queryRange(range, found);
    }
    return found;
  }
}

/* ─── Config ─── */

export interface NetworkBackgroundProps {
  nodeCount?: number;
  connectionDistance?: number;
  speed?: number;
  particleSize?: number;
  opacity?: number;
  enableMouseInteraction?: boolean;
  enablePulseAnimation?: boolean;
  enableParallax?: boolean;
  className?: string;
}

const COLORS = [
  "59, 130, 246",
  "6, 182, 212",
  "139, 92, 246",
  "34, 197, 94",
  "99, 102, 241",
];

const PREFERS_REDUCED_MOTION =
  typeof window !== "undefined" &&
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/* ─── Component ─── */

export function NetworkBackground({
  nodeCount = 200,
  connectionDistance = 150,
  speed = 0.15,
  particleSize = 1.5,
  opacity = 0.6,
  enableMouseInteraction = true,
  enablePulseAnimation = true,
  enableParallax = true,
  className = "",
}: NetworkBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef<AnimState | null>(null);

  const reducedMotion = useMemo(() => PREFERS_REDUCED_MOTION, []);

  /* ─── Initialize state ─── */
  const initState = useCallback(
    (w: number, h: number) => {
      const dpr = window.devicePixelRatio || 1;
      const nodes: Node[] = [];
      const connections: Connection[] = [];
      const pulses: Pulse[] = [];
      const ripples: Ripple[] = [];

      for (let i = 0; i < nodeCount; i++) {
        const depth = Math.random();
        const sz = (particleSize * (0.4 + depth * 0.6)) * (0.8 + Math.random() * 0.4);
        nodes.push({
          x: Math.random() * w,
          y: Math.random() * h,
          vx: (Math.random() - 0.5) * speed,
          vy: (Math.random() - 0.5) * speed,
          size: sz,
          baseSize: sz,
          opacity: (0.15 + Math.random() * 0.45) * opacity,
          baseOpacity: (0.15 + Math.random() * 0.45) * opacity,
          color: COLORS[Math.floor(Math.random() * COLORS.length)],
          glowIntensity: 0.3 + Math.random() * 0.4,
          blinkPhase: Math.random() * Math.PI * 2,
          blinkSpeed: 0.2 + Math.random() * 0.6,
          depth,
          active: true,
        });
      }

      const bounds: QuadtreeBounds = { x: 0, y: 0, w, h };
      const quadtree = new Quadtree(bounds, 8);

      stateRef.current = {
        nodes,
        connections,
        pulses,
        ripples,
        mouse: { x: w / 2, y: h / 2, active: false, clickTime: 0 },
        quadtree,
        width: w,
        height: h,
        dpr,
        animId: 0,
        paused: false,
        lastTime: 0,
        drift: { x: 0, y: 0 },
        driftAngle: 0,
        initialized: true,
      };
    },
    [nodeCount, speed, particleSize, opacity]
  );

  /* ─── Find neighbors using quadtree ─── */
  const findNeighbors = useCallback(
    (state: AnimState, index: number) => {
      const node = state.nodes[index];
      const halfD = connectionDistance;
      const range: QuadtreeBounds = {
        x: node.x - halfD,
        y: node.y - halfD,
        w: halfD * 2,
        h: halfD * 2,
      };
      state.quadtree.clear();
      for (let i = 0; i < state.nodes.length; i++) {
        if (i !== index && state.nodes[i].active) {
          state.quadtree.insert(i, state.nodes[i].x, state.nodes[i].y);
        }
      }
      const found: number[] = [];
      state.quadtree.queryRange(range, found);
      return found;
    },
    [connectionDistance]
  );

  /* ─── Update loop ─── */
  const update = useCallback(
    (dt: number) => {
      const state = stateRef.current;
      if (!state || state.paused) return;

      const { nodes, connections, pulses, ripples, mouse } = state;
      const w = state.width;
      const h = state.height;

      /* ─ Drift (slow camera pan) ─ */
      if (enableParallax) {
        state.driftAngle += dt * 0.00003;
        state.drift.x = Math.cos(state.driftAngle) * 15;
        state.drift.y = Math.sin(state.driftAngle * 0.7) * 10;
      }

      /* ─ Update nodes ─ */
      for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];
        if (!n.active) continue;

        /* Mouse attraction */
        if (enableMouseInteraction && mouse.active) {
          const dx = mouse.x - n.x;
          const dy = mouse.y - n.y;
          const distSq = dx * dx + dy * dy;
          const maxDist = 250;
          if (distSq < maxDist * maxDist && distSq > 1) {
            const dist = Math.sqrt(distSq);
            const force = (1 - dist / maxDist) * 0.008 * dt;
            n.vx += (dx / dist) * force;
            n.vy += (dy / dist) * force;
          }
        }

        /* Damping */
        n.vx *= 0.998;
        n.vy *= 0.998;

        /* Clamp speed */
        const maxSpeed = speed * 3;
        const spd = Math.sqrt(n.vx * n.vx + n.vy * n.vy);
        if (spd > maxSpeed) {
          n.vx = (n.vx / spd) * maxSpeed;
          n.vy = (n.vy / spd) * maxSpeed;
        }

        /* Drift influence */
        n.vx += state.drift.x * 0.0001 * n.depth;
        n.vy += state.drift.y * 0.0001 * n.depth;

        n.x += n.vx * dt * 0.06;
        n.y += n.vy * dt * 0.06;

        /* Wrap around edges with padding */
        const pad = 50;
        if (n.x < -pad) n.x = w + pad;
        if (n.x > w + pad) n.x = -pad;
        if (n.y < -pad) n.y = h + pad;
        if (n.y > h + pad) n.y = -pad;

        /* Blink */
        n.blinkPhase += n.blinkSpeed * dt * 0.001;
        const blink = 0.85 + 0.15 * Math.sin(n.blinkPhase);
        n.opacity = n.baseOpacity * blink;

        /* Pulse size subtly */
        n.size = n.baseSize * (0.95 + 0.05 * Math.sin(n.blinkPhase * 0.7));
      }

      /* ─ Build connections ─ */
      /* Rebuild quadtree with all nodes */
      state.quadtree.clear();
      for (let i = 0; i < nodes.length; i++) {
        if (nodes[i].active) {
          state.quadtree.insert(i, nodes[i].x, nodes[i].y);
        }
      }

      /* Reuse connection pool */
      let connIdx = 0;
      const usedPairs = new Set<string>();

      for (let i = 0; i < nodes.length; i++) {
        const n = nodes[i];
        if (!n.active) continue;

        const range: QuadtreeBounds = {
          x: n.x - connectionDistance,
          y: n.y - connectionDistance,
          w: connectionDistance * 2,
          h: connectionDistance * 2,
        };
        const neighbors: number[] = [];
        state.quadtree.queryRange(range, neighbors);

        for (const j of neighbors) {
          if (j <= i) continue;
          const m = nodes[j];
          if (!m.active) continue;

          const dx = n.x - m.x;
          const dy = n.y - m.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist > connectionDistance) continue;

          const pairKey = i < j ? `${i}:${j}` : `${j}:${i}`;
          if (usedPairs.has(pairKey)) continue;
          usedPairs.add(pairKey);

          const targetOpacity = (1 - dist / connectionDistance) * 0.25 * opacity;

          if (connIdx < connections.length) {
            const c = connections[connIdx];
            c.nodeA = i;
            c.nodeB = j;
            c.targetOpacity = targetOpacity;
            c.width = 0.5 + (1 - dist / connectionDistance) * 0.5;
            c.active = true;
          } else {
            connections.push({
              nodeA: i,
              nodeB: j,
              opacity: 0,
              targetOpacity,
              width: 0.5 + (1 - dist / connectionDistance) * 0.5,
              active: true,
            });
          }
          connIdx++;
        }
      }

      /* Fade out unused connections */
      for (let i = connIdx; i < connections.length; i++) {
        connections[i].active = false;
      }

      /* Smooth opacity transition */
      for (let i = 0; i < connections.length; i++) {
        const c = connections[i];
        if (c.active) {
          c.opacity += (c.targetOpacity - c.opacity) * 0.05;
        } else {
          c.opacity *= 0.95;
          if (c.opacity < 0.005) {
            connections.splice(i, 1);
            i--;
          }
        }
      }

      /* ─ Pulses (data traveling along connections) ─ */
      if (enablePulseAnimation) {
        /* Spawn new pulses occasionally */
        if (connections.length > 0 && Math.random() < 0.003 * dt * 0.06) {
          const idx = Math.floor(Math.random() * connections.length);
          if (connections[idx]?.active && connections[idx].opacity > 0.05) {
            let pulse = pulses.find((p) => !p.active);
            if (!pulse) {
              pulse = { connectionIndex: idx, progress: 0, speed: 0.3 + Math.random() * 0.4, opacity: 0.8, active: true };
              pulses.push(pulse);
            } else {
              pulse.connectionIndex = idx;
              pulse.progress = 0;
              pulse.speed = 0.3 + Math.random() * 0.4;
              pulse.opacity = 0.8;
              pulse.active = true;
            }
          }
        }

        for (const p of pulses) {
          if (!p.active) continue;
          p.progress += p.speed * dt * 0.001;
          if (p.progress >= 1) {
            p.active = false;
          }
        }
      }

      /* ─ Ripples (click effect) ─ */
      for (let i = ripples.length - 1; i >= 0; i--) {
        const r = ripples[i];
        if (!r.active) continue;
        r.radius += dt * 0.08;
        r.opacity = Math.max(0, 1 - r.radius / r.maxRadius);
        if (r.opacity <= 0) {
          ripples.splice(i, 1);
        }
      }
    },
    [connectionDistance, enableMouseInteraction, enablePulseAnimation, enableParallax, speed, opacity]
  );

  /* ─── Render ─── */
  const render = useCallback(() => {
    const state = stateRef.current;
    if (!state) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const { nodes, connections, pulses, ripples, drift } = state;
    const dpr = state.dpr;
    const w = state.width;
    const h = state.height;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    /* ─ Subtle radial background glow ─ */
    const cx = w / 2 + drift.x;
    const cy = h / 2 + drift.y;
    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(w, h) * 0.6);
    grad.addColorStop(0, "rgba(37, 99, 235, 0.025)");
    grad.addColorStop(0.5, "rgba(6, 182, 212, 0.01)");
    grad.addColorStop(1, "transparent");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, w, h);

    ctx.save();
    ctx.translate(drift.x * 0.15, drift.y * 0.15);

    /* ─ Draw connections ─ */
    ctx.lineCap = "round";
    for (const c of connections) {
      if (!c.active && c.opacity < 0.005) continue;
      const nA = nodes[c.nodeA];
      const nB = nodes[c.nodeB];
      if (!nA || !nB) continue;

      ctx.beginPath();
      ctx.moveTo(nA.x, nA.y);
      ctx.lineTo(nB.x, nB.y);
      ctx.strokeStyle = `rgba(59, 130, 246, ${c.opacity})`;
      ctx.lineWidth = c.width;
      ctx.stroke();
    }

    /* ─ Draw pulses ─ */
    if (enablePulseAnimation) {
      for (const p of pulses) {
        if (!p.active) continue;
        const c = connections[p.connectionIndex];
        if (!c) continue;
        const nA = nodes[c.nodeA];
        const nB = nodes[c.nodeB];
        if (!nA || !nB) continue;

        const px = nA.x + (nB.x - nA.x) * p.progress;
        const py = nA.y + (nB.y - nA.y) * p.progress;
        const pGrad = ctx.createRadialGradient(px, py, 0, px, py, 6);
        pGrad.addColorStop(0, `rgba(6, 182, 212, ${p.opacity})`);
        pGrad.addColorStop(1, "rgba(6, 182, 212, 0)");
        ctx.beginPath();
        ctx.arc(px, py, 6, 0, Math.PI * 2);
        ctx.fillStyle = pGrad;
        ctx.fill();
      }
    }

    /* ─ Draw nodes ─ */
    for (const n of nodes) {
      if (!n.active) continue;

      /* Glow */
      const glowSize = n.size * (3 + n.glowIntensity * 4);
      const glow = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, glowSize);
      glow.addColorStop(0, `rgba(${n.color}, ${n.opacity * n.glowIntensity * 0.3})`);
      glow.addColorStop(1, `rgba(${n.color}, 0)`);
      ctx.beginPath();
      ctx.arc(n.x, n.y, glowSize, 0, Math.PI * 2);
      ctx.fillStyle = glow;
      ctx.fill();

      /* Core dot */
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${n.color}, ${n.opacity})`;
      ctx.fill();
    }

    /* ─ Draw ripples ─ */
    for (const r of ripples) {
      if (!r.active) continue;
      ctx.beginPath();
      ctx.arc(r.x, r.y, r.radius, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(59, 130, 246, ${r.opacity * 0.5})`;
      ctx.lineWidth = 1.5;
      ctx.stroke();

      /* Inner glow ring */
      ctx.beginPath();
      ctx.arc(r.x, r.y, r.radius * 0.7, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(6, 182, 212, ${r.opacity * 0.3})`;
      ctx.lineWidth = 0.8;
      ctx.stroke();
    }

    ctx.restore();
  }, [enablePulseAnimation]);

  /* ─── Animation loop ─── */
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const resize = () => {
      const rect = canvas.parentElement?.getBoundingClientRect();
      if (!rect) return;
      const w = rect.width;
      const h = rect.height;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;

      if (!stateRef.current?.initialized) {
        initState(w, h);
      } else {
        stateRef.current.width = w;
        stateRef.current.height = h;
        stateRef.current.dpr = dpr;
      }
    };

    resize();

    const onVisibility = () => {
      if (stateRef.current) {
        stateRef.current.paused = document.hidden;
        if (!document.hidden) {
          stateRef.current.lastTime = performance.now();
        }
      }
    };

    const onResize = () => resize();

    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("resize", onResize);

    /* ─ Main loop ─ */
    let running = true;
    const loop = (time: number) => {
      if (!running) return;
      const state = stateRef.current;
      if (state && !state.paused) {
        const dt = state.lastTime ? Math.min(time - state.lastTime, 50) : 16;
        state.lastTime = time;
        update(dt);
        render();
      }
      stateRef.current!.animId = requestAnimationFrame(loop);
    };

    stateRef.current!.animId = requestAnimationFrame(loop);

    return () => {
      running = false;
      cancelAnimationFrame(stateRef.current?.animId ?? 0);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("resize", onResize);
    };
  }, [initState, update, render]);

  /* ─── Mouse handlers ─── */
  const onMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (!enableMouseInteraction || !stateRef.current) return;
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      stateRef.current.mouse.x = e.clientX - rect.left;
      stateRef.current.mouse.y = e.clientY - rect.top;
      stateRef.current.mouse.active = true;
    },
    [enableMouseInteraction]
  );

  const onMouseLeave = useCallback(() => {
    if (stateRef.current) {
      stateRef.current.mouse.active = false;
    }
  }, []);

  const onClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (!stateRef.current) return;
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      stateRef.current.ripples.push({
        x,
        y,
        radius: 0,
        maxRadius: 180,
        opacity: 1,
        active: true,
      });
    },
    []
  );

  /* ─── Reduced motion ─── */
  if (reducedMotion) {
    return <div className={`absolute inset-0 pointer-events-none ${className}`} />;
  }

  return (
    <div className={`absolute inset-0 overflow-hidden pointer-events-none ${className}`}>
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full"
        style={{ pointerEvents: enableMouseInteraction ? "auto" : "none" }}
        onMouseMove={onMouseMove}
        onMouseLeave={onMouseLeave}
        onClick={onClick}
      />
    </div>
  );
}
