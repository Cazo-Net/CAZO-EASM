"use client";

import { useState, useRef, useEffect } from "react";
import { MessageSquare, X, Send, Loader2 } from "lucide-react";
import { CazoMark } from "@/components/marketing/CazoLogo";
import { useSupportStore } from "@/lib/supportStore";
import { cn } from "@/lib/utils";

export function SupportChat() {
  const { isOpen, messages, unreadCount, loading, sending, toggle, close, sendMessage } =
    useSupportStore();
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  const handleSend = () => {
    if (!input.trim() || sending) return;
    sendMessage(input);
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      {/* Chat Panel */}
      {isOpen && (
        <div className="fixed bottom-20 right-5 z-50 w-[360px] h-[480px] bg-card border border-border/60 rounded-xl shadow-2xl flex flex-col overflow-hidden animate-in slide-in-from-bottom-4 fade-in duration-200">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border/50 bg-card/95 backdrop-blur shrink-0">
            <div className="flex items-center gap-2.5">
              <div className="relative">
                <CazoMark className="h-6 w-6" />
              </div>
              <div>
                <p className="text-sm font-semibold">Support</p>
                <p className="text-[10px] text-muted-foreground">We typically reply within minutes</p>
              </div>
            </div>
            <button
              onClick={close}
              className="p-1 rounded-md hover:bg-muted/50 text-muted-foreground hover:text-foreground transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {messages.length === 0 && !loading && (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <CazoMark className="h-10 w-10 mb-3 opacity-30" />
                <p className="text-sm text-muted-foreground">How can we help you?</p>
                <p className="text-xs text-muted-foreground/60 mt-1">
                  Send a message and our team will assist you.
                </p>
              </div>
            )}
            {loading && (
              <div className="flex justify-center py-4">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            )}
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={cn(
                  "flex",
                  msg.sender_type === "user" ? "justify-end" : "justify-start"
                )}
              >
                <div
                  className={cn(
                    "max-w-[80%] rounded-lg px-3 py-2 text-xs leading-relaxed",
                    msg.sender_type === "user"
                      ? "bg-phosphor/15 text-foreground border border-phosphor/20"
                      : "bg-muted/50 text-foreground border border-border/50"
                  )}
                >
                  {msg.sender_name && (
                    <p className="text-[10px] font-medium text-muted-foreground mb-1">{msg.sender_name}</p>
                  )}
                  {msg.message}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="px-3 py-2.5 border-t border-border/50 bg-card/95 backdrop-blur shrink-0">
            <div className="flex items-center gap-2">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type a message..."
                className="flex-1 bg-muted/30 border border-border/50 rounded-lg px-3 py-2 text-xs placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-phosphor/30 focus:border-phosphor/30"
                disabled={sending}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || sending}
                className={cn(
                  "p-2 rounded-lg transition-colors",
                  input.trim() && !sending
                    ? "bg-phosphor text-void hover:bg-phosphor/90"
                    : "bg-muted/30 text-muted-foreground cursor-not-allowed"
                )}
              >
                {sending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Send className="h-3.5 w-3.5" />
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Floating Button */}
      <button
        onClick={toggle}
        className={cn(
          "fixed bottom-5 right-5 z-50 flex items-center justify-center w-14 h-14 rounded-2xl transition-all duration-200 shadow-lg hover:shadow-xl hover:scale-105",
          isOpen
            ? "bg-muted/80 border border-border/60"
            : "bg-card border border-border/60 hover:border-phosphor/30"
        )}
        aria-label={isOpen ? "Close support chat" : "Open support chat"}
      >
        {isOpen ? (
          <X className="h-5 w-5 text-foreground" />
        ) : (
          <div className="relative">
            <CazoMark className="h-7 w-7" />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 flex h-3.5 w-3.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-green-500 border-2 border-card" />
              </span>
            )}
            {/* Green online dot */}
            {unreadCount === 0 && (
              <span className="absolute -top-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-green-500 border-2 border-card" />
            )}
          </div>
        )}
      </button>
    </>
  );
}
