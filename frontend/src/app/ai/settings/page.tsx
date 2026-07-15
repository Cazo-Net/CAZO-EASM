"use client";

import { useEffect, useState } from "react";
import {
  Settings,
  Loader2,
  Save,
  Check,
  BarChart3,
  MessageSquare,
  FileText,
  Clock,
  DollarSign,
} from "lucide-react";
import { motion } from "framer-motion";
import { getAISettings, updateAISettings, getAIUsage } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import type { AISettings as AISettingsType, AIUsage } from "@/types";

function AISettingsContent() {
  const [settings, setSettings] = useState<AISettingsType | null>(null);
  const [usage, setUsage] = useState<AIUsage | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [s, u] = await Promise.all([getAISettings(), getAIUsage()]);
      setSettings(s);
      setUsage(u);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    try {
      await updateAISettings({
        provider: settings.provider,
        model: settings.model,
        temperature: settings.temperature,
        max_tokens: settings.max_tokens,
        language: settings.language,
        tone: settings.tone,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      // silently fail
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <div className="border-b border-border/50 bg-card/30 backdrop-blur-xl sticky top-0 z-10">
        <div className="mx-auto max-w-3xl px-6 py-5">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
                <Settings className="h-6 w-6 text-primary" />
                AI Settings
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Configure AI model, tone, and preferences.
              </p>
            </div>
            <button
              onClick={handleSave}
              disabled={saving}
              className={cn(
                "flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-medium transition-colors",
                saved
                  ? "bg-emerald-500/10 text-emerald-400"
                  : "bg-primary text-primary-foreground hover:bg-primary/90"
              )}
            >
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : saved ? <Check className="h-3.5 w-3.5" /> : <Save className="h-3.5 w-3.5" />}
              {saved ? "Saved" : "Save"}
            </button>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-3xl px-6 py-8 space-y-6">
        {/* Model Settings */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-border/50 bg-card/60 overflow-hidden"
        >
          <div className="border-b border-border/30 px-6 py-4">
            <h2 className="text-sm font-semibold">Model Configuration</h2>
          </div>
          <div className="p-6 space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <label className="text-xs font-medium">Provider</label>
                <select
                  value={settings?.provider || "openai"}
                  onChange={(e) => setSettings(s => s ? { ...s, provider: e.target.value } : s)}
                  className="w-full rounded-lg border border-border/50 bg-muted/30 px-3 py-2 text-sm"
                >
                  <option value="openai">OpenAI</option>
                  <option value="ollama">Ollama (Local)</option>
                  <option value="stub">Stub (Demo)</option>
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-xs font-medium">Model</label>
                <select
                  value={settings?.model || "gpt-4o-mini"}
                  onChange={(e) => setSettings(s => s ? { ...s, model: e.target.value } : s)}
                  className="w-full rounded-lg border border-border/50 bg-muted/30 px-3 py-2 text-sm"
                >
                  <option value="gpt-4o-mini">GPT-4o Mini</option>
                  <option value="gpt-4o">GPT-4o</option>
                  <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                  <option value="llama3">Llama 3</option>
                  <option value="mistral">Mistral</option>
                </select>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium">Temperature: {settings?.temperature || 0.7}</label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={settings?.temperature || 0.7}
                onChange={(e) => setSettings(s => s ? { ...s, temperature: parseFloat(e.target.value) } : s)}
                className="w-full accent-primary"
              />
              <div className="flex justify-between text-[10px] text-muted-foreground">
                <span>Precise</span>
                <span>Balanced</span>
                <span>Creative</span>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium">Max Tokens: {settings?.max_tokens || 2048}</label>
              <input
                type="range"
                min="256"
                max="8192"
                step="256"
                value={settings?.max_tokens || 2048}
                onChange={(e) => setSettings(s => s ? { ...s, max_tokens: parseInt(e.target.value) } : s)}
                className="w-full accent-primary"
              />
            </div>
          </div>
        </motion.div>

        {/* Response Settings */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="rounded-xl border border-border/50 bg-card/60 overflow-hidden"
        >
          <div className="border-b border-border/30 px-6 py-4">
            <h2 className="text-sm font-semibold">Response Settings</h2>
          </div>
          <div className="p-6 space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <label className="text-xs font-medium">Tone</label>
                <select
                  value={settings?.tone || "balanced"}
                  onChange={(e) => setSettings(s => s ? { ...s, tone: e.target.value } : s)}
                  className="w-full rounded-lg border border-border/50 bg-muted/30 px-3 py-2 text-sm"
                >
                  <option value="executive">Executive</option>
                  <option value="technical">Technical</option>
                  <option value="balanced">Balanced</option>
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-xs font-medium">Language</label>
                <select
                  value={settings?.language || "en"}
                  onChange={(e) => setSettings(s => s ? { ...s, language: e.target.value } : s)}
                  className="w-full rounded-lg border border-border/50 bg-muted/30 px-3 py-2 text-sm"
                >
                  <option value="en">English</option>
                  <option value="es">Spanish</option>
                  <option value="fr">French</option>
                  <option value="de">German</option>
                  <option value="ja">Japanese</option>
                  <option value="zh">Chinese</option>
                </select>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Usage Analytics */}
        {usage && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="rounded-xl border border-border/50 bg-card/60 overflow-hidden"
          >
            <div className="border-b border-border/30 px-6 py-4">
              <h2 className="text-sm font-semibold flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-cyan-400" />
                Usage Analytics
              </h2>
            </div>
            <div className="p-6">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  { label: "Questions Asked", value: usage.total_questions, icon: MessageSquare, color: "text-primary" },
                  { label: "Reports Generated", value: usage.total_reports, icon: FileText, color: "text-cyan-400" },
                  { label: "Avg Response Time", value: `${usage.avg_response_time_ms}ms`, icon: Clock, color: "text-amber-400" },
                  { label: "Estimated Cost", value: `$${usage.estimated_cost.toFixed(4)}`, icon: DollarSign, color: "text-emerald-400" },
                ].map((stat) => (
                  <div key={stat.label} className="rounded-lg border border-border/30 p-4">
                    <stat.icon className={cn("h-4 w-4 mb-2", stat.color)} />
                    <p className="text-lg font-bold">{stat.value}</p>
                    <p className="text-[10px] text-muted-foreground mt-0.5">{stat.label}</p>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}

export default function AISettingsPage() {
  return (
    <ProtectedRoute>
      <AISettingsContent />
    </ProtectedRoute>
  );
}
