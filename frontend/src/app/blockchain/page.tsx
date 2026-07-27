"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Search,
  Wallet,
  Loader2,
  Shield,
  AlertTriangle,
  Building2,
  Scale,
  ExternalLink,
  RotateCcw,
} from "lucide-react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { useBlockchainStore } from "@/lib/blockchainStore";

const CHAINS = [
  { value: "ethereum", label: "Ethereum" },
  { value: "bitcoin", label: "Bitcoin" },
];

const EXAMPLE_ADDRESSES = [
  { address: "0xdAC17F958D2ee523a2206206994597C13D831ec7", label: "USDT (Tether)" },
  { address: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", label: "USDC (Circle)" },
  { address: "0x28C6c06298d514Db089934071355E5743bf21d60", label: "Binance Hot Wallet" },
];

function getRiskColor(score: number): string {
  if (score >= 80) return "text-red-400 bg-red-500/10 border-red-500/20";
  if (score >= 60) return "text-orange-400 bg-orange-500/10 border-orange-500/20";
  if (score >= 40) return "text-yellow-400 bg-yellow-500/10 border-yellow-500/20";
  if (score >= 20) return "text-blue-400 bg-blue-500/10 border-blue-500/20";
  return "text-green-400 bg-green-500/10 border-green-500/20";
}

function BlockchainContent() {
  const {
    address,
    chain,
    walletData,
    walletLoading,
    walletError,
    lookupWallet,
    setChain,
    reset,
  } = useBlockchainStore();

  const [localAddress, setLocalAddress] = useState(address);

  useEffect(() => {
    setLocalAddress(address);
  }, [address]);

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (localAddress.trim()) {
        lookupWallet(localAddress, chain);
      }
    },
    [localAddress, chain, lookupWallet]
  );

  const handleExampleClick = useCallback(
    (addr: string) => {
      setLocalAddress(addr);
      lookupWallet(addr, chain);
    },
    [chain, lookupWallet]
  );

  const wallet = walletData?.wallet;
  const attribution = walletData?.attribution;
  const risk = walletData?.risk;

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-6xl mx-auto px-6 py-8">
        <PageHeader
          title="Blockchain Intelligence"
          description="Wallet analysis, entity attribution, and on-chain risk scoring"
          icon={<Wallet className="h-5 w-5" />}
        />

        {/* Search */}
        <SectionCard title="Wallet Lookup" icon={<Search className="h-4 w-4" />} className="mt-6">
          <form onSubmit={handleSearch} className="flex gap-3">
            <div className="flex-1 flex gap-2">
              <Input
                placeholder="0x... or enter address"
                value={localAddress}
                onChange={(e) => setLocalAddress(e.target.value)}
                className="font-mono text-sm"
              />
              <select
                value={chain}
                onChange={(e) => setChain(e.target.value)}
                className="border border-border rounded-md bg-background px-3 text-sm"
              >
                {CHAINS.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>
            <Button type="submit" disabled={walletLoading || !localAddress.trim()}>
              {walletLoading ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <Search className="w-4 h-4 mr-2" />
              )}
              Lookup
            </Button>
          </form>

          {/* Example addresses */}
          {!wallet && !walletLoading && (
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="text-xs text-muted-foreground mr-1">Try:</span>
              {EXAMPLE_ADDRESSES.map((ex) => (
                <button
                  key={ex.address}
                  onClick={() => handleExampleClick(ex.address)}
                  className="text-xs font-mono text-muted-foreground hover:text-foreground border border-border rounded px-2 py-1 transition-colors"
                >
                  {ex.label}
                </button>
              ))}
            </div>
          )}
        </SectionCard>

        {/* Error */}
        {walletError && (
          <div className="mt-4 p-4 border border-red-500/20 bg-red-500/5 rounded-lg text-red-400 text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            {walletError}
          </div>
        )}

        {/* Results */}
        {wallet && (
          <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Wallet Overview */}
            <div className="lg:col-span-2 space-y-6">
              <SectionCard title="Wallet Overview" icon={<Wallet className="h-4 w-4" />}>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <div className="text-xs text-muted-foreground">Address</div>
                    <div className="font-mono text-sm mt-1 truncate" title={wallet.address}>
                      {wallet.address?.slice(0, 10)}...{wallet.address?.slice(-8)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Chain</div>
                    <div className="text-sm mt-1 capitalize">{wallet.chain}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Type</div>
                    <div className="text-sm mt-1 capitalize">{wallet.wallet_type}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Balance</div>
                    <div className="text-sm mt-1">{wallet.balance} {chain === "bitcoin" ? "BTC" : "ETH"}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Transactions</div>
                    <div className="text-sm mt-1">{wallet.tx_count?.toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">First Seen</div>
                    <div className="text-sm mt-1">
                      {wallet.first_seen
                        ? new Date(wallet.first_seen).toLocaleDateString()
                        : "\u2014"}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Last Active</div>
                    <div className="text-sm mt-1">
                      {wallet.last_active
                        ? new Date(wallet.last_active).toLocaleDateString()
                        : "\u2014"}
                    </div>
                  </div>
                </div>
              </SectionCard>

              {/* Attribution */}
              {attribution && (
                <SectionCard title="Entity Attribution" icon={<Building2 className="h-4 w-4" />}>
                  <div className="space-y-3">
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-medium">
                        {attribution.entity || "Unknown Entity"}
                      </span>
                      <Badge variant="outline" className="text-xs">
                        {attribution.category}
                      </Badge>
                      <Badge variant="secondary" className="text-xs">
                        {attribution.confidence}% confidence
                      </Badge>
                    </div>
                    {attribution.evidence && attribution.evidence.length > 0 && (
                      <div className="space-y-2">
                        <div className="text-xs text-muted-foreground">Evidence</div>
                        {attribution.evidence.map((ev: any, i: number) => (
                          <div
                            key={i}
                            className="text-xs border border-border rounded p-2 flex items-start gap-2"
                          >
                            <span className="font-medium">{ev.source}:</span>
                            <span className="text-muted-foreground">{ev.reason}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </SectionCard>
              )}
            </div>

            {/* Risk Score Sidebar */}
            <div className="space-y-6">
              {risk && (
                <SectionCard title="Risk Assessment" icon={<Shield className="h-4 w-4" />}>
                  <div className="text-center py-4">
                    <div
                      className={`inline-flex items-center justify-center w-20 h-20 rounded-full border-2 ${getRiskColor(
                        risk.score
                      )}`}
                    >
                      <span className="text-2xl font-bold">{risk.score}</span>
                    </div>
                    <div className="mt-2">
                      <Badge variant="outline" className={getRiskColor(risk.score)}>
                        {risk.band}
                      </Badge>
                    </div>
                  </div>

                  {risk.factors && risk.factors.length > 0 && (
                    <div className="mt-4 space-y-2">
                      <div className="text-xs text-muted-foreground">Risk Factors</div>
                      {risk.factors.map((f: any, i: number) => (
                        <div
                          key={i}
                          className="flex items-center justify-between text-xs border border-border rounded p-2"
                        >
                          <span>{f.name}</span>
                          <div className="flex items-center gap-2">
                            <span className="text-muted-foreground">&times;{f.weight}</span>
                            <span
                              className={
                                f.score >= 70
                                  ? "text-red-400"
                                  : f.score >= 40
                                  ? "text-yellow-400"
                                  : "text-green-400"
                              }
                            >
                              {f.score}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </SectionCard>
              )}

              {/* Quick Actions */}
              <SectionCard title="Actions" icon={<Scale className="h-4 w-4" />}>
                <div className="space-y-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full justify-start"
                    onClick={() => window.open(`https://etherscan.io/address/${address}`, "_blank")}
                  >
                    <ExternalLink className="w-4 h-4 mr-2" />
                    View on Etherscan
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full justify-start"
                    onClick={reset}
                  >
                    <RotateCcw className="w-4 h-4 mr-2" />
                    Clear Results
                  </Button>
                </div>
              </SectionCard>
            </div>
          </div>
        )}

        {/* Empty state */}
        {!wallet && !walletLoading && !walletError && (
          <EmptyState
            icon={<Wallet className="h-8 w-8" />}
            title="No wallet analyzed"
            description="Enter an Ethereum or Bitcoin address above to begin analysis."
          />
        )}
      </div>
    </div>
  );
}

export default function BlockchainPage() {
  return (
    <ProtectedRoute>
      <BlockchainContent />
    </ProtectedRoute>
  );
}
