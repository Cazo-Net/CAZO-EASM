"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Wallet,
  ArrowLeft,
  ExternalLink,
  Copy,
  CheckCircle,
  XCircle,
  Clock,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Shield,
  Building2,
} from "lucide-react";
import Link from "next/link";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getRiskColor(score: number): string {
  if (score >= 80) return "text-red-400 bg-red-500/10 border-red-500/20";
  if (score >= 60) return "text-orange-400 bg-orange-500/10 border-orange-500/20";
  if (score >= 40) return "text-yellow-400 bg-yellow-500/10 border-yellow-500/20";
  if (score >= 20) return "text-blue-400 bg-blue-500/10 border-blue-500/20";
  return "text-green-400 bg-green-500/10 border-green-500/20";
}

function AddressDetailContent() {
  const params = useParams();
  const address = params.address as string;
  const chain = "ethereum";

  const [wallet, setWallet] = useState<any>(null);
  const [attribution, setAttribution] = useState<any>(null);
  const [risk, setRisk] = useState<any>(null);
  const [transactions, setTransactions] = useState<any>(null);
  const [txPage, setTxPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [txLoading, setTxLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const res = await fetch(
          `${API_BASE}/api/v1/blockchain/wallet/${address}?chain=${chain}`
        );
        if (res.ok) {
          const data = await res.json();
          setWallet(data.wallet);
          setAttribution(data.attribution);
          setRisk(data.risk);
        }
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }
    if (address) load();
  }, [address]);

  const loadTx = useCallback(
    async (page: number) => {
      setTxLoading(true);
      setTxPage(page);
      try {
        const res = await fetch(
          `${API_BASE}/api/v1/blockchain/wallet/${address}/transactions?chain=${chain}&page=${page}&page_size=20`
        );
        if (res.ok) {
          const data = await res.json();
          setTransactions(data);
        }
      } catch {
        // ignore
      } finally {
        setTxLoading(false);
      }
    },
    [address]
  );

  useEffect(() => {
    if (wallet) loadTx(1);
  }, [wallet, loadTx]);

  const handleCopy = () => {
    navigator.clipboard.writeText(address);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!wallet) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center gap-4">
        <p className="text-muted-foreground">Wallet not found</p>
        <Link href="/blockchain">
          <Button variant="outline">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Lookup
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-6xl mx-auto px-6 py-8">
        <Link
          href="/blockchain"
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-4"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back to Lookup
        </Link>

        <PageHeader
          title={`${wallet.wallet_type === "contract" ? "Contract" : "Wallet"} Analysis`}
          description={address}
          icon={<Wallet className="h-5 w-5" />}
        />

        {/* Wallet Header Card */}
        <div className="mt-6 border border-border rounded-lg p-6">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-lg font-medium">
                  {attribution?.entity || "Unknown Entity"}
                </h2>
                {attribution && (
                  <Badge variant="outline" className="text-xs">
                    {attribution.category}
                  </Badge>
                )}
              </div>
              <div className="flex items-center gap-2 mt-2">
                <code className="text-xs font-mono text-muted-foreground">
                  {address}
                </code>
                <button onClick={handleCopy} className="text-muted-foreground hover:text-foreground">
                  {copied ? (
                    <CheckCircle className="w-3.5 h-3.5 text-green-400" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                </button>
              </div>
            </div>
            {risk && (
              <div className="text-right">
                <div
                  className={`inline-flex items-center justify-center w-14 h-14 rounded-full border-2 ${getRiskColor(
                    risk.score
                  )}`}
                >
                  <span className="text-lg font-bold">{risk.score}</span>
                </div>
                <div className="mt-1">
                  <Badge variant="outline" className={`text-xs ${getRiskColor(risk.score)}`}>
                    {risk.band}
                  </Badge>
                </div>
              </div>
            )}
          </div>

          {/* Stats Row */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-6 pt-4 border-t border-border">
            <div>
              <div className="text-xs text-muted-foreground">Balance</div>
              <div className="text-sm font-medium mt-1">{wallet.balance} {chain === "bitcoin" ? "BTC" : "ETH"}</div>
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
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Transactions */}
          <div className="lg:col-span-2">
            <SectionCard title="Transaction History" icon={<Clock className="h-4 w-4" />}>
              {txLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : transactions?.items?.length > 0 ? (
                <div className="space-y-2">
                  {transactions.items.map((tx: any, i: number) => (
                    <div
                      key={tx.hash + i}
                      className="flex items-center justify-between p-3 border border-border rounded text-xs"
                    >
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
                            {tx.decoded_method || tx.method || "transfer"} &middot; Block #{tx.block_number}
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-medium">{tx.value} ETH</div>
                        {tx.fee && (
                          <div className="text-muted-foreground">Fee: {tx.fee} ETH</div>
                        )}
                      </div>
                    </div>
                  ))}

                  {/* Pagination */}
                  <div className="flex items-center justify-between pt-2">
                    <span className="text-xs text-muted-foreground">
                      Page {transactions.page}
                    </span>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={txPage <= 1}
                        onClick={() => loadTx(txPage - 1)}
                      >
                        <ChevronLeft className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={!transactions.has_next}
                        onClick={() => loadTx(txPage + 1)}
                      >
                        <ChevronRight className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No transactions found
                </p>
              )}
            </SectionCard>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Risk Factors */}
            {risk?.factors?.length > 0 && (
              <SectionCard title="Risk Factors" icon={<Shield className="h-4 w-4" />}>
                <div className="space-y-2">
                  {risk.factors.map((f: any, i: number) => (
                    <div
                      key={i}
                      className="flex items-center justify-between text-xs border border-border rounded p-2"
                    >
                      <span>{f.name}</span>
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
                  ))}
                </div>
              </SectionCard>
            )}

            {/* Attribution Evidence */}
            {attribution?.evidence?.length > 0 && (
              <SectionCard title="Attribution Evidence" icon={<Building2 className="h-4 w-4" />}>
                <div className="space-y-2">
                  {attribution.evidence.map((ev: any, i: number) => (
                    <div key={i} className="text-xs border border-border rounded p-2">
                      <div className="font-medium">{ev.source}</div>
                      <div className="text-muted-foreground mt-0.5">{ev.reason}</div>
                    </div>
                  ))}
                </div>
              </SectionCard>
            )}

            {/* External Links */}
            <SectionCard title="External" icon={<ExternalLink className="h-4 w-4" />}>
              <div className="space-y-2">
                <a
                  href={`https://etherscan.io/address/${address}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  View on Etherscan
                </a>
                <a
                  href={`https://www.blockchain.com/eth/address/${address}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  View on Blockchain.com
                </a>
              </div>
            </SectionCard>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AddressDetailPage() {
  return (
    <ProtectedRoute>
      <AddressDetailContent />
    </ProtectedRoute>
  );
}
