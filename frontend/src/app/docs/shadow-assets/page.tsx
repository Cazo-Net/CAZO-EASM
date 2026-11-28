import { DocsLayout } from "@/components/docs/DocsLayout";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "What is a Shadow Asset? — CAZO Docs",
  description: "How CAZO discovers assets you forgot you own and what the confidence score means.",
};

export default function ShadowAssetsDocPage() {
  return (
    <DocsLayout>
      <article className="max-w-2xl">
        <h1 className="text-3xl font-semibold text-foreground">
          What is a Shadow Asset?
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          A shadow asset is an internet-facing resource that&rsquo;s probably
          yours but isn&rsquo;t in your confirmed inventory. It&rsquo;s the
          staging box someone set up and forgot about, the old vendor subdomain
          nobody remembers, the certificate reused on infrastructure that
          isn&rsquo;t in your asset list.
        </p>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          These are often the riskiest assets — because nobody&rsquo;s watching
          them, nobody&rsquo;s patching them, and nobody remembers they exist
          until something goes wrong.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          How CAZO discovers them
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          CAZO doesn&rsquo;t just list what you tell it to look for. It
          discovers your perimeter from the outside and then correlates
          infrastructure to find things that probably belong to you. The three
          main signals:
        </p>
        <ul className="mt-4 space-y-3 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>
              <strong className="text-foreground">Shared IP:</strong> A host
              resolves to the same IP address as a confirmed asset. If
              you&rsquo;re on shared hosting, this is common — but it can also
              reveal a forgotten service on your own infrastructure.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-signal" />
            <span>
              <strong className="text-foreground">Shared certificate:</strong>{" "}
              A host presents the same TLS certificate as a confirmed asset.
              Certificates often cover multiple domains — this reveals
              infrastructure you may not have inventoried.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-neon-violet" />
            <span>
              <strong className="text-foreground">Shared ASN:</strong> A host
              is announced by the same Autonomous System Number as your confirmed
              assets. This suggests the host is operated by the same network
              owner — you.
            </span>
          </li>
        </ul>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Confidence scoring
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          Each shadow asset candidate gets a confidence score — a percentage
          representing how likely it is that this asset belongs to you. The
          score is based on:
        </p>
        <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber" />
            <span>
              How many signals matched (shared IP + shared cert + shared ASN is
              stronger than just one)
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber" />
            <span>
              How specific the signals are (a wildcard cert covering 10,000
              domains is weaker than a cert covering 3 domains)
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber" />
            <span>
              Whether the host was discovered alongside confirmed assets vs.
              independently
            </span>
          </li>
        </ul>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          A score of 82% means &ldquo;we&rsquo;re fairly confident this is
          yours, but we can&rsquo;t be 100% certain without your confirmation.&rdquo;
          It&rsquo;s a signal for you to investigate, not a verdict.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          What to do with shadow assets
        </h2>
        <ol className="mt-3 space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground">
              1.
            </span>
            <span>
              <strong className="text-foreground">Review:</strong> Look at the
              signals. Does this look like yours?
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground">
              2.
            </span>
            <span>
              <strong className="text-foreground">Confirm or dismiss:</strong>{" "}
              If it&rsquo;s yours, confirm it — it joins your regular inventory
              and gets monitored. If it&rsquo;s not, dismiss it.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 text-xs font-mono text-muted-foreground">
              3.
            </span>
            <span>
              <strong className="text-foreground">Investigate:</strong>{" "}
              Unconfirmed shadow assets are often the ones with the most risk.
              They may have outdated software, no monitoring, and no incident
              response plan.
            </span>
          </li>
        </ol>

        <div className="mt-10 rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-muted-foreground">
            See also:{" "}
            <Link href="/docs/evidence-panel" className="text-phosphor hover:underline">
              Reading the Evidence Panel
            </Link>{" "}
            &middot;{" "}
            <Link href="/docs/threat-score" className="text-phosphor hover:underline">
              Threat Exposure Score
            </Link>
          </p>
        </div>
      </article>
    </DocsLayout>
  );
}
