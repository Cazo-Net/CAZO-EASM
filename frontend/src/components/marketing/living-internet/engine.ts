/**
 * Living Internet — simulation engine.
 *
 * Owns the PixiJS Application and all scene state. Rendering strategy for
 * performance:
 *  - One cached radial-glow texture, reused as tinted/scaled Sprites for every
 *    node glow (avoids per-frame Graphics rasterization).
 *  - Node cores + all connections + pulses drawn into a small number of pooled
 *    Graphics objects, cleared and redrawn per frame.
 *  - A uniform spatial grid limits connection candidate checks to neighbours.
 *  - Object pools for pulses and ripples; nothing is allocated in the hot loop.
 */

import {
  Application,
  Container,
  Graphics,
  Sprite,
  Texture,
  Text,
  TextStyle,
  Assets,
  Ticker,
} from "pixi.js";
import {
  BRAND,
  NODE_STYLES,
  INFRA_KINDS,
  DISCOVERY_KINDS,
  DISCOVERY_EVENTS,
  SECURITY_EVENTS,
  ACTIVITY_LINES,
  DYNAMIC_LABELS,
  resolveQuality,
  type NodeKind,
  type QualityTier,
} from "./types";

interface SceneNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  baseR: number;
  kind: NodeKind;
  color: number;
  layer: 0 | 1 | 2; // 0 stars, 1 mesh, 2 infra
  depth: number; // 0..1 parallax depth (1 = closest)
  glyph: string;
  // lifecycle
  born: number; // ms timestamp
  life: number; // -1 = permanent, else ms remaining
  appear: number; // 0..1 spawn-in progress
  // dynamics
  pulsePhase: number;
  alert: number; // 0..1 security-flash intensity
  glow: Sprite; // glow sprite (layer 2/1)
  // logo morph target
  homeX: number;
  homeY: number;
  morphX: number;
  morphY: number;
}

interface DataPulse {
  active: boolean;
  a: SceneNode | null;
  b: SceneNode | null;
  t: number;
  speed: number;
  color: number;
  size: number;
}

interface Ripple {
  active: boolean;
  x: number;
  y: number;
  r: number;
  max: number;
  color: number;
}

interface FloatLabel {
  container: Container;
  text: Text;
  node: SceneNode | null;
  ttl: number; // ms remaining
  max: number;
  offY: number;
}

interface FeedItem {
  container: Container;
  ttl: number;
  max: number;
  index: number;
}

const TWO_PI = Math.PI * 2;

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}
function easeOutCubic(t: number) {
  return 1 - Math.pow(1 - t, 3);
}
function pick<T>(arr: readonly T[]): T {
  return arr[(Math.random() * arr.length) | 0];
}

/** Build a soft radial-glow texture once, reused for all glows. */
function makeGlowTexture(app: Application, size = 128): Texture {
  const g = new Graphics();
  const steps = 24;
  for (let i = steps; i >= 0; i--) {
    const t = i / steps;
    const r = (size / 2) * t;
    const alpha = Math.pow(1 - t, 2.2) * 0.9;
    g.circle(size / 2, size / 2, r).fill({ color: 0xffffff, alpha });
  }
  const tex = app.renderer.generateTexture(g);
  g.destroy();
  return tex;
}

/** Small crisp dot texture for stars. */
function makeDotTexture(app: Application, size = 8): Texture {
  const g = new Graphics();
  g.circle(size / 2, size / 2, size / 2).fill({ color: 0xffffff, alpha: 1 });
  const tex = app.renderer.generateTexture(g);
  g.destroy();
  return tex;
}

export interface EngineHandle {
  destroy: () => void;
  setPaused: (paused: boolean) => void;
  setExclusion: (rect: DOMRect | null) => void;
  setGlobalAlpha: (a: number) => void;
  canvas: HTMLCanvasElement;
}

export interface EngineOptions {
  container: HTMLElement;
  /** DOM rect of the hero headline to avoid overlapping. */
  exclusion?: DOMRect | null;
  /** activity-feed mount (HTML overlay is handled separately; unused here). */
  reducedMotion?: boolean;
}

export async function createEngine(opts: EngineOptions): Promise<EngineHandle> {
  const { container } = opts;
  const quality: QualityTier = resolveQuality();
  const reduced = !!opts.reducedMotion;

  const initW = container.clientWidth || window.innerWidth || 1280;
  const initH = container.clientHeight || window.innerHeight || 720;

  const app = new Application();
  await app.init({
    background: BRAND.bg,
    backgroundAlpha: 1,
    antialias: true,
    resolution: Math.min(window.devicePixelRatio || 1, 2),
    autoDensity: true,
    powerPreference: "high-performance",
    width: initW,
    height: initH,
    resizeTo: container,
  });
  container.appendChild(app.canvas);
  app.canvas.style.width = "100%";
  app.canvas.style.height = "100%";
  app.canvas.style.display = "block";
  app.canvas.style.position = "absolute";
  app.canvas.style.inset = "0";
  // Ensure the renderer picks up the real container size once mounted.
  app.renderer.resize(
    container.clientWidth || initW,
    container.clientHeight || initH,
  );

  const W = () => app.renderer.width / app.renderer.resolution;
  const H = () => app.renderer.height / app.renderer.resolution;

  // ── layers (back → front) ──────────────────────────────────────────
  const scene = new Container();
  app.stage.addChild(scene);

  const layerStars = new Container();
  const layerLinks = new Container();
  const layerGlow = new Container();
  const layerCores = new Container();
  const layerFx = new Container();
  const layerLabels = new Container();
  scene.addChild(layerStars, layerLinks, layerGlow, layerCores, layerFx, layerLabels);

  const glowTex = makeGlowTexture(app);
  const dotTex = makeDotTexture(app);

  // link + core + pulse graphics (redrawn each frame)
  const linkG = new Graphics();
  const coreG = new Graphics();
  const fxG = new Graphics();
  layerLinks.addChild(linkG);
  layerCores.addChild(coreG);
  layerFx.addChild(fxG);

  // ── state ──────────────────────────────────────────────────────────
  const infra: SceneNode[] = [];
  const mesh: SceneNode[] = [];
  const stars: SceneNode[] = [];
  const pulses: DataPulse[] = [];
  const ripples: Ripple[] = [];
  const labels: FloatLabel[] = [];
  const feed: FeedItem[] = [];

  let globalAlpha = 0; // fades in on start, driven externally for scroll
  let targetAlpha = 1;
  let paused = false;
  let exclusion: DOMRect | null = opts.exclusion ?? null;
  const containerRect = () => container.getBoundingClientRect();

  const pointer = { x: -9999, y: -9999, active: false };

  // parallax drift
  const drift = { x: 0, y: 0, tx: 0, ty: 0 };

  // scan beam
  const scan = { active: false, x: 0, next: 4000, dir: 1 };

  // logo morph
  const morph = { active: false, t: 0, phase: 0 as 0 | 1 | 2, next: 30000 };

  // ── node factory ───────────────────────────────────────────────────
  function makeStar(): SceneNode {
    const depth = 0.1 + Math.random() * 0.25;
    const s: SceneNode = {
      x: Math.random() * W(),
      y: Math.random() * H(),
      vx: (Math.random() - 0.5) * 0.03,
      vy: (Math.random() - 0.5) * 0.03,
      baseR: 0.6 + Math.random() * 1.1,
      kind: "ip",
      color: BRAND.soft,
      layer: 0,
      depth,
      glyph: "",
      born: performance.now(),
      life: -1,
      appear: 1,
      pulsePhase: Math.random() * TWO_PI,
      alert: 0,
      glow: null as unknown as Sprite,
      homeX: 0,
      homeY: 0,
      morphX: 0,
      morphY: 0,
    };
    const sp = new Sprite(dotTex);
    sp.anchor.set(0.5);
    sp.tint = BRAND.soft;
    sp.alpha = 0.15 + depth * 0.5;
    sp.width = sp.height = s.baseR * 2;
    layerStars.addChild(sp);
    s.glow = sp;
    return s;
  }

  function makeNode(kind: NodeKind, layer: 1 | 2, x?: number, y?: number, life = -1): SceneNode {
    const style = NODE_STYLES[kind];
    const depth = layer === 2 ? 0.7 + Math.random() * 0.3 : 0.35 + Math.random() * 0.3;
    const s: SceneNode = {
      x: x ?? Math.random() * W(),
      y: y ?? Math.random() * H(),
      vx: (Math.random() - 0.5) * 0.12,
      vy: (Math.random() - 0.5) * 0.12,
      baseR: style.radius * (layer === 2 ? 1 : 0.55),
      kind,
      color: style.color,
      layer,
      depth,
      glyph: layer === 2 ? style.glyph : "",
      born: performance.now(),
      life,
      appear: 0,
      pulsePhase: Math.random() * TWO_PI,
      alert: 0,
      glow: null as unknown as Sprite,
      homeX: 0,
      homeY: 0,
      morphX: 0,
      morphY: 0,
    };
    s.homeX = s.x;
    s.homeY = s.y;
    const g = new Sprite(glowTex);
    g.anchor.set(0.5);
    g.tint = style.color;
    g.alpha = 0;
    g.blendMode = "add";
    layerGlow.addChild(g);
    s.glow = g;
    return s;
  }

  function seed() {
    for (let i = 0; i < quality.stars; i++) stars.push(makeStar());
    for (let i = 0; i < quality.mesh; i++) mesh.push(makeNode(pick(DISCOVERY_KINDS), 1));
    for (let i = 0; i < quality.infra; i++) infra.push(makeNode(pick(INFRA_KINDS), 2));
    for (let i = 0; i < quality.maxPulses; i++)
      pulses.push({ active: false, a: null, b: null, t: 0, speed: 0, color: 0, size: 0 });
    for (let i = 0; i < 24; i++)
      ripples.push({ active: false, x: 0, y: 0, r: 0, max: 0, color: 0 });
  }

  // ── spatial grid (for connections) ─────────────────────────────────
  const CELL = 140;
  let grid = new Map<number, SceneNode[]>();
  function gridKey(cx: number, cy: number) {
    return cx * 100000 + cy;
  }
  function rebuildGrid(nodes: SceneNode[]) {
    grid = new Map();
    for (const n of nodes) {
      const cx = (n.x / CELL) | 0;
      const cy = (n.y / CELL) | 0;
      const k = gridKey(cx, cy);
      let cell = grid.get(k);
      if (!cell) grid.set(k, (cell = []));
      cell.push(n);
    }
  }

  // ── pulses ─────────────────────────────────────────────────────────
  function spawnPulse(a: SceneNode, b: SceneNode) {
    const p = pulses.find((x) => !x.active);
    if (!p) return;
    p.active = true;
    p.a = a;
    p.b = b;
    p.t = 0;
    p.speed = 0.25 + Math.random() * 0.55;
    p.color = Math.random() < 0.5 ? BRAND.primary : BRAND.secondary;
    p.size = 1.4 + Math.random() * 1.6;
  }

  function spawnRipple(x: number, y: number, max: number, color: number) {
    const r = ripples.find((x) => !x.active);
    if (!r) return;
    r.active = true;
    r.x = x;
    r.y = y;
    r.r = 0;
    r.max = max;
    r.color = color;
  }

  // ── discovery events ───────────────────────────────────────────────
  const feedRoot = new Container();
  layerLabels.addChild(feedRoot);

  const labelStyle = new TextStyle({
    fontFamily: "JetBrains Mono, ui-monospace, monospace",
    fontSize: 11,
    fill: BRAND.soft,
    letterSpacing: 0.4,
  });
  const feedStyle = new TextStyle({
    fontFamily: "JetBrains Mono, ui-monospace, monospace",
    fontSize: 11,
    fill: BRAND.primary,
    letterSpacing: 0.4,
  });
  const discoveryStyle = new TextStyle({
    fontFamily: "JetBrains Mono, ui-monospace, monospace",
    fontSize: 10,
    fill: BRAND.soft,
    letterSpacing: 0.6,
  });

  let discNext = 2500;
  let secNext = 9000;
  let feedNext = 2000;
  let labelNext = 5000;

  function fireDiscovery() {
    const ev = pick(DISCOVERY_EVENTS);
    // spawn near a random infra node
    const anchor = infra[(Math.random() * infra.length) | 0];
    if (!anchor) return;
    const ang = Math.random() * TWO_PI;
    const dist = 60 + Math.random() * 120;
    const nx = Math.min(W() - 20, Math.max(20, anchor.x + Math.cos(ang) * dist));
    const ny = Math.min(H() - 20, Math.max(20, anchor.y + Math.sin(ang) * dist));
    const layer: 1 | 2 = Math.random() < 0.35 ? 2 : 1;
    const node = makeNode(ev.kind, layer, nx, ny, layer === 2 ? -1 : 14000 + Math.random() * 8000);
    if (layer === 2) infra.push(node);
    else mesh.push(node);
    spawnRipple(nx, ny, 46, node.color);

    // discovery label floats up from the new node
    const c = new Container();
    const t = new Text({ text: ev.label, style: discoveryStyle });
    t.anchor.set(0.5);
    const dot = new Graphics().circle(0, 0, 2).fill({ color: node.color });
    dot.x = -t.width / 2 - 6;
    c.addChild(dot, t);
    c.x = nx;
    c.y = ny - 14;
    c.alpha = 0;
    layerLabels.addChild(c);
    labels.push({ container: c, text: t, node, ttl: 3000, max: 3000, offY: 0 });
  }

  function fireSecurity() {
    const target = infra[(Math.random() * infra.length) | 0];
    if (!target) return;
    target.alert = 1;
    spawnRipple(target.x, target.y, 60, BRAND.critical);
    const c = new Container();
    const t = new Text({ text: pick(SECURITY_EVENTS), style: discoveryStyle });
    t.style.fill = BRAND.critical;
    t.anchor.set(0.5);
    c.addChild(t);
    c.x = target.x;
    c.y = target.y - 16;
    c.alpha = 0;
    layerLabels.addChild(c);
    labels.push({ container: c, text: t, node: target, ttl: 2600, max: 2600, offY: 0 });
  }

  function fireDynamicLabel() {
    if (labels.length >= quality.maxLabels) return;
    const anchor = infra[(Math.random() * infra.length) | 0];
    if (!anchor) return;
    const c = new Container();
    const t = new Text({ text: pick(DYNAMIC_LABELS), style: labelStyle });
    t.anchor.set(0, 0.5);
    const bg = new Graphics();
    bg.roundRect(-6, -t.height / 2 - 3, t.width + 12, t.height + 6, 4)
      .fill({ color: 0x0b0d12, alpha: 0.6 })
      .stroke({ color: anchor.color, alpha: 0.3, width: 1 });
    c.addChild(bg, t);
    c.x = anchor.x + 12;
    c.y = anchor.y - 10;
    c.alpha = 0;
    layerLabels.addChild(c);
    labels.push({ container: c, text: t, node: anchor, ttl: 4200, max: 4200, offY: 0 });
  }

  function fireFeed() {
    if (feed.length >= 5) return;
    const c = new Container();
    const t = new Text({ text: "+ " + pick(ACTIVITY_LINES), style: feedStyle });
    t.anchor.set(0, 0);
    c.addChild(t);
    c.alpha = 0;
    feedRoot.addChild(c);
    feed.push({ container: c, ttl: 3400, max: 3400, index: 0 });
  }

  // ── interaction ────────────────────────────────────────────────────
  function onPointerMove(e: PointerEvent) {
    const rect = containerRect();
    pointer.x = e.clientX - rect.left;
    pointer.y = e.clientY - rect.top;
    pointer.active = true;
    drift.tx = (pointer.x / W() - 0.5) * -20;
    drift.ty = (pointer.y / H() - 0.5) * -20;
  }
  function onPointerLeave() {
    pointer.active = false;
    pointer.x = pointer.y = -9999;
    drift.tx = 0;
    drift.ty = 0;
  }
  function onPointerDown(e: PointerEvent) {
    const rect = containerRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    spawnRipple(x, y, 220, BRAND.primary);
    // nudge nearby nodes outward
    for (const n of infra) {
      const dx = n.x - x;
      const dy = n.y - y;
      const d2 = dx * dx + dy * dy;
      if (d2 < 200 * 200 && d2 > 1) {
        const d = Math.sqrt(d2);
        const f = (1 - d / 200) * 1.4;
        n.vx += (dx / d) * f;
        n.vy += (dy / d) * f;
      }
    }
  }

  if (!reduced) {
    window.addEventListener("pointermove", onPointerMove, { passive: true });
    container.addEventListener("pointerleave", onPointerLeave);
    container.addEventListener("pointerdown", onPointerDown);
  }

  // ── logo silhouette (CAZO ring) target points ──────────────────────
  // Open perimeter ring matching the CazoMark: arc from ~-40° around to ~+250°.
  function logoPoints(count: number): { x: number; y: number }[] {
    const cx = W() / 2;
    const cy = H() * 0.46;
    const R = Math.min(W(), H()) * 0.16;
    const start = -0.7; // radians
    const end = TWO_PI * 0.82; // open ring
    const pts: { x: number; y: number }[] = [];
    for (let i = 0; i < count; i++) {
      const a = lerp(start, end, i / (count - 1));
      pts.push({ x: cx + Math.cos(a) * R, y: cy + Math.sin(a) * R });
    }
    return pts;
  }

  function beginMorph() {
    morph.active = true;
    morph.phase = 0;
    morph.t = 0;
    const pts = logoPoints(infra.length);
    // assign each infra node its nearest ring point (greedy)
    infra.forEach((n, i) => {
      const p = pts[i % pts.length];
      n.morphX = p.x + (Math.random() - 0.5) * 6;
      n.morphY = p.y + (Math.random() - 0.5) * 6;
      n.homeX = n.x;
      n.homeY = n.y;
    });
  }

  // ── FPS-based adaptive quality ─────────────────────────────────────
  let fpsAccum = 0;
  let fpsFrames = 0;
  let linkAlphaScale = 1;
  let connectBudget = quality.infra + quality.mesh;

  // ── main loop ──────────────────────────────────────────────────────
  seed();

  const tick = (ticker: Ticker) => {
    if (paused) return;
    const dtMs = Math.min(ticker.deltaMS, 50);
    const dt = dtMs / 16.6667;
    const now = performance.now();

    // global alpha ease
    globalAlpha = lerp(globalAlpha, targetAlpha, 0.06);
    scene.alpha = globalAlpha;

    // parallax drift ease
    drift.x = lerp(drift.x, drift.tx, 0.02);
    drift.y = lerp(drift.y, drift.ty, 0.02);

    // fps sampling
    fpsAccum += ticker.deltaMS;
    fpsFrames++;
    if (fpsAccum >= 1000) {
      const fps = (fpsFrames * 1000) / fpsAccum;
      if (fps < 45 && connectBudget > 40) {
        connectBudget = Math.max(40, connectBudget - 20);
        linkAlphaScale = Math.max(0.5, linkAlphaScale - 0.1);
      } else if (fps > 58 && connectBudget < quality.infra + quality.mesh) {
        connectBudget += 10;
      }
      fpsAccum = 0;
      fpsFrames = 0;
    }

    // ── timers ──
    if (!reduced) {
      discNext -= dtMs;
      if (discNext <= 0) {
        fireDiscovery();
        discNext = 2200 + Math.random() * 3200;
      }
      secNext -= dtMs;
      if (secNext <= 0) {
        fireSecurity();
        secNext = 8000 + Math.random() * 9000;
      }
      feedNext -= dtMs;
      if (feedNext <= 0) {
        fireFeed();
        feedNext = 1800 + Math.random() * 2600;
      }
      labelNext -= dtMs;
      if (labelNext <= 0) {
        fireDynamicLabel();
        labelNext = 3500 + Math.random() * 4500;
      }

      // scan beam
      scan.next -= dtMs;
      if (!scan.active && scan.next <= 0) {
        scan.active = true;
        scan.dir = Math.random() < 0.5 ? 1 : -1;
        scan.x = scan.dir === 1 ? -60 : W() + 60;
      }
      if (scan.active) {
        scan.x += scan.dir * (W() / 1400) * dtMs;
        if ((scan.dir === 1 && scan.x > W() + 60) || (scan.dir === -1 && scan.x < -60)) {
          scan.active = false;
          scan.next = 15000 + Math.random() * 6000;
        }
      }

      // logo morph scheduler
      morph.next -= dtMs;
      if (!morph.active && morph.next <= 0) {
        beginMorph();
        morph.next = 45000 + Math.random() * 30000;
      }
      if (morph.active) {
        morph.t += dtMs;
        if (morph.phase === 0 && morph.t > 1600) {
          morph.phase = 1;
          morph.t = 0;
        } else if (morph.phase === 1 && morph.t > 2600) {
          morph.phase = 2;
          morph.t = 0;
        } else if (morph.phase === 2 && morph.t > 1600) {
          morph.active = false;
        }
      }
    }

    // ── update stars (slow parallax) ──
    for (const s of stars) {
      s.x += s.vx * dt + drift.x * 0.004 * s.depth;
      s.y += s.vy * dt + drift.y * 0.004 * s.depth;
      if (s.x < -5) s.x = W() + 5;
      else if (s.x > W() + 5) s.x = -5;
      if (s.y < -5) s.y = H() + 5;
      else if (s.y > H() + 5) s.y = -5;
      s.pulsePhase += 0.01 * dt;
      const tw = 0.7 + Math.sin(s.pulsePhase) * 0.3;
      s.glow.x = s.x;
      s.glow.y = s.y;
      s.glow.alpha = (0.12 + s.depth * 0.45) * tw;
    }

    // ── update movable nodes ──
    const all = [...mesh, ...infra];
    for (let i = all.length - 1; i >= 0; i--) {
      const n = all[i];
      // lifecycle
      if (n.appear < 1) n.appear = Math.min(1, n.appear + dtMs / 700);
      if (n.life > 0) {
        n.life -= dtMs;
        if (n.life <= 0) {
          // fade out then remove
          n.appear -= dtMs / 500;
          if (n.appear <= 0) {
            n.glow.destroy();
            const arr = n.layer === 2 ? infra : mesh;
            const idx = arr.indexOf(n);
            if (idx >= 0) arr.splice(idx, 1);
            continue;
          }
        }
      }
      if (n.alert > 0) n.alert = Math.max(0, n.alert - dtMs / 1400);

      const px = drift.x * n.depth * 0.05;
      const py = drift.y * n.depth * 0.05;

      if (morph.active && n.layer === 2) {
        const k =
          morph.phase === 0
            ? easeOutCubic(Math.min(1, morph.t / 1600))
            : morph.phase === 1
              ? 1
              : 1 - easeOutCubic(Math.min(1, morph.t / 1600));
        n.x = lerp(n.homeX, n.morphX, k);
        n.y = lerp(n.homeY, n.morphY, k);
      } else {
        n.x += n.vx * dt;
        n.y += n.vy * dt;
        // gentle damping + wander
        n.vx *= 0.985;
        n.vy *= 0.985;
        n.vx += (Math.random() - 0.5) * 0.008;
        n.vy += (Math.random() - 0.5) * 0.008;

        // pointer attraction (nearby nodes lean toward cursor, connections strengthen)
        if (pointer.active) {
          const dx = pointer.x - n.x;
          const dy = pointer.y - n.y;
          const d2 = dx * dx + dy * dy;
          if (d2 < 180 * 180 && d2 > 1) {
            const d = Math.sqrt(d2);
            const f = (1 - d / 180) * 0.02;
            n.vx += (dx / d) * f;
            n.vy += (dy / d) * f;
          }
        }

        // hero exclusion — push nodes gently out of the headline box
        if (exclusion) {
          const rect = containerRect();
          const ex0 = exclusion.left - rect.left;
          const ey0 = exclusion.top - rect.top;
          const ex1 = ex0 + exclusion.width;
          const ey1 = ey0 + exclusion.height;
          const pad = 24;
          if (n.x > ex0 - pad && n.x < ex1 + pad && n.y > ey0 - pad && n.y < ey1 + pad) {
            const cx = (ex0 + ex1) / 2;
            const cy = (ey0 + ey1) / 2;
            const dx = n.x - cx;
            const dy = n.y - cy;
            const d = Math.hypot(dx, dy) || 1;
            n.vx += (dx / d) * 0.05;
            n.vy += (dy / d) * 0.05;
          }
        }

        // bounds bounce
        if (n.x < 10) n.vx += 0.05;
        else if (n.x > W() - 10) n.vx -= 0.05;
        if (n.y < 10) n.vy += 0.05;
        else if (n.y > H() - 10) n.vy -= 0.05;
      }

      n.pulsePhase += 0.03 * dt;
      const gx = n.x + px;
      const gy = n.y + py;
      const pulse = 0.5 + Math.sin(n.pulsePhase) * 0.5;
      const appearK = easeOutCubic(Math.max(0, Math.min(1, n.appear)));
      const glowSize = n.baseR * (n.layer === 2 ? 7 : 5) * (0.8 + pulse * 0.25) * appearK;
      n.glow.x = gx;
      n.glow.y = gy;
      n.glow.width = n.glow.height = glowSize;
      const alertMix = n.alert;
      n.glow.tint = alertMix > 0.01 ? BRAND.critical : n.color;
      n.glow.alpha =
        ((n.layer === 2 ? 0.32 : 0.16) + pulse * 0.12 + alertMix * 0.4) * appearK;
    }

    // ── connections + pulse spawn (spatial grid) ──
    rebuildGrid(infra);
    linkG.clear();
    let connMade = 0;
    const linkMaxDist = 190;
    for (const n of infra) {
      if (n.appear < 0.4) continue;
      const cx = (n.x / CELL) | 0;
      const cy = (n.y / CELL) | 0;
      for (let ox = -1; ox <= 1; ox++) {
        for (let oy = -1; oy <= 1; oy++) {
          const cell = grid.get(gridKey(cx + ox, cy + oy));
          if (!cell) continue;
          for (const m of cell) {
            if (m === n || m.x < n.x) continue; // avoid dup pairs
            if (connMade > connectBudget) break;
            const dx = m.x - n.x;
            const dy = m.y - n.y;
            const d2 = dx * dx + dy * dy;
            if (d2 > linkMaxDist * linkMaxDist) continue;
            const d = Math.sqrt(d2);
            const near = pointer.active
              ? Math.max(
                  0,
                  1 -
                    Math.min(
                      Math.hypot(pointer.x - n.x, pointer.y - n.y),
                      Math.hypot(pointer.x - m.x, pointer.y - m.y),
                    ) /
                      200,
                )
              : 0;
            let a =
              (1 - d / linkMaxDist) *
              0.22 *
              linkAlphaScale *
              Math.min(n.appear, m.appear);
            a += near * 0.25;
            if (scan.active) {
              const sd = Math.abs((n.x + m.x) / 2 - scan.x);
              if (sd < 90) a += (1 - sd / 90) * 0.5;
            }
            if (a < 0.012) continue;
            const color = near > 0.1 ? BRAND.primary : BRAND.secondary;
            // bezier bow
            const mx = (n.x + m.x) / 2;
            const my = (n.y + m.y) / 2;
            const nx = -(m.y - n.y);
            const ny = m.x - n.x;
            const nl = Math.hypot(nx, ny) || 1;
            const bow = Math.sin(now / 2600 + n.x * 0.01) * (d * 0.06);
            const qx = mx + (nx / nl) * bow;
            const qy = my + (ny / nl) * bow;
            linkG.moveTo(n.x, n.y).quadraticCurveTo(qx, qy, m.x, m.y);
            linkG.stroke({ color, alpha: Math.min(0.6, a), width: 1 });

            // occasionally launch a pulse along this link
            if (!reduced && Math.random() < 0.0016 * dt) spawnPulse(n, m);
            connMade++;
          }
        }
      }
    }

    // ── node cores ──
    coreG.clear();
    for (const n of [...mesh, ...infra]) {
      const appearK = easeOutCubic(Math.max(0, Math.min(1, n.appear)));
      if (appearK <= 0.01) continue;
      const px = drift.x * n.depth * 0.05;
      const py = drift.y * n.depth * 0.05;
      const pulse = 0.5 + Math.sin(n.pulsePhase) * 0.5;
      const r = n.baseR * appearK * (0.9 + pulse * 0.15);
      const col = n.alert > 0.01 ? BRAND.critical : n.color;
      coreG.circle(n.x + px, n.y + py, r).fill({ color: col, alpha: 0.9 * appearK });
      if (n.layer === 2) {
        coreG
          .circle(n.x + px, n.y + py, r + 1.5)
          .stroke({ color: col, alpha: 0.4 * appearK, width: 1 });
      }
    }

    // ── data pulses ──
    fxG.clear();
    for (const p of pulses) {
      if (!p.active || !p.a || !p.b) continue;
      p.t += (p.speed * dtMs) / 1000;
      if (p.t >= 1 || p.a.appear <= 0 || p.b.appear <= 0) {
        p.active = false;
        continue;
      }
      const x = lerp(p.a.x, p.b.x, p.t);
      const y = lerp(p.a.y, p.b.y, p.t);
      fxG.circle(x, y, p.size + 1.5).fill({ color: p.color, alpha: 0.25 });
      fxG.circle(x, y, p.size).fill({ color: p.color, alpha: 0.95 });
    }

    // ── ripples ──
    for (const r of ripples) {
      if (!r.active) continue;
      r.r += (r.max / 40) * dt;
      const k = r.r / r.max;
      if (k >= 1) {
        r.active = false;
        continue;
      }
      fxG.circle(r.x, r.y, r.r).stroke({ color: r.color, alpha: (1 - k) * 0.5, width: 1.5 });
    }

    // ── scan beam glow line ──
    if (scan.active) {
      fxG
        .rect(scan.x - 1, 0, 2, H())
        .fill({ color: BRAND.primary, alpha: 0.35 });
      fxG.rect(scan.x - 30, 0, 60, H()).fill({ color: BRAND.primary, alpha: 0.05 });
    }

    // ── labels (float + fade) ──
    for (let i = labels.length - 1; i >= 0; i--) {
      const L = labels[i];
      L.ttl -= dtMs;
      const p = 1 - L.ttl / L.max;
      const fade = p < 0.2 ? p / 0.2 : p > 0.8 ? (1 - p) / 0.2 : 1;
      if (L.node) {
        L.offY += 0.15 * dt;
        L.container.x = L.node.x + (L.text.anchor.x === 0 ? 12 : 0);
        L.container.y = L.node.y - 14 - L.offY;
      }
      L.container.alpha = Math.max(0, fade) * 0.9;
      if (L.ttl <= 0) {
        L.container.destroy();
        labels.splice(i, 1);
      }
    }

    // ── activity feed (bottom-left stack) ──
    let fy = H() - 24;
    for (let i = feed.length - 1; i >= 0; i--) {
      const F = feed[i];
      F.ttl -= dtMs;
      const p = 1 - F.ttl / F.max;
      const fade = p < 0.15 ? p / 0.15 : p > 0.85 ? (1 - p) / 0.15 : 1;
      F.container.x = 24;
      F.container.y = fy;
      F.container.alpha = Math.max(0, fade) * 0.85;
      fy -= 20;
      if (F.ttl <= 0) {
        F.container.destroy();
        feed.splice(i, 1);
      }
    }
  };

  app.ticker.add(tick);

  // reduced motion: render one static frame then stop the ticker
  if (reduced) {
    app.ticker.update();
    targetAlpha = 0.7;
    globalAlpha = 0.7;
    scene.alpha = 0.7;
    app.ticker.stop();
  }

  return {
    canvas: app.canvas,
    destroy() {
      window.removeEventListener("pointermove", onPointerMove);
      container.removeEventListener("pointerleave", onPointerLeave);
      container.removeEventListener("pointerdown", onPointerDown);
      app.ticker.remove(tick);
      glowTex.destroy(true);
      dotTex.destroy(true);
      app.destroy(true, { children: true, texture: true });
    },
    setPaused(p: boolean) {
      paused = p;
      if (p) app.ticker.stop();
      else if (!reduced) app.ticker.start();
    },
    setExclusion(rect: DOMRect | null) {
      exclusion = rect;
    },
    setGlobalAlpha(a: number) {
      targetAlpha = Math.max(0, Math.min(1, a));
    },
  };
}
