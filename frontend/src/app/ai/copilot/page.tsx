"use client";

import { useEffect, useState, useRef } from "react";
import { useSearchParams } from "next/navigation";
import {
  Sparkles,
  Send,
  Loader2,
  Bot,
  User,
  Trash2,
  MessageSquare,
  Plus,
  ChevronDown,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { aiChat, listAIConversations, getAIConversation, deleteAIConversation } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import type { AIConversation, AIMessage } from "@/types";

function parseAIContent(content: string): { summary: string; details: any } {
  try {
    const parsed = JSON.parse(content);
    return { summary: parsed.summary || content, details: parsed };
  } catch {
    return { summary: content, details: null };
  }
}

function AICopilotContent() {
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("q") || "";

  const [conversations, setConversations] = useState<AIConversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<AIMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showSidebar, setShowSidebar] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    loadConversations();
  }, []);

  useEffect(() => {
    if (initialQuery && !loading) {
      handleSend(initialQuery);
    }
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadConversations = async () => {
    try {
      const convs = await listAIConversations();
      setConversations(convs);
    } catch {
      // silently fail
    }
  };

  const loadConversation = async (id: string) => {
    try {
      const conv = await getAIConversation(id);
      setActiveConvId(id);
      setMessages(conv.messages);
      setShowSidebar(false);
    } catch {
      // silently fail
    }
  };

  const handleNewConversation = () => {
    setActiveConvId(null);
    setMessages([]);
    setInput("");
  };

  const handleDeleteConversation = async (id: string) => {
    try {
      await deleteAIConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeConvId === id) {
        setActiveConvId(null);
        setMessages([]);
      }
    } catch {
      // silently fail
    }
  };

  const handleSend = async (overrideInput?: string) => {
    const msg = overrideInput || input;
    if (!msg.trim() || loading) return;

    const userMsg: AIMessage = {
      id: `temp-${Date.now()}`,
      role: "user",
      content: msg,
      model_used: null,
      response_time_ms: null,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const result = await aiChat(msg, activeConvId || undefined);
      const assistantMsg: AIMessage = {
        id: result.message.id,
        role: "assistant",
        content: result.message.content,
        model_used: result.message.model_used,
        response_time_ms: result.message.response_time_ms,
        created_at: result.message.created_at,
      };
      setMessages((prev) => [...prev.filter((m) => !m.id.startsWith("temp-")), userMsg, assistantMsg]);
      setActiveConvId(result.conversation_id);
      loadConversations();
    } catch {
      const errorMsg: AIMessage = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: "I encountered an error processing your request. Please try again.",
        model_used: "error",
        response_time_ms: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev.filter((m) => !m.id.startsWith("temp-")), userMsg, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const suggestedPrompts = [
    "Summarize my platform",
    "What changed today?",
    "Show certificates expiring this month",
    "Which assets require attention?",
    "Generate an executive summary",
  ];

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <div className={cn(
        "w-64 border-r border-border/50 bg-card/50 flex flex-col shrink-0 transition-all duration-300",
        showSidebar ? "translate-x-0" : "-translate-x-full md:translate-x-0 md:w-64",
        "fixed md:relative z-30 h-full"
      )}>
        <div className="p-3 border-b border-border/30">
          <button
            onClick={handleNewConversation}
            className="flex items-center gap-2 w-full rounded-lg bg-primary/10 px-3 py-2.5 text-sm font-medium text-primary hover:bg-primary/20 transition-colors"
          >
            <Plus className="h-4 w-4" />
            New Conversation
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {conversations.map((conv) => (
            <div
              key={conv.id}
              className={cn(
                "group flex items-center gap-2 rounded-lg px-3 py-2 text-sm cursor-pointer transition-colors",
                activeConvId === conv.id
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-muted/30"
              )}
              onClick={() => loadConversation(conv.id)}
            >
              <MessageSquare className="h-3.5 w-3.5 shrink-0" />
              <span className="flex-1 truncate">{conv.title}</span>
              <button
                onClick={(e) => { e.stopPropagation(); handleDeleteConversation(conv.id); }}
                className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Main Chat */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center gap-3 border-b border-border/50 bg-card/30 backdrop-blur-xl px-4 py-3">
          <button
            onClick={() => setShowSidebar(!showSidebar)}
            className="md:hidden p-1.5 rounded-lg hover:bg-muted/30"
          >
            <MessageSquare className="h-4 w-4" />
          </button>
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-cyan-400">
              <Sparkles className="h-4 w-4 text-white" />
            </div>
            <div>
              <h1 className="text-sm font-semibold">AI Copilot</h1>
              <p className="text-[10px] text-muted-foreground">Ask anything about your attack surface</p>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="relative mb-6">
                <div className="absolute inset-0 rounded-full bg-primary/20 blur-2xl" />
                <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl border border-border/50 bg-card/80">
                  <Sparkles className="h-8 w-8 text-primary" />
                </div>
              </div>
              <h2 className="text-xl font-bold mb-2">AI Copilot</h2>
              <p className="text-sm text-muted-foreground max-w-md mb-8">
                Ask questions about your assets, certificates, vulnerabilities, and more.
                The AI uses your platform data to provide accurate insights.
              </p>
              <div className="grid gap-2 max-w-lg w-full">
                {suggestedPrompts.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => handleSend(prompt)}
                    className="flex items-center gap-2 rounded-lg border border-border/30 px-4 py-3 text-sm text-left text-muted-foreground hover:bg-muted/30 hover:text-foreground transition-colors"
                  >
                    <Sparkles className="h-3.5 w-3.5 text-primary/50 shrink-0" />
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-6">
              {messages.map((msg) => (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={cn(
                    "flex gap-3",
                    msg.role === "assistant" ? "justify-start" : "justify-end"
                  )}
                >
                  {msg.role === "assistant" && (
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-cyan-400">
                      <Bot className="h-4 w-4 text-white" />
                    </div>
                  )}
                  <div className={cn(
                    "max-w-[80%] rounded-xl px-4 py-3",
                    msg.role === "assistant"
                      ? "bg-muted/30 border border-border/30"
                      : "bg-primary text-primary-foreground"
                  )}>
                    <div className="text-sm whitespace-pre-wrap">
                      {(() => {
                        const { summary, details } = parseAIContent(msg.content);
                        if (details) {
                          return (
                            <div className="space-y-3">
                              <p>{summary}</p>
                              {details.key_observations && (
                                <div>
                                  <p className="font-medium text-xs uppercase tracking-wider text-muted-foreground mb-1">Key Observations</p>
                                  <ul className="list-disc list-inside space-y-0.5 text-xs text-muted-foreground">
                                    {details.key_observations.map((obs: string, i: number) => <li key={i}>{obs}</li>)}
                                  </ul>
                                </div>
                              )}
                              {details.recommendations && (
                                <div>
                                  <p className="font-medium text-xs uppercase tracking-wider text-muted-foreground mb-1">Recommendations</p>
                                  <ul className="list-disc list-inside space-y-0.5 text-xs text-muted-foreground">
                                    {(Array.isArray(details.recommendations) ? details.recommendations : []).map((rec: any, i: number) => (
                                      <li key={i}>{typeof rec === "string" ? rec : rec.title || JSON.stringify(rec)}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                            </div>
                          );
                        }
                        return summary;
                      })()}
                    </div>
                    {msg.model_used && msg.model_used !== "error" && (
                      <p className="text-[10px] text-muted-foreground/50 mt-2">
                        {msg.model_used}{msg.response_time_ms ? ` · ${msg.response_time_ms}ms` : ""}
                      </p>
                    )}
                  </div>
                  {msg.role === "user" && (
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted">
                      <User className="h-4 w-4 text-muted-foreground" />
                    </div>
                  )}
                </motion.div>
              ))}
              {loading && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex gap-3"
                >
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-cyan-400">
                    <Bot className="h-4 w-4 text-white" />
                  </div>
                  <div className="rounded-xl bg-muted/30 border border-border/30 px-4 py-3">
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  </div>
                </motion.div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="border-t border-border/50 bg-card/30 backdrop-blur-xl px-4 py-4">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-end gap-2 rounded-xl border border-border/50 bg-card/60 p-2">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about your assets, certificates, vulnerabilities..."
                className="flex-1 resize-none bg-transparent px-3 py-2 text-sm outline-none min-h-[40px] max-h-[120px]"
                rows={1}
                disabled={loading}
              />
              <button
                onClick={() => handleSend()}
                disabled={!input.trim() || loading}
                className={cn(
                  "flex h-9 w-9 items-center justify-center rounded-lg transition-colors",
                  input.trim() && !loading
                    ? "bg-primary text-primary-foreground hover:bg-primary/90"
                    : "bg-muted text-muted-foreground"
                )}
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
            <p className="text-[10px] text-muted-foreground/50 text-center mt-2">
              AI responses are based on your platform data. Always verify critical findings.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AICopilotPage() {
  return (
    <ProtectedRoute>
      <AICopilotContent />
    </ProtectedRoute>
  );
}
