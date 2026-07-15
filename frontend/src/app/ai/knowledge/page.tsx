"use client";

import { useEffect, useState } from "react";
import {
  BookOpen,
  Search,
  Lock,
  Globe,
  Cpu,
  Shield,
  BarChart3,
  FileText,
  Loader2,
  ArrowRight,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { listAIKnowledge } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import type { AIKnowledge } from "@/types";

const categories = [
  { id: "certificates", label: "Certificates", icon: Lock, color: "text-emerald-400" },
  { id: "dns", label: "DNS", icon: Globe, color: "text-cyan-400" },
  { id: "technologies", label: "Technologies", icon: Cpu, color: "text-violet-400" },
  { id: "security", label: "Security", icon: Shield, color: "text-red-400" },
  { id: "platform", label: "Platform", icon: BarChart3, color: "text-primary" },
  { id: "reports", label: "Reports", icon: FileText, color: "text-amber-400" },
];

const defaultArticles: AIKnowledge[] = [
  {
    id: "1", title: "SSL Certificates", category: "certificates",
    content: "SSL certificates secure HTTPS connections between browsers and servers. AttackSec tracks certificate issuer, validity dates, grade (A+ to F), protocol, and cipher suite.\n\nWhy it matters: Expired or weak certificates expose users to man-in-the-middle attacks. Regular monitoring prevents security gaps.\n\nWhere it appears: Assets page (SSL tab), Scan detail page.\n\nRelated: Technology detection, DNS records.",
    related_pages: ["/assets", "/scan/[id]"], tags: ["ssl", "tls", "certificate", "https"],
  },
  {
    id: "2", title: "DNS Records", category: "dns",
    content: "DNS records map domain names to IP addresses and services. AttackSec discovers A, AAAA, CNAME, MX, NS, TXT, and SRV records.\n\nWhy it matters: DNS misconfigurations can redirect traffic, expose internal infrastructure, or indicate compromise.\n\nWhere it appears: DNS Records page, Scan detail page.\n\nRelated: Subdomains, WHOIS data.",
    related_pages: ["/dns", "/scan/[id]"], tags: ["dns", "domain", "nameserver", "mx"],
  },
  {
    id: "3", title: "Technology Detection", category: "technologies",
    content: "Technology detection identifies web frameworks, CMS, servers, programming languages, JavaScript libraries, and other software running on discovered assets.\n\nWhy it matters: Outdated or vulnerable technologies are common attack vectors. Knowing your tech stack helps prioritize patching.\n\nWhere it appears: Assets page (Technologies tab), Scan detail page.\n\nRelated: Vulnerabilities, SSL certificates.",
    related_pages: ["/assets", "/scan/[id]"], tags: ["technology", "framework", "cms", "server"],
  },
  {
    id: "4", title: "Exposure Score", category: "security",
    content: "The exposure score (0-100) is a composite risk rating based on vulnerability severity, SSL status, open ports, and technology age.\n\nWhy it matters: Provides a single number to track your security posture over time and compare across projects.\n\nWhere it appears: Dashboard, Scan detail page.\n\nRelated: Vulnerabilities, Risk factors.",
    related_pages: ["/dashboard", "/scan/[id]"], tags: ["risk", "score", "exposure", "security"],
  },
  {
    id: "5", title: "Vulnerability Severity", category: "security",
    content: "Vulnerabilities are classified by severity: Critical (immediate action), High (urgent), Medium (planned), Low (informational).\n\nWhy it matters: Severity helps prioritize remediation efforts. Critical and high-severity findings should be addressed first.\n\nWhere it appears: Vulnerabilities page, Scan detail page.\n\nRelated: Exposure score, Reports.",
    related_pages: ["/vulnerabilities", "/scan/[id]"], tags: ["vulnerability", "severity", "critical", "high"],
  },
  {
    id: "6", title: "Asset Relationships", category: "platform",
    content: "Assets in AttackSec are connected: Domains contain subdomains, subdomains have ports, DNS records, SSL certificates, and technologies.\n\nWhy it matters: Understanding relationships helps assess blast radius — if one asset is compromised, what else is at risk?\n\nWhere it appears: Attack Graph, Asset detail views.\n\nRelated: Attack graph, Subdomains.",
    related_pages: ["/graph", "/assets"], tags: ["relationship", "graph", "asset", "dependency"],
  },
  {
    id: "7", title: "Reports", category: "reports",
    content: "Reports summarize scan findings in shareable formats. Types include Executive, Technical, Weekly, Monthly, and Project-specific reports.\n\nWhy it matters: Reports communicate security posture to stakeholders who may not access the platform directly.\n\nWhere it appears: Reports page.\n\nRelated: Dashboard, Recommendations.",
    related_pages: ["/reports"], tags: ["report", "export", "pdf", "executive"],
  },
  {
    id: "8", title: "Platform Terminology", category: "platform",
    content: "Key terms used in AttackSec:\n\n• Subdomain: A domain that is part of a larger domain (e.g., api.example.com)\n• Port: Network port where services are running\n• Certificate: Digital certificate for HTTPS encryption\n• WHOIS: Domain ownership and registration data\n• Risk Score: Composite security rating (0-100)\n• Exposure: The sum of all security risks across your attack surface",
    related_pages: ["/dashboard"], tags: ["terminology", "glossary", "definition"],
  },
];

function KnowledgeContent() {
  const [articles, setArticles] = useState<AIKnowledge[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    loadArticles();
  }, [selectedCategory]);

  const loadArticles = async () => {
    setLoading(true);
    try {
      const data = await listAIKnowledge(selectedCategory || undefined);
      setArticles(data.length > 0 ? data : defaultArticles);
    } catch {
      setArticles(defaultArticles);
    } finally {
      setLoading(false);
    }
  };

  const filteredArticles = articles.filter((a) => {
    if (selectedCategory && a.category !== selectedCategory) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return a.title.toLowerCase().includes(q) || a.content.toLowerCase().includes(q) || a.tags.some((t) => t.includes(q));
    }
    return true;
  });

  return (
    <div className="min-h-screen">
      <div className="border-b border-border/50 bg-card/30 backdrop-blur-xl sticky top-0 z-10">
        <div className="mx-auto max-w-5xl px-6 py-5">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
                <BookOpen className="h-6 w-6 text-primary" />
                Knowledge Center
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Understand certificates, DNS, technologies, and platform concepts.
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-5xl px-6 py-8">
        {/* Search */}
        <div className="relative mb-6">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search articles..."
            className="w-full rounded-xl border border-border/50 bg-card/60 pl-10 pr-4 py-3 text-sm outline-none focus:border-primary/50 transition-colors"
          />
        </div>

        {/* Category Filters */}
        <div className="flex flex-wrap gap-2 mb-6">
          <button
            onClick={() => setSelectedCategory("")}
            className={cn(
              "rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
              !selectedCategory ? "bg-primary text-primary-foreground" : "bg-muted/50 text-muted-foreground hover:bg-muted"
            )}
          >
            All
          </button>
          {categories.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(selectedCategory === cat.id ? "" : cat.id)}
              className={cn(
                "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
                selectedCategory === cat.id ? "bg-primary text-primary-foreground" : "bg-muted/50 text-muted-foreground hover:bg-muted"
              )}
            >
              <cat.icon className={cn("h-3 w-3", selectedCategory === cat.id ? "text-primary-foreground" : cat.color)} />
              {cat.label}
            </button>
          ))}
        </div>

        {/* Articles */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-3">
            {filteredArticles.map((article) => (
              <motion.div
                key={article.id}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-xl border border-border/50 bg-card/60 overflow-hidden"
              >
                <button
                  onClick={() => setExpandedId(expandedId === article.id ? null : article.id)}
                  className="flex items-center gap-3 w-full px-5 py-4 text-left hover:bg-muted/20 transition-colors"
                >
                  {expandedId === article.id ? (
                    <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
                  )}
                  <span className="font-medium text-sm">{article.title}</span>
                  <span className="rounded-full bg-muted/50 px-2 py-0.5 text-[10px] text-muted-foreground ml-auto">
                    {article.category}
                  </span>
                </button>
                <AnimatePresence>
                  {expandedId === article.id && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="px-5 pb-5 pt-0 space-y-3">
                        <div className="whitespace-pre-wrap text-sm text-muted-foreground leading-relaxed">
                          {article.content}
                        </div>
                        {article.tags && article.tags.length > 0 && (
                          <div className="flex flex-wrap gap-1.5">
                            {article.tags.map((tag) => (
                              <span key={tag} className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function AIKnowledgePage() {
  return (
    <ProtectedRoute>
      <KnowledgeContent />
    </ProtectedRoute>
  );
}
