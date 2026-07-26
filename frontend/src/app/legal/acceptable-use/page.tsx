import { LegalLayout } from "@/components/legal/LegalLayout";

export const metadata = {
  title: "Acceptable Use Policy — CAZO EASM",
  description: "Rules for acceptable use of the CAZO platform.",
};

export default function AcceptableUsePage() {
  return (
    <LegalLayout lastUpdated="July 2026">
      <h1>Acceptable Use Policy</h1>

      <p>
        This policy defines acceptable use of CAZO EASM. Violations may result in
        account suspension or termination.
      </p>

      <h2>You May</h2>
      <ul>
        <li>Scan infrastructure you own or are explicitly authorized to test</li>
        <li>
          Use scan results for legitimate security assessment and remediation
        </li>
        <li>Share findings with your team and stakeholders</li>
        <li>Use the API within published rate limits</li>
        <li>Automate workflows using your own integrations</li>
      </ul>

      <h2>You May Not</h2>
      <ul>
        <li>
          <strong>Scan targets without authorization.</strong> You must have
          ownership or explicit written permission for every target in your
          scope.
        </li>
        <li>
          <strong>Use CAZO to facilitate attacks.</strong> CAZO is an assessment
          tool, not an attack platform. Do not use findings to exploit
          vulnerabilities without separate authorization.
        </li>
        <li>
          <strong>Resell or share access.</strong> Your account is for your use.
          Do not resell access to CAZO&rsquo;s scanning infrastructure or
          provide scan-as-a-service to unauthorized third parties.
        </li>
        <li>
          <strong>Abuse scanning infrastructure.</strong> Do not use CAZO to
          perform denial-of-service testing, port flooding, or any activity
          designed to disrupt target availability.
        </li>
        <li>
          <strong>Circumvent scope controls.</strong> Do not attempt to bypass
          scope authorization, rate limiting, or any other safety control in the
          Platform.
        </li>
        <li>
          <strong>Scrape or harvest data.</strong> Do not use CAZO to bulk-harvest
          data about infrastructure you don&rsquo;t own or control.
        </li>
        <li>
          <strong>Violate applicable laws.</strong> Your use must comply with all
          applicable laws and regulations in your jurisdiction.
        </li>
      </ul>

      <h2>Rate Limiting and Quotas</h2>
      <p>
        CAZO enforces scanning rate limits per organization. These limits protect
        both you and the targets you scan. If you need higher limits for
        legitimate purposes, contact us.
      </p>

      <h2>Enforcement</h2>
      <p>We investigate reports of abuse. Consequences include:</p>
      <ol>
        <li>Warning and scope suspension (first offense or unintentional)</li>
        <li>Account suspension (repeated or serious violations)</li>
        <li>Account termination (willful or egregious violations)</li>
        <li>Legal action where warranted</li>
      </ol>
      <p>
        We reserve the right to immediately suspend accounts engaged in scanning
        that generates legal complaints or threatens target availability.
      </p>

      <h2>Reporting Abuse</h2>
      <p>
        If you discover someone using CAZO to scan targets without
        authorization:{" "}
        <a href="mailto:hello@cazo.io" className="text-phosphor hover:underline">
          hello@cazo.io
        </a>
      </p>
    </LegalLayout>
  );
}
