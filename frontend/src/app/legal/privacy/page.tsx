import { LegalLayout } from "@/components/legal/LegalLayout";

export const metadata = {
  title: "Privacy Policy — CAZO EASM",
  description: "How CAZO collects, stores, protects, and shares your data.",
};

export default function PrivacyPage() {
  return (
    <LegalLayout lastUpdated="July 2026">
      <h1>Privacy Policy</h1>

      <p>
        This Privacy Policy describes how CAZO EASM (&ldquo;we&rdquo;) collects,
        uses, stores, and shares information when you use our Platform.
      </p>

      <h2>Information We Collect</h2>

      <h3>Account Data</h3>
      <ul>
        <li>
          Email address, name, and authentication credentials (hashed passwords,
          optional MFA configuration)
        </li>
        <li>Organization name and membership</li>
        <li>API keys (hashed, not stored in plaintext)</li>
      </ul>

      <h3>Scan Data</h3>
      <ul>
        <li>
          Domains, IPs, and infrastructure you add to your authorized scopes
        </li>
        <li>
          Results of scans you initiate: subdomains, ports, certificates, DNS
          records, technologies, vulnerabilities, WHOIS data
        </li>
        <li>Scan metadata: timestamps, duration, status, configuration</li>
      </ul>

      <h3>Usage Data</h3>
      <ul>
        <li>Pages visited, features used, actions taken within the Platform</li>
        <li>
          Browser type and approximate location (country-level) from access logs
        </li>
        <li>Error logs and performance data</li>
      </ul>

      <h3>What We Do NOT Collect</h3>
      <ul>
        <li>Your internal network topology or private infrastructure</li>
        <li>Data from targets outside your authorized scopes</li>
        <li>
          Payment information (currently &mdash; may change if billing is added)
        </li>
      </ul>

      <h2>How We Use Your Information</h2>
      <ul>
        <li>
          <strong>Provide the service:</strong> Running scans, storing results,
          displaying dashboards
        </li>
        <li>
          <strong>Security:</strong> Detecting abuse, unauthorized access, and
          policy violations
        </li>
        <li>
          <strong>Improvement:</strong> Understanding which features are used to
          prioritize development
        </li>
        <li>
          <strong>Communication:</strong> Service announcements, security alerts
          (you can opt out of non-essential communications)
        </li>
      </ul>
      <p>
        We do not sell your data. We do not use your scan results for
        advertising. We do not train models on your data.
      </p>

      <h2>Data Retention</h2>
      <ul>
        <li>
          <strong>Account data:</strong> Retained while your account is active.
          Deleted within 30 days of account deletion (except where legally
          required to retain longer).
        </li>
        <li>
          <strong>Scan data:</strong> Retained for the life of your account. You
          may delete individual scans at any time. Upon account deletion, scan
          data is purged within 30 days.
        </li>
        <li>
          <strong>Audit logs:</strong> Retained for 1 year for security and
          compliance purposes, then automatically purged.
        </li>
        <li>
          <strong>Usage data:</strong> Anonymized after 90 days; retained in
          anonymized form indefinitely for product improvement.
        </li>
      </ul>
      <p>
        We do not currently offer automated data retention policies (e.g.,
        auto-delete scan results after N days). At our current scale, manual
        deletion via the UI or account deletion is sufficient. We may add
        retention controls in the future.
      </p>

      <h2>Data Storage and Security</h2>
      <ul>
        <li>
          All data is stored in encrypted databases on infrastructure we control
        </li>
        <li>Data is encrypted at rest and in transit (TLS)</li>
        <li>
          Access to your data is scoped per-organization &mdash; your data is
          isolated from other organizations&rsquo; data at the application layer
        </li>
        <li>
          We follow industry-standard security practices but cannot guarantee
          absolute security (no one can)
        </li>
      </ul>

      <h2>Third-Party Data Sources</h2>
      <p>CAZO queries public data sources to enrich scan results:</p>
      <table>
        <thead>
          <tr>
            <th>Source</th>
            <th>What we send</th>
            <th>What we receive</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>crt.sh</td>
            <td>Domain name</td>
            <td>Certificate transparency logs</td>
          </tr>
          <tr>
            <td>NVD (NIST)</td>
            <td>CVE identifiers</td>
            <td>Vulnerability details</td>
          </tr>
          <tr>
            <td>RDAP/WHOIS</td>
            <td>Domain name</td>
            <td>Registration data</td>
          </tr>
          <tr>
            <td>DNS resolvers</td>
            <td>Domain names</td>
            <td>DNS records</td>
          </tr>
        </tbody>
      </table>
      <p>
        We send only the domain or identifier being queried. No user data,
        account information, or scan metadata is shared with these sources.
      </p>

      <h2>Data Sharing</h2>
      <p>We share your data only:</p>
      <ul>
        <li>With your organization members (scoped by your org settings)</li>
        <li>When required by law or legal process</li>
        <li>
          To protect the rights, safety, or property of CAZO, our users, or the
          public
        </li>
        <li>
          With service providers who assist in operating the Platform (hosting,
          infrastructure), bound by data processing agreements
        </li>
      </ul>

      <h2>Your Rights</h2>
      <p>
        Depending on your jurisdiction, you may have the right to:
      </p>
      <ul>
        <li>Access your personal data</li>
        <li>Correct inaccurate data</li>
        <li>Delete your data</li>
        <li>Export your data (portability)</li>
        <li>Object to processing</li>
      </ul>
      <p>
        To exercise these rights:{" "}
        <a href="mailto:hello@cazo.io" className="text-phosphor hover:underline">
          hello@cazo.io
        </a>{" "}
        or through the Platform&rsquo;s settings.
      </p>

      <h2>Cookies and Tracking</h2>
      <p>
        CAZO uses essential cookies for authentication and session management. We
        do not use advertising cookies or third-party tracking scripts.
      </p>

      <h2>Children&rsquo;s Privacy</h2>
      <p>
        CAZO is not intended for users under 18. We do not knowingly collect data
        from children.
      </p>

      <h2>Changes to This Policy</h2>
      <p>
        We may update this policy. Material changes will be communicated via
        email and in-app notification.
      </p>

      <h2>Contact</h2>
      <p>
        Privacy questions or requests:{" "}
        <a href="mailto:hello@cazo.io" className="text-phosphor hover:underline">
          hello@cazo.io
        </a>
      </p>
    </LegalLayout>
  );
}
