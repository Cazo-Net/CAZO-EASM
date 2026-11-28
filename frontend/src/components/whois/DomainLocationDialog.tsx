"use client";

import { useEffect, useState } from "react";
import { Loader2, MapPin, Server, Building, AlertTriangle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getDomainLocation, type DomainLocation } from "@/lib/api";
import { countryFlag, countryName } from "@/lib/country";

const ERRORS: Record<string, string> = {
  unreachable: "Location service could not be reached",
  rate_limited: "Location service limit reached, try again later",
  bad_response: "Location service gave an unreadable answer",
};

export function DomainLocationDialog({
  domain,
  onOpenChange,
}: {
  domain: string | null;
  onOpenChange: (open: boolean) => void;
}) {
  const [data, setData] = useState<DomainLocation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!domain) return;
    let cancelled = false;
    setData(null);
    setError(null);
    getDomainLocation(domain)
      .then((d) => !cancelled && setData(d))
      .catch((e) => {
        if (cancelled) return;
        setError(e?.response?.status === 404 ? "This domain is not in your scans." : "Could not load the location.");
      });
    return () => {
      cancelled = true;
    };
  }, [domain]);

  return (
    <Dialog open={!!domain} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg" data-testid="domain-location-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MapPin className="h-4 w-4 text-primary" />
            {domain}
          </DialogTitle>
          <DialogDescription>Where this domain is registered and where its servers are.</DialogDescription>
        </DialogHeader>

        {!data && !error && (
          <div className="flex items-center justify-center py-10 text-sm text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Looking up location…
          </div>
        )}
        {error && <p className="py-6 text-sm text-destructive">{error}</p>}

        {data && (
          <div className="space-y-5">
            <section>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Registrant (WHOIS)
              </h4>
              {data.registrant_country ? (
                <p className="flex items-center gap-2 text-sm text-foreground">
                  <span className="text-lg leading-none">{countryFlag(data.registrant_country)}</span>
                  {countryName(data.registrant_country)}
                  <span className="text-xs text-muted-foreground">({data.registrant_country})</span>
                </p>
              ) : (
                <p className="text-sm text-muted-foreground">Not published. Most registrars hide it for privacy.</p>
              )}
            </section>

            <section>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Server location
              </h4>
              {data.locations.length === 0 ? (
                <p className="text-sm text-muted-foreground">The latest scan found no IP address for this domain.</p>
              ) : (
                <ul className="divide-y divide-border rounded-lg border border-border">
                  {data.locations.map((loc) => (
                    <li key={loc.ip} className="flex items-start gap-3 p-3" data-testid="domain-location-row">
                      <span className="mt-0.5 text-lg leading-none">{countryFlag(loc.country) || "🌐"}</span>
                      <div className="min-w-0 flex-1">
                        <p className="font-mono text-xs text-muted-foreground">{loc.ip}</p>
                        {loc.private ? (
                          <p className="text-sm text-muted-foreground">Private or reserved address, not looked up</p>
                        ) : loc.error ? (
                          <p className="flex items-center gap-1.5 text-sm text-warning">
                            <AlertTriangle className="h-3.5 w-3.5" />
                            {ERRORS[loc.error] || "Location unavailable"}
                          </p>
                        ) : (
                          <>
                            <p className="text-sm text-foreground">
                              {[loc.city, loc.region, countryName(loc.country)].filter(Boolean).join(", ") || "Unknown"}
                              {loc.anycast && <span className="ml-2 text-xs text-muted-foreground">(anycast, served from many places)</span>}
                            </p>
                            {(loc.provider || loc.asn) && (
                              <p className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
                                <Building className="h-3 w-3" />
                                {loc.provider}
                                {loc.asn && <span className="font-mono">{loc.asn}</span>}
                              </p>
                            )}
                          </>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-2 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <Server className="h-3 w-3" />
                IPs from the latest scan. Location by {data.provider}.
              </p>
            </section>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
