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
  Clock,
  CheckCircle,
  XCircle,
  Coins,
  Globe,
  FileWarning,
  ChevronLeft,
  ChevronRight,
  Copy,
} from "lucide-react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useBlockchainStore } from "@/lib/blockchainStore";

const CHAINS = [
  { value: "ethereum", label: "Ethereum", token: "ETH", color: "bg-blue-500" },
  { value: "bitcoin", label: "Bitcoin", token: "BTC", color: "bg-orange-500" },
  { value: "solana", label: "Solana", token: "SOL", color: "bg-purple-500" },
  { value: "polygon", label: "Polygon", token: "MATIC", color: "bg-violet-500" },
  { value: "bnb", label: "BNB Chain", token: "BNB", color: "bg-yellow-500" },
  { value: "arbitrum", label: "Arbitrum", token: "ETH", color: "bg-cyan-500" },
  { value: "optimism", label: "Optimism", token: "ETH", color: "bg-red-500" },
  { value: "base", label: "Base", token: "ETH", color: "bg-blue-400" },
  { value: "avalanche", label: "Avalanche", token: "AVAX", color: "bg-red-400" },
  { value: "tron", label: "Tron", token: "TRX", color: "bg-red-600" },
];

const EXPLORER_MAP: Record<string, string> = {
  ethereum: "etherscan.io",
  bitcoin: "blockstream.info",
  solana: "solscan.io",
  polygon: "polygonscan.com",
  bnb: "bscscan.com",
  arbitrum: "arbiscan.com",
  optimism: "optimistic.etherscan.io",
  base: "basescan.org",
  avalanche: "snowtrace.io",
  tron: "tronscan.org",
};

const EXAMPLE_ADDRESSES: Record<string, { address: string; label: string }[]> = {
  ethereum: [
    { address: "0xdAC17F958D2ee523a2206206994597C13D831ec7", label: "USDT (Tether)" },
    { address: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", label: "USDC (Circle)" },
    { address: "0x28C6c06298d514Db089934071355E5743bf21d60", label: "Binance Hot Wallet" },
  ],
  bitcoin: [
    { address: "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh", label: "Genesis Block" },
    { address: "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo", label: "Binance Cold Wallet" },
  ],
  solana: [
    { address: "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM", label: "Binance Hot Wallet" },
    { address: "5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9", label: "FTX Cold Wallet" },
  ],
  polygon: [
    { address: "0x37305B1cD40574E4C5Ce33f8e8306Be057fD7341", label: "Polygon Bridge" },
  ],
  bnb: [
    { address: "0x8894E0a0c962CB723c1ef8a1B676f17E857B6C42", label: "Binance Hot Wallet" },
  ],
  arbitrum: [
    { address: "0xc3a6FF0531E75D3487648161435D70b98F85c9D2", label: "Arbitrum Bridge" },
  ],
  optimism: [
    { address: "0x25ace71c97B33Cc4729CF772ae268934afc7521f", label: "Optimism Bridge" },
  ],
  base: [
    { address: "0x3154Cf16ccdb4C6d922629664174b904d80F2C35", label: "Base Bridge" },
  ],
  avalanche: [
    { address: "0x8b8731292F9bA492830E4696da2e52e2C6bAB0dC", label: "Avalanche Bridge" },
  ],
  tron: [
    { address: "TNaRAoLUyYEV2uEYXWfV2VQSEiF8bUjbYP", label: "Binance Hot Wallet" },
  ],
};

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
    txData,
    txLoading,
    tokens,
    intel,
    sanctions,
    contractDetail,
    lookupWallet,
    loadTransactions,
    setChain,
    reset,
  } = useBlockchainStore();

  const [localAddress, setLocalAddress] = useState(address);
  const [txPage, setTxPage] = useState(1);
  const [copied, setCopied] = useState(false);
  const selectedChain = CHAINS.find((c) => c.value === chain) || CHAINS[0];
  const chainExamples = EXAMPLE_ADDRESSES[chain] || EXAMPLE_ADDRESSES.ethereum;

  useEffect(() => {
    setLocalAddress(address);
  }, [address]);

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (localAddress.trim()) {
        lookupWallet(localAddress, chain);
        setTxPage(1);
      }
    },
    [localAddress, chain, lookupWallet]
  );

  const handleExampleClick = useCallback(
    (addr: string) => {
      setLocalAddress(addr);
      lookupWallet(addr, chain);
      setTxPage(1);
    },
    [chain, lookupWallet]
  );

  const handleCopy = () => {
    navigator.clipboard.writeText(address);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleTxPage = (page: number) => {
    setTxPage(page);
    loadTransactions(page);
  };

  const wallet = walletData?.wallet;
  const attribution = walletData?.attribution;
  const risk = walletData?.risk;

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-6 py-8">
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
                placeholder={`Search ${selectedChain.label} address...`}
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
                    {c.label} ({c.token})
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

          <div className="mt-3 flex flex-wrap gap-1.5">
            {CHAINS.map((c) => (
              <button
                key={c.value}
                onClick={() => setChain(c.value)}
                className={`inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-full border transition-colors ${
                  chain === c.value
                    ? "border-foreground/30 bg-foreground/10 text-foreground"
                    : "border-border text-muted-foreground hover:text-foreground hover:border-foreground/20"
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${c.color}`} />
                {c.label}
              </button>
            ))}
          </div>

          {!wallet && !walletLoading && (
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="text-xs text-muted-foreground mr-1">Try:</span>
              {chainExamples.map((ex) => (
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
            {/* Main Content */}
            <div className="lg:col-span-2 space-y-6">
              {/* Wallet Overview */}
              <SectionCard title="Wallet Overview" icon={<Wallet className="h-4 w-4" />}>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <code className="text-xs font-mono text-muted-foreground">{address}</code>
                      <button onClick={handleCopy} className="text-muted-foreground hover:text-foreground">
                        {copied ? <CheckCircle className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                    <Badge variant="outline" className="text-xs capitalize">{chain}</Badge>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <div className="text-xs text-muted-foreground">Balance</div>
                      <div className="text-sm font-medium mt-1">{wallet.balance} {selectedChain.token}</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">Transactions</div>
                      <div className="text-sm font-medium mt-1">{wallet.tx_count?.toLocaleString()}</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">Type</div>
                      <div className="text-sm font-medium mt-1 capitalize">{wallet.wallet_type}</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">Token Count</div>
                      <div className="text-sm font-medium mt-1">{wallet.token_count || tokens.length || 0}</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">First Seen</div>
                      <div className="text-sm font-medium mt-1">
                        {wallet.first_seen ? new Date(wallet.first_seen).toLocaleDateString() : "\u2014"}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">Last Active</div>
                      <div className="text-sm font-medium mt-1">
                        {wallet.last_active ? new Date(wallet.last_active).toLocaleDateString() : "\u2014"}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">Inbound Volume</div>
                      <div className="text-sm font-medium mt-1">{wallet.inbound_volume || "0"}</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">Outbound Volume</div>
                      <div className="text-sm font-medium mt-1">{wallet.outbound_volume || "0"}</div>
                    </div>
                  </div>
                </div>
              </SectionCard>

              {/* Contract Detail */}
              {contractDetail && (
                <SectionCard title="Contract Details" icon={<FileWarning className="h-4 w-4" />}>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-xs text-muted-foreground">Contract Name</div>
                      <div className="text-sm font-medium mt-1">{contractDetail.name || "\u2014"}</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">Type</div>
                      <div className="text-sm font-medium mt-1">{contractDetail.contract_type || "Unknown"}</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">Verified</div>
                      <div className="text-sm font-medium mt-1">{contractDetail.verified ? "Yes" : "No"}</div>
                    </div>
                  </div>
                </SectionCard>
              )}

              {/* Token Balances */}
              {tokens && tokens.length > 0 && (
                <SectionCard title="Token Balances" icon={<Coins className="h-4 w-4" />}>
                  <div className="space-y-2">
                    {tokens.map((t: any, i: number) => (
                      <div key={i} className="flex items-center justify-between text-xs border border-border rounded p-2">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{t.token_symbol || t.symbol}</span>
                          <span className="text-muted-foreground">{t.token_name || t.name}</span>
                        </div>
                        <span className="font-mono">{t.balance}</span>
                      </div>
                    ))}
                  </div>
                </SectionCard>
              )}

              {/* Attribution */}
              {attribution && attribution.entity_name && (
                <SectionCard title="Entity Attribution" icon={<Building2 className="h-4 w-4" />}>
                  <div className="space-y-3">
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-medium">{attribution.entity_name}</span>
                      <Badge variant="outline" className="text-xs">{attribution.category}</Badge>
                      <Badge variant="secondary" className="text-xs">{attribution.confidence}% confidence</Badge>
                    </div>
                    {attribution.evidence && attribution.evidence.length > 0 && (
                      <div className="space-y-2">
                        <div className="text-xs text-muted-foreground">Evidence</div>
                        {attribution.evidence.map((ev: any, i: number) => (
                          <div key={i} className="text-xs border border-border rounded p-2 flex items-start gap-2">
                            <span className="font-medium">{ev.source}:</span>
                            <span className="text-muted-foreground">{ev.reason}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </SectionCard>
              )}

              {/* Transaction History */}
              {txData && (
                <SectionCard title="Transaction History" icon={<Clock className="h-4 w-4" />}>
                  {txLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                    </div>
                  ) : txData.items && txData.items.length > 0 ? (
                    <div className="space-y-2">
                      {txData.items.map((tx: any, i: number) => (
                        <div key={tx.hash + i} className="flex items-center justify-between p-3 border border-border rounded text-xs">
                          <div className="flex items-center gap-3">
                            {tx.status === "success" ? (
                              <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
                            ) : (
                              <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                            )}
                            <div>
                              <div className="font-mono truncate max-w-[200px]" title={tx.hash}>
                                {tx.hash?.slice(0, 16)}...
                              </div>
                              <div className="text-muted-foreground mt-0.5">
                                {tx.decoded_method || tx.method || "transfer"} {tx.block_number ? `Block #${tx.block_number}` : ""}
                              </div>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="font-medium">{tx.value} {selectedChain.token}</div>
                            {tx.fee && <div className="text-muted-foreground">Fee: {tx.fee}</div>}
                            {tx.timestamp && (
                              <div className="text-muted-foreground">
                                {typeof tx.timestamp === "number"
                                  ? new Date(tx.timestamp).toLocaleDateString()
                                  : new Date(tx.timestamp).toLocaleDateString()}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                      <div className="flex items-center justify-between pt-2">
                        <span className="text-xs text-muted-foreground">Page {txData.page}</span>
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={txPage <= 1}
                            onClick={() => handleTxPage(txPage - 1)}
                          >
                            <ChevronLeft className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={!txData.has_next}
                            onClick={() => handleTxPage(txPage + 1)}
                          >
                            <ChevronRight className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground text-center py-8">No transactions found</p>
                  )}
                </SectionCard>
              )}

              {/* Sanctions / OFAC */}
              {sanctions && (
                <SectionCard title="Sanctions & Compliance" icon={<FileWarning className="h-4 w-4" />}>
                  <div className="space-y-2">
                    {sanctions.sanctioned ? (
                      <div className="text-xs bg-red-500/10 border border-red-500/20 rounded p-3 font-medium text-red-400 flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4" />
                        OFAC SANCTIONS MATCH: {sanctions.entity_name || sanctions.ofac?.entity_name || "Unknown"}
                      </div>
                    ) : (
                      <div className="text-xs text-green-400 flex items-center gap-2">
                        <CheckCircle className="w-4 h-4" />
                        Not on OFAC sanctions list
                      </div>
                    )}
                    {sanctions.ofac && (
                      <div className="text-xs border border-border rounded p-2 space-y-1">
                        {sanctions.ofac.entity_name && <div>Entity: {sanctions.ofac.entity_name}</div>}
                        {sanctions.ofac.program && <div>Program: {sanctions.ofac.program}</div>}
                        {sanctions.ofac_listed !== undefined && <div>Listed: {sanctions.ofac_listed ? "Yes" : "No"}</div>}
                      </div>
                    )}
                  </div>
                </SectionCard>
              )}

              {/* External Intel */}
              {intel && (
                <SectionCard title="External Intelligence" icon={<Globe className="h-4 w-4" />}>
                  <div className="space-y-2">
                    {intel.sanctioned && (
                      <div className="text-xs bg-red-500/10 border border-red-500/20 rounded p-2 font-medium text-red-400">
                        OFAC SANCTIONS MATCH: {intel.ofac?.entity_name}
                      </div>
                    )}
                    {intel.ofac && !intel.sanctioned && (
                      <div className="text-xs text-muted-foreground">OFAC: Not sanctioned</div>
                    )}
                    {intel.etherscan_labels && intel.etherscan_labels.length > 0 && (
                      <div className="space-y-1">
                        <div className="text-xs text-muted-foreground">Labels:</div>
                        {intel.etherscan_labels.map((l: any, i: number) => (
                          <div key={i} className="text-xs border border-border rounded p-2">
                            <span className="font-medium">{l.label}</span>
                            <span className="text-muted-foreground ml-2">({l.address?.slice(0, 10)}...)</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {intel.chainalysis && (
                      <div className="text-xs border border-border rounded p-2">
                        <span className="font-medium">Chainalysis:</span>{" "}
                        <span className="text-muted-foreground">{JSON.stringify(intel.chainalysis)}</span>
                      </div>
                    )}
                    {!intel.sanctioned && (!intel.etherscan_labels || intel.etherscan_labels.length === 0) && !intel.chainalysis && (
                      <div className="text-xs text-muted-foreground">No external intelligence available</div>
                    )}
                  </div>
                </SectionCard>
              )}
            </div>

            {/* Sidebar */}
            <div className="space-y-6">
              {/* Risk Score */}
              {risk && (
                <SectionCard title="Risk Assessment" icon={<Shield className="h-4 w-4" />}>
                  <div className="text-center py-4">
                    <div
                      className={`inline-flex items-center justify-center w-20 h-20 rounded-full border-2 ${getRiskColor(
                        risk.score
                      )}`}
                    >
                      <span className="text-2xl font-semibold">{risk.score}</span>
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
                        <div key={i} className="flex items-center justify-between text-xs border border-border rounded p-2">
                          <span>{f.label || f.name}</span>
                          <div className="flex items-center gap-2">
                            {f.weight && <span className="text-muted-foreground">&times;{f.weight}</span>}
                            <span
                              className={
                                (f.contribution || f.score || 0) >= 70
                                  ? "text-red-400"
                                  : (f.contribution || f.score || 0) >= 40
                                  ? "text-yellow-400"
                                  : "text-green-400"
                              }
                            >
                              {f.contribution || f.score || 0}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {risk.anomaly_score != null && (
                    <div className="mt-4 pt-4 border-t border-border">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground">Anomaly Score</span>
                        <span
                          className={
                            risk.anomaly_score > 0.7
                              ? "text-red-400 font-medium"
                              : risk.anomaly_score > 0.4
                              ? "text-yellow-400"
                              : "text-green-400"
                          }
                        >
                          {(risk.anomaly_score * 100).toFixed(1)}%
                        </span>
                      </div>
                    </div>
                  )}
                </SectionCard>
              )}

              {/* Actions */}
              <SectionCard title="Actions" icon={<Scale className="h-4 w-4" />}>
                <div className="space-y-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full justify-start"
                    onClick={() => window.open(`https://${EXPLORER_MAP[chain] || "etherscan.io"}/address/${address}`, "_blank")}
                  >
                    <ExternalLink className="w-4 h-4 mr-2" />
                    View on {EXPLORER_MAP[chain] || "Etherscan"}
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
            description="Enter an address above to begin cross-chain analysis."
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
