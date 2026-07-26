import { LegalLayout } from "@/components/legal/LegalLayout";
import Link from "next/link";

export const metadata = {
  title: "Terms of Service — CAZO EASM",
  description: "Terms governing your use of CAZO External Attack Surface Management.",
};

export default function TermsPage() {
  return (
    <LegalLayout lastUpdated="July 2026">
      <h1>Terms of Service</h1>

      <p>
        These Terms of Service (&ldquo;Terms&rdquo;) govern your use of CAZO EASM
        (&ldquo;the Platform&rdquo;), operated by CAZO (&ldquo;we&rdquo;,
        &ldquo;us&rdquo;). By creating an account or using the Platform, you
        agree to these Terms.
      </p>

      <h2>1. Account Terms</h2>
      <p>
        You must be at least 18 years old to use CAZO. You&rsquo;re responsible
        for all activity under your account. Keep your credentials secure &mdash;
        we&rsquo;re not liable for unauthorized access caused by your own
        security lapses.
      </p>
      <p>
        You may not share your account credentials with others. Each person who
        needs access should have their own account.
      </p>

      <h2>2. What CAZO Does</h2>
      <p>
        CAZO is an external attack surface management platform. It discovers and
        monitors assets on the public internet &mdash; subdomains, open ports,
        certificates, technologies, and vulnerabilities &mdash; from the outside,
        the way an attacker would.
      </p>
      <p>
        CAZO does not access your internal networks, servers, or private
        infrastructure. All scanning is performed from CAZO&rsquo;s
        infrastructure against publicly reachable endpoints.
      </p>

      <h2>3. Authorized Scanning &mdash; Your Responsibility</h2>
      <p>
        CAZO is a tool for scanning infrastructure you own or are explicitly
        authorized to test. You bear full legal responsibility for ensuring you
        have proper authorization before adding any target to your scope.
      </p>
      <p>
        See our{" "}
        <Link href="/legal/authorized-scanning" className="text-phosphor hover:underline">
          Authorized Scanning Policy
        </Link>{" "}
        for the full requirements. By using CAZO, you represent that you will
        only scan targets you have authorization to test.
      </p>

      <h2>4. Payment and Billing</h2>
      <p>
        CAZO is currently offered as a free service. We reserve the right to
        introduce paid plans in the future. If billing is introduced, these Terms
        will be updated accordingly.
      </p>

      <h2>5. Your Data</h2>
      <p>
        You own your scan results and account data. See our{" "}
        <Link href="/legal/privacy" className="text-phosphor hover:underline">
          Privacy Policy
        </Link>{" "}
        for how we collect, store, and protect your data.
      </p>

      <h2>6. Limitation of Liability</h2>
      <p>
        CAZO is provided &ldquo;as is&rdquo; without warranties of any kind. We
        are not liable for any damages arising from your use of the Platform,
        including but not limited to direct, indirect, incidental, consequential,
        or punitive damages.
      </p>
      <p>Specifically, we are not liable for:</p>
      <ul>
        <li>Decisions you make based on CAZO&rsquo;s findings</li>
        <li>
          Legal consequences of scanning targets without proper authorization
        </li>
        <li>Actions taken by third parties based on scan results you share</li>
      </ul>
      <p>
        Our total liability shall not exceed the amount you paid us in the 12
        months preceding the claim (or $0 if you&rsquo;re on the free tier).
      </p>

      <h2>7. Termination</h2>
      <p>
        You may terminate your account at any time from Settings. We may suspend
        or terminate your account if you violate these Terms, the{" "}
        <Link href="/legal/authorized-scanning" className="text-phosphor hover:underline">
          Authorized Scanning Policy
        </Link>
        , or the{" "}
        <Link href="/legal/acceptable-use" className="text-phosphor hover:underline">
          Acceptable Use Policy
        </Link>
        . Upon termination, your data will be handled per our{" "}
        <Link href="/legal/privacy" className="text-phosphor hover:underline">
          Privacy Policy
        </Link>
        .
      </p>

      <h2>8. Changes to These Terms</h2>
      <p>
        We may update these Terms. We&rsquo;ll notify you of material changes via
        email or in-app notification. Continued use after changes take effect
        constitutes acceptance.
      </p>

      <h2>9. Governing Law</h2>
      <p>
        These Terms are governed by applicable law in the jurisdiction where CAZO
        operates. Specific jurisdiction details will be added upon legal review.
      </p>

      <h2>10. Contact</h2>
      <p>
        Questions about these Terms:{" "}
        <a href="mailto:hello@cazo.io" className="text-phosphor hover:underline">
          hello@cazo.io
        </a>
      </p>
    </LegalLayout>
  );
}
