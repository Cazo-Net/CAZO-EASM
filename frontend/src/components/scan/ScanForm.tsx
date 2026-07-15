"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Globe, Loader2, Radar } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import api from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export function ScanForm() {
  const router = useRouter();
  const [domain, setDomain] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!domain.trim()) {
      setError("Please enter a domain");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await api.post("/scans", {
        domain: domain.trim(),
        scan_type: "full",
      });
      router.push(`/scan/${response.data.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to create scan");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-xl border border-border/50 bg-card/60 backdrop-blur-xl overflow-hidden">
      <div className="px-5 pt-5 pb-3">
        <div className="flex items-center gap-2 mb-1">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10">
            <Radar className="h-3.5 w-3.5 text-primary" />
          </div>
          <h3 className="text-sm font-semibold">Start New Scan</h3>
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
          <Button
            type="submit"
            disabled={loading || !domain.trim()}
            className="w-full h-10 bg-gradient-to-r from-primary to-cyan-500 hover:from-primary/90 hover:to-cyan-500/90 text-primary-foreground font-medium shadow-lg shadow-primary/25 transition-all"
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
