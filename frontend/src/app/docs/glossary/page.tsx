import { DocsLayout } from "@/components/docs/DocsLayout";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Glossary — CAZO Docs",
  description: "Plain-language definitions of the technical terms used throughout CAZO.",
};

const TERMS: { term: string; definition: string }[] = [
  {
    term: "ASN (Autonomous System Number)",
    definition:
      "A unique identifier for a network operator on the internet. ISPs, cloud providers, and large organizations each have one or more ASNs. CAZO uses shared ASNs to correlate assets that are likely operated by the same entity.",
  },
  {
    term: "Attack surface",
    definition:
      "The sum of all points where an unauthorized user can try to enter or extract data from your environment. In CAZO's context, this means everything on the public internet that's associated with your organization — subdomains, open ports, certificates, running services.",
  },
  {
    term: "CIDR (Classless Inter-Domain Routing)",
    definition:
      "A way to represent a range of IP addresses. For example, 192.168.0.0/24 represents all IP addresses from 192.168.0.0 to 192.168.0.255. CAZO lets you add CIDR ranges as authorized scopes when you control a block of IPs.",
  },
  {
    term: "CVE (Common Vulnerabilities and Exposures)",
    definition:
      "A standardized identifier for a known security vulnerability. CVEs are assigned by MITRE and detailed in NVD (National Vulnerability Database). CAZO matches detected software versions against CVE databases to find potential vulnerabilities.",
  },
  {
    term: "CVSS (Common Vulnerability Scoring System)",
    definition:
      "A numerical score (0–10) rating the severity of a CVE. Higher scores indicate more severe vulnerabilities. CAZO uses CVSS scores to prioritize findings, but the score alone doesn't tell you whether the vulnerability is actually exploitable on your specific host.",
  },
  {
    term: "CNAME (Canonical Name)",
    definition:
      "A DNS record that aliases one domain to another. For example, www.example.com might be a CNAME pointing to example.com. CNAMEs reveal relationships between domains.",
  },
  {
    term: "DNS (Domain Name System)",
    definition:
      "The system that translates human-readable domain names (example.com) into IP addresses (52.14.89.103) that computers use to connect. CAZO performs DNS lookups as a core part of asset discovery.",
  },
  {
    term: "EASM (External Attack Surface Management)",
    definition:
      "Discovering and monitoring everything about your organization that's visible on the public internet. Unlike internal security tools, EASM works from the outside — the same vantage point an attacker would have.",
  },
  {
    term: "Fingerprint",
    definition:
      "Identifying what software, version, or technology a running service is using. For example, detecting that a web server is running nginx 1.24.0. CAZO fingerprints technologies from HTTP headers, service banners, and other observable signals.",
  },
  {
    term: "False positive",
    definition:
      "A finding that appears to be a real issue but isn't actually a problem. For example, flagging a CVE against software that has already been patched, or reporting an open port that's actually a CDN endpoint. CAZO labels findings honestly to help you distinguish real issues from noise.",
  },
  {
    term: "SAN (Subject Alternative Name)",
    definition:
      "Additional domain names covered by a TLS certificate. A single certificate might cover example.com, www.example.com, and api.example.com. CAZO uses SAN data to discover related infrastructure.",
  },
  {
    term: "Scope (Authorized Scope)",
    definition:
      "A declaration of what you're authorized to scan. CAZO enforces scopes server-side — no scan runs against a target that isn't registered as an authorized scope for your organization.",
  },
  {
    term: "Shadow asset",
    definition:
      "An internet-facing resource that's probably yours but isn't in your confirmed inventory. Discovered through shared infrastructure signals (IP, certificate, ASN). Often the riskiest assets because nobody's monitoring them.",
  },
  {
    term: "SSRF (Server-Side Request Forgery)",
    definition:
      "An attack where someone uses your server to make requests to internal or private resources. CAZO blocks scans against private IPs to prevent being used as an SSRF vector.",
  },
  {
    term: "Subdomain",
    definition:
      "A domain nested under a parent domain. api.example.com is a subdomain of example.com. Organizations often have dozens or hundreds of subdomains, many of which may be forgotten or unmonitored.",
  },
  {
    term: "TLS certificate",
    definition:
      "A digital certificate that encrypts traffic between a client and server (the padlock in your browser). Certificates contain domain names, expiration dates, and issuer information. CAZO monitors certificate status and uses certificate data to discover related infrastructure.",
  },
  {
    term: "TTL (Time to Live)",
    definition:
      "How long a DNS record should be cached before re-checking with the authoritative DNS server. Lower TTLs mean changes propagate faster but generate more DNS queries.",
  },
  {
    term: "Verified vs. Unverified (CVE)",
    definition:
      "A verified finding means CAZO directly observed evidence of the vulnerability. An unverified finding means the software version matches a CVE in NVD, but CAZO hasn't confirmed it's actually exploitable on your host. See the full article for details.",
  },
  {
    term: "Wildcard",
    definition:
      "A scope entry like *.example.com that authorizes scanning of all subdomains under example.com. Useful when you control a large number of subdomains and don't want to register each one individually.",
  },
];

export default function GlossaryDocPage() {
  return (
    <DocsLayout>
      <article className="max-w-2xl">
        <h1 className="font-display text-3xl font-semibold text-foreground">
          Glossary
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          Plain-language definitions of the technical terms used throughout
          CAZO.
        </p>

        <div className="mt-8 divide-y divide-border/40">
          {TERMS.map((t) => (
            <div key={t.term} className="py-4 first:pt-0 last:pb-0">
              <h3 className="text-sm font-semibold text-foreground">
                {t.term}
              </h3>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                {t.definition}
              </p>
            </div>
          ))}
        </div>
      </article>
    </DocsLayout>
  );
}
