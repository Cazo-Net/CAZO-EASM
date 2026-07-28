import { DocsLayout } from "@/components/docs/DocsLayout";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Blockchain Intelligence — CAZO Docs",
  description: "Cross-chain wallet analysis, entity attribution, and on-chain risk scoring across 10 blockchains.",
};

export default function BlockchainIntelDocPage() {
  return (
    <DocsLayout>
      <article className="max-w-2xl">
        <h1 className="font-display text-3xl font-semibold text-foreground">
          Blockchain Intelligence
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          CAZO monitors wallet activity, entity attribution, and on-chain risk
          across 10 blockchains. Enter any wallet address to get instant risk
          scoring, transaction history, and entity intelligence.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Supported Chains
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          CAZO supports the following blockchains natively:
        </p>
        <div className="mt-4 grid grid-cols-2 gap-3">
          {[
            { chain: "Ethereum", token: "ETH", color: "bg-blue-500" },
            { chain: "Bitcoin", token: "BTC", color: "bg-orange-500" },
            { chain: "Solana", token: "SOL", color: "bg-purple-500" },
            { chain: "Polygon", token: "MATIC", color: "bg-violet-500" },
            { chain: "BNB Chain", token: "BNB", color: "bg-yellow-500" },
            { chain: "Arbitrum", token: "ETH", color: "bg-cyan-500" },
            { chain: "Optimism", token: "ETH", color: "bg-red-500" },
            { chain: "Base", token: "ETH", color: "bg-blue-400" },
            { chain: "Avalanche", token: "AVAX", color: "bg-red-400" },
            { chain: "Tron", token: "TRX", color: "bg-red-600" },
          ].map((c) => (
            <div
              key={c.chain}
              className="flex items-center gap-2 rounded-lg border border-border/50 bg-card/40 p-3"
            >
              <span className={`h-2.5 w-2.5 rounded-full ${c.color}`} />
              <div>
                <div className="text-sm font-medium text-foreground">{c.chain}</div>
                <div className="text-xs text-muted-foreground">{c.token}</div>
              </div>
            </div>
          ))}
        </div>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          What you get
        </h2>
        <ul className="mt-4 space-y-3 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>
              <strong className="text-foreground">Risk scoring:</strong> A 0–100
              score based on transaction patterns, known associations, and
              behavioral signals.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-signal" />
            <span>
              <strong className="text-foreground">Entity attribution:</strong>{" "}
              Identify whether a wallet belongs to an exchange, DeFi protocol,
              mixer, or known threat actor.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-neon-violet" />
            <span>
              <strong className="text-foreground">Sanctions screening:</strong>{" "}
              Automatic OFAC SDN list matching against 21+ known illicit
              addresses (Lazarus Group, Tornado Cash, Garantex, etc.).
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber" />
            <span>
              <strong className="text-foreground">Cross-chain tracing:</strong>{" "}
              Bridge interaction detection and cross-chain fund flow analysis.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-signal-red" />
            <span>
              <strong className="text-foreground">Anomaly detection:</strong>{" "}
              ML-powered behavioral analysis flagging unusual transaction
              patterns.
            </span>
          </li>
        </ul>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          How to use it
        </h2>
        <ol className="mt-3 space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground/60">1.</span>
            <span>
              Navigate to <strong className="text-foreground">Blockchain Intel</strong> in the
              sidebar.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground/60">2.</span>
            <span>
              Select the chain from the chip selector (Ethereum, Bitcoin, Solana,
              etc.).
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground/60">3.</span>
            <span>
              Paste a wallet address and click <strong className="text-foreground">Lookup</strong>.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground/60">4.</span>
            <span>
              Review the risk score, entity attribution, transaction history,
              and any sanctions matches.
            </span>
          </li>
        </ol>

        <div className="mt-6 rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-4">
          <p className="text-sm text-muted-foreground">
            <strong className="text-yellow-400">Note:</strong> Blockchain
            intelligence requires API keys for each chain. Add{" "}
            <code className="text-xs text-foreground/70">ETHERSCAN_API_KEY</code>{" "}
            (and equivalent keys for other chains) to your backend environment
            for live data. Without keys, CAZO returns simulated data.
          </p>
        </div>

        <div className="mt-10 rounded-xl border border-border/50 bg-card/40 p-5">
          <p className="text-sm text-muted-foreground">
            See also:{" "}
            <Link href="/docs/threat-score" className="text-phosphor hover:underline">
              Threat Exposure Score
            </Link>{" "}
            &middot;{" "}
            <Link href="/docs/glossary" className="text-phosphor hover:underline">
              Glossary
            </Link>
          </p>
        </div>
      </article>
    </DocsLayout>
  );
}
