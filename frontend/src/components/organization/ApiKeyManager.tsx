"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Key,
  Trash2,
  RotateCw,
  Copy,
  Eye,
  EyeOff,
  Plus,
  Check,
  Clock,
  AlertTriangle,
} from "lucide-react";
import type { ApiKeyV2 } from "@/types";

interface ApiKeyManagerProps {
  keys: ApiKeyV2[];
  newKey?: string;
  onCreate?: (name: string, scopes: string[]) => void;
  onRevoke?: (id: string) => void;
  onRotate?: (id: string) => void;
  className?: string;
}

export function ApiKeyManager({
  keys,
  newKey,
  onCreate,
  onRevoke,
  onRotate,
  className,
}: ApiKeyManagerProps) {
  const [showCreate, setShowCreate] = React.useState(false);
  const [name, setName] = React.useState("");
  const [copied, setCopied] = React.useState(false);
  const [showKey, setShowKey] = React.useState(false);

  const handleCreate = () => {
    if (name.trim() && onCreate) {
      onCreate(name.trim(), []);
      setName("");
      setShowCreate(false);
    }
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
        <CardTitle className="text-base font-semibold flex items-center gap-2">
          <Key className="w-4 h-4" />
          API Keys
        </CardTitle>
        {onCreate && (
          <Button size="sm" onClick={() => setShowCreate(!showCreate)}>
            <Plus className="w-4 h-4 mr-2" />
            New Key
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {showCreate && (
          <div className="flex gap-2">
            <Input
              placeholder="Key name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="flex-1"
            />
            <Button onClick={handleCreate} disabled={!name.trim()}>
              Create
            </Button>
            <Button variant="outline" onClick={() => setShowCreate(false)}>
              Cancel
            </Button>
          </div>
        )}

        {newKey && (
          <div className="p-3 rounded-lg bg-brand/5 border border-brand/20 space-y-2">
            <div className="flex items-center gap-2 text-sm text-brand font-medium">
              <Key className="w-4 h-4" />
              New API Key Created
            </div>
            <div className="flex items-center gap-2">
              <code className="flex-1 text-xs bg-background p-2 rounded font-mono break-all">
                {showKey ? newKey : "••••••••••••••••••••••••••••••••••••"}
              </code>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowKey(!showKey)}
              >
                {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleCopy(newKey)}
              >
                {copied ? <Check className="w-4 h-4 text-success" /> : <Copy className="w-4 h-4" />}
              </Button>
            </div>
            <p className="text-xs text-warning">
              <AlertTriangle className="w-3 h-3 inline mr-1" />
              Copy this key now. It won&apos;t be shown again.
            </p>
          </div>
        )}

        {keys.length === 0 ? (
          <div className="text-center py-8 space-y-3">
            <Key className="w-10 h-10 text-muted-foreground mx-auto" />
            <p className="text-sm text-muted-foreground">No API keys</p>
          </div>
        ) : (
          <div className="space-y-2">
            {keys.map((key) => (
              <div
                key={key.id}
                className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-muted">
                    <Key className="w-4 h-4 text-foreground" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">{key.name}</p>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="font-mono">{key.prefix}••••••••</span>
                      {key.expires_at && (
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          Expires {new Date(key.expires_at).toLocaleDateString()}
                        </span>
                      )}
                      {key.last_used_at && (
                        <span>
                          Last used {new Date(key.last_used_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {key.scopes?.length > 0 && (
                    <Badge variant="outline" className="text-xs">
                      {key.scopes.length} scope{key.scopes.length > 1 ? "s" : ""}
                    </Badge>
                  )}
                  {onRotate && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onRotate(key.id)}
                    >
                      <RotateCw className="w-4 h-4" />
                    </Button>
                  )}
                  {onRevoke && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onRevoke(key.id)}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
