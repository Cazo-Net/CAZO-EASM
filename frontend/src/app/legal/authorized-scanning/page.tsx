import { LegalLayout } from "@/components/legal/LegalLayout";
import Link from "next/link";

export const metadata = {
  title: "Authorized Scanning Policy — CAZO EASM",
  description: "Your responsibilities when using CAZO to scan targets.",
};

export default function AuthorizedScanningPage() {
  return (
    <LegalLayout lastUpdated="July 2026">
      <h1>Authorized Scanning Policy</h1>

      <p>
        This policy describes your responsibilities when using CAZO to scan
        targets. It is a binding part of your agreement with CAZO.
      </p>

      <h2>Your Authorization Obligations</h2>
      <p>
        Before adding any target to your CAZO scope, you must have one of:
      </p>
      <ol>
        <li>
          <strong>Ownership:</strong> You own the target domain, IP block, or
          infrastructure.
        </li>
        <li>
          <strong>Written authorization:</strong> The owner has given you
          explicit, documented permission to perform security testing on the
          target.
        </li>
        <li>
          <strong>Bug bounty / responsible disclosure:</strong> The target
          operator has a published policy that permits the type of scanning
          you&rsquo;re performing.
        </li>
      </ol>
      <p>
        &ldquo;Probably mine&rdquo; is not authorization. &ldquo;I think we own
        that&rdquo; is not authorization. If you cannot point to a specific
        basis for your authorization, do not add the target.
      </p>

      <h2>What CAZO Enforces (Technical Controls)</h2>
      <p>CAZO applies the following server-side checks:</p>
      <ul>
        <li>
          <strong>Scope registration required:</strong> No scan can run against a
          target that isn&rsquo;t registered as an authorized scope for your
          organization. In production, an organization with zero configured
          scopes cannot run any scans.
        </li>
        <li>
          <strong>Target matching:</strong> Each scan target is validated against
          your registered scopes (exact domain, wildcard, IP, or CIDR match)
          before execution.
        </li>
        <li>
          <strong>Private IP blocking:</strong> Targets on private, loopback,
          reserved, or link-local networks are always blocked &mdash; regardless
          of your scope configuration. This prevents SSRF attacks.
        </li>
        <li>
          <strong>Audit trail:</strong> Every scope creation, scope deletion, and
          scan attempt (authorized or denied) is logged with: who performed the
          action, when, what target, and the authorization basis.
        </li>
      </ul>
      <p>
        These controls are automated and non-bypassable within the Platform.
      </p>

      <h2>What CAZO Does NOT Enforce (Your Responsibility)</h2>
      <p>
        CAZO&rsquo;s technical controls verify that a target matches a registered
        scope. They do <strong>not</strong> verify that your authorization to
        scan that scope is valid or current. Specifically:
      </p>
      <ul>
        <li>
          CAZO does not independently verify that you own the domain you
          registered
        </li>
        <li>
          CAZO does not check whether a third-party has revoked your
          authorization
        </li>
        <li>
          CAZO does not verify that your scanning activity complies with the
          target operator&rsquo;s terms of service or acceptable use policy
        </li>
      </ul>
      <p>
        <strong>
          You are legally responsible for the accuracy of your scope
          authorizations.
        </strong>
      </p>

      <h2>If a Third Party Disputes Your Scan</h2>
      <p>If a third party claims your scan was unauthorized:</p>
      <ol>
        <li>
          CAZO will provide our audit trail showing: when you added the scope,
          what authorization basis you recorded, when scans ran against that
          scope, and who performed those actions.
        </li>
        <li>
          This audit trail is your evidence. Keep your scope registrations
          accurate and your authorization documentation current.
        </li>
        <li>
          CAZO may suspend the disputed scope pending resolution. We will notify
          you and provide the audit data you need to respond.
        </li>
      </ol>

      <h2>Scope Verification (Optional)</h2>
      <p>
        CAZO supports optional DNS TXT record verification for domains. When
        enabled, you prove domain ownership by adding a{" "}
        <code>_cazo-verify.&lt;domain&gt;</code> TXT record. This is not
        currently required but may be required for certain features in the
        future.
      </p>

      <h2>Scope Notes</h2>
      <p>
        When adding a scope, you can (and should) record your authorization basis
        in the &ldquo;Note&rdquo; field. Examples:
      </p>
      <ul>
        <li>&ldquo;Own infrastructure &mdash; Acme Corp&rdquo;</li>
        <li>
          &ldquo;Authorized via SOW #2024-0312 with Example Inc&rdquo;
        </li>
        <li>
          &ldquo;Bug bounty program: example.com/security&rdquo;
        </li>
      </ul>
      <p>This note becomes part of your audit trail.</p>

      <h2>Consequences of Violations</h2>
      <p>Scanning targets without authorization may result in:</p>
      <ul>
        <li>Immediate suspension of the disputed scope</li>
        <li>Suspension of your account pending review</li>
        <li>Permanent termination for repeated or willful violations</li>
        <li>Cooperation with law enforcement if required</li>
      </ul>
      <p>
        We take unauthorized scanning seriously &mdash; both for legal protection
        and because it undermines trust in the security testing community.
      </p>

      <h2>This Policy May Change</h2>
      <p>
        We may update this policy. Material changes will be communicated via
        email and in-app notification. Continued use of scope-adding features
        after changes take effect constitutes acceptance.
      </p>
    </LegalLayout>
  );
}
