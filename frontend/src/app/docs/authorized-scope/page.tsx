import { DocsLayout } from "@/components/docs/DocsLayout";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "What is Authorized Scope? — CAZO Docs",
  description: "What a scope is, why you need it, and how CAZO enforces it.",
};

export default function AuthorizedScopeDocPage() {
  return (
    <DocsLayout>
      <article className="max-w-2xl">
        <h1 className="text-3xl font-semibold text-foreground">
          What is Authorized Scope, and why do I need it?
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          An authorized scope is a declaration of what you&rsquo;re allowed to
          scan. Before CAZO will run any scan, the target must be registered as
          an authorized scope for your organization.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Why scopes exist
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          CAZO actively scans the public internet. Without scope enforcement, a
          user could (accidentally or intentionally) scan infrastructure they
          don&rsquo;t own. That creates legal risk for you, for CAZO, and for
          the target operator.
        </p>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          Scopes exist to ensure every scan has a legitimate authorization
          basis. They protect you by creating a clear record of what you
          authorized and when.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Scope types
        </h2>
        <ul className="mt-3 space-y-3 text-sm text-muted-foreground">
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-phosphor" />
            <span>
              <strong className="text-foreground">Domain:</strong>{" "}
              <code className="text-xs">example.com</code> — authorizes this
              exact domain and its directly observed subdomains.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-signal" />
            <span>
              <strong className="text-foreground">Wildcard:</strong>{" "}
              <code className="text-xs">*.example.com</code> — authorizes all
              subdomains of example.com (api.example.com, staging.example.com,
              etc.) plus the apex domain.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-neon-violet" />
            <span>
              <strong className="text-foreground">IP:</strong>{" "}
              <code className="text-xs">52.14.89.103</code> — authorizes a
              single IP address.
            </span>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber" />
            <span>
              <strong className="text-foreground">CIDR:</strong>{" "}
              <code className="text-xs">52.14.89.0/24</code> — authorizes an
              entire IP range. Use this for cloud providers where you control a
              block.
            </span>
          </li>
        </ul>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          How enforcement works
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          When you create a scan, CAZO checks the target against your
          organization&rsquo;s registered scopes before the scan runs. If the
          target doesn&rsquo;t match any scope, the scan is blocked with a 403
          error and the attempt is logged.
        </p>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          This check happens server-side and cannot be bypassed through the UI or
          API.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          Private IP blocking
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          Regardless of your scope configuration, CAZO always blocks scans
          against private, loopback, reserved, and link-local IP addresses
          (10.x.x.x, 192.168.x.x, 127.x.x.x, etc.). This prevents SSRF
          attacks where someone could use CAZO to scan internal networks.
        </p>

        <h2 className="mt-10 text-xl font-semibold text-foreground">
          The Note field
        </h2>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          When you add a scope, you can record your authorization basis in the
          Note field. This is optional but strongly recommended. If a third party
          ever disputes your scan, this note becomes part of your audit trail.
        </p>
        <p className="mt-3 text-sm text-muted-foreground">
          Examples:
        </p>
        <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
          <li>&ldquo;Own infrastructure &mdash; Acme Corp&rdquo;</li>
          <li>&ldquo;Authorized via SOW #2024-0312&rdquo;</li>
          <li>&ldquo;Bug bounty: example.com/security&rdquo;</li>
        </ul>

        <div className="mt-10 rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-muted-foreground">
            See also:{" "}
            <Link href="/legal/authorized-scanning" className="text-phosphor hover:underline">
              Authorized Scanning Policy
            </Link>{" "}
            &middot;{" "}
            <Link href="/docs/scan-statuses" className="text-phosphor hover:underline">
              Why &ldquo;blocked by CDN&rdquo;?
            </Link>
          </p>
        </div>
      </article>
    </DocsLayout>
  );
}
