"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Globe, Loader2, Radar, ChevronDown, ChevronUp } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import api, { getErrorMessage } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

type Profile = "quick" | "full" | "custom";

const PROFILES: { value: Profile; label: string; desc: string }[] = [
  { value: "quick", label: "Quick", desc: "Top 20 subs, fast ports (pure code)" },
  { value: "full", label: "Full", desc: "All subs, full ports, CVE correlation" },
  { value: "custom", label: "Custom", desc: "Choose your own options" },
];

const TOOL_OPTIONS = [
  { value: "default", label: "crt.sh / OTX" },
  { value: "bruteforce", label: "DNS Brute-force" },
  { value: "permutations", label: "Permutations" },
] as const;

export function ScanForm() {
  const router = useRouter();
  const [domain, setDomain] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [profile, setProfile] = useState<Profile>("full");
  const [showFilters, setShowFilters] = useState(false);

  // Custom filter state
  const [maxSubs, setMaxSubs] = useState(0);
  const [portMode, setPortMode] = useState<"quick" | "full">("full");
  const [selectedTools, setSelectedTools] = useState<string[]>(["default", "bruteforce", "permutations"]);

  const toggleTool = (tool: string) => {
    setSelectedTools((prev) =>
      prev.includes(tool) ? prev.filter((t) => t !== tool) : [...prev, tool]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!domain.trim()) {
      setError("Please enter a domain");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const scanOptions =
        profile === "custom"
          ? {
              scan_size: maxSubs > 20 ? "large" : "small",
              max_subdomains: maxSubs,
              port_mode: portMode,
              subdomain_tools: selectedTools,
            }
          : undefined;

      const response = await api.post("/scans", {
        domain: domain.trim(),
        scan_type: profile,
        ...(scanOptions ? { scan_options: scanOptions } : {}),
      });
      router.push(`/scan/${response.data.id}`);
    } catch (err: any) {
      setError(getErrorMessage(err, "Failed to create scan"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-xl border border-border/50 bg-card/60 backdrop-blur-xl overflow-hidden">
      <div className="px-5 pt-5 pb-3">
        <div className="flex items-center gap-2 mb-1">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand/10">
            <Radar className="h-3.5 w-3.5 text-brand" />
          </div>
          <h3 className="text-sm font-semibold font-display">Start New Scan</h3>
        </div>
        <p className="text-xs text-muted-foreground pl-9">
          Enter a domain to discover subdomains, ports, SSL certs, and
          technologies.
        </p>
      </div>
      <div className="px-5 pb-5">
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="relative">
            <Globe className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="example.com"
              value={domain}
              onChange={(e) => {
                setDomain(e.target.value);
                setError("");
              }}
              disabled={loading}
              className="h-11 pl-11 pr-4 bg-muted/30 border-border/50 focus:border-primary/50 focus:ring-primary/20 text-sm"
            />
          </div>

          {/* Profile selector */}
          <div className="flex gap-2">
            {PROFILES.map((p) => (
              <button
                key={p.value}
                type="button"
                onClick={() => setProfile(p.value)}
                className={`flex-1 rounded-lg px-3 py-2 text-xs font-medium border transition-all ${
                  profile === p.value
                    ? "bg-primary/10 border-primary/50 text-primary"
                    : "bg-muted/30 border-border/50 text-muted-foreground hover:bg-muted/50"
                }`}
              >
                <div>{p.label}</div>
                <div className="text-[10px] font-normal mt-0.5 opacity-70">{p.desc}</div>
              </button>
            ))}
          </div>

          {/* Custom filter toggle */}
          {profile === "custom" && (
            <button
              type="button"
              onClick={() => setShowFilters(!showFilters)}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {showFilters ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              {showFilters ? "Hide filters" : "Show filters"}
            </button>
          )}

          {/* Vulnerability note — pure-code detection (no Nuclei binary) */}
          <p className="text-[10px] text-muted-foreground/70 leading-relaxed">
            Vulnerabilities are detected in pure Python: heuristic misconfig
            checks + version-based CVE correlation against a local NVD snapshot.
            Findings are marked UNVERIFIED (no live exploit verification).
          </p>

          {/* Custom filter panel */}
          <AnimatePresence>
            {profile === "custom" && showFilters && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="space-y-3 overflow-hidden"
              >
                {/* Max subdomains */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">
                    Max subdomains (0 = unlimited)
                  </label>
                  <Input
                    type="number"
                    min={0}
                    value={maxSubs}
                    onChange={(e) => setMaxSubs(Number(e.target.value))}
                    className="h-9 bg-muted/30 border-border/50 text-sm"
                  />
                </div>

                {/* Port mode */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">Port scan mode</label>
                  <div className="flex gap-2">
                    {(["quick", "full"] as const).map((mode) => (
                      <button
                        key={mode}
                        type="button"
                        onClick={() => setPortMode(mode)}
                        className={`flex-1 rounded-lg px-3 py-1.5 text-xs font-medium border transition-all ${
                          portMode === mode
                            ? "bg-primary/10 border-primary/50 text-primary"
                            : "bg-muted/30 border-border/50 text-muted-foreground hover:bg-muted/50"
                        }`}
                      >
                        {mode === "quick" ? "Quick (top ports)" : "Full (1-9999)"}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Subdomain tools */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">
                    Subdomain sources
                  </label>
                  <div className="flex gap-2">
                    {TOOL_OPTIONS.map((tool) => (
                      <button
                        key={tool.value}
                        type="button"
                        onClick={() => toggleTool(tool.value)}
                        className={`rounded-lg px-3 py-1.5 text-xs font-medium border transition-all ${
                          selectedTools.includes(tool.value)
                            ? "bg-primary/10 border-primary/50 text-primary"
                            : "bg-muted/30 border-border/50 text-muted-foreground hover:bg-muted/50"
                        }`}
                      >
                        {tool.label}
                      </button>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <Button
            type="submit"
            disabled={loading || !domain.trim()}
            className="w-full h-10 bg-gradient-to-r from-primary to-cyan-signal hover:from-primary/90 hover:to-cyan-signal/90 text-brand-foreground font-medium shadow-glow-sm transition-all"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Globe className="h-4 w-4" />
            )}
            Scan
          </Button>
        </form>
        <AnimatePresence>
          {error && (
            <motion.p
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-3 text-sm text-destructive text-center"
            >
              {error}
            </motion.p>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
