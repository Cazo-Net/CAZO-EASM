"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, MessageSquare, Send, X } from "lucide-react";
import { CazoMark } from "@/components/marketing/CazoLogo";
import { MAX_MESSAGE_LENGTH, useSupportStore } from "@/lib/supportStore";
import { cn } from "@/lib/utils";

function formatTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const time = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  if (d.toDateString() === new Date().toDateString()) return time;
  return `${d.toLocaleDateString([], { month: "short", day: "numeric" })}, ${time}`;
}

const fieldClass =
  "w-full bg-muted/30 border border-border rounded-lg px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/40 focus:border-primary/40";

export function SupportChat() {
  const { mode, isOpen, conversationId, status, messages, unreadCount, loading, sending, error, toggle, close, sendMessage } =
    useSupportStore();
  const [input, setInput] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [website, setWebsite] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // A visitor gives their email once, with the first message.
  const needsDetails = mode === "guest" && !conversationId;
  const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const canSend = !!input.trim() && !sending && (!needsDetails || emailOk);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, isOpen]);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, close]);

  // Grow the box with the text, up to a few lines.
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 112)}px`;
  }, [input, isOpen]);

  const handleSend = async () => {
    if (!canSend) return;
    const ok = await sendMessage(input, needsDetails ? { name: name.trim(), email: email.trim(), website } : undefined);
    if (ok) setInput("");
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      {isOpen && (
        <div
          role="dialog"
          aria-label="CAZO support chat"
          data-testid="support-chat-panel"
          className="fixed z-50 bottom-20 right-3 left-3 sm:left-auto sm:right-5 sm:w-[380px] h-[min(540px,calc(100dvh-7rem))] bg-card border border-border rounded-xl shadow-2xl flex flex-col overflow-hidden animate-in slide-in-from-bottom-4 fade-in duration-200"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
            <div className="flex items-center gap-2.5 min-w-0">
              <CazoMark className="h-7 w-7 shrink-0" />
              <div className="min-w-0">
                <p className="text-sm font-semibold leading-tight">CAZO Support</p>
                <p className="text-xs text-muted-foreground leading-tight mt-0.5">
                  A real person reads every message.
                </p>
              </div>
            </div>
            <button
              onClick={close}
              aria-label="Close support chat"
              className="p-1.5 rounded-md hover:bg-muted/50 text-muted-foreground hover:text-foreground transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3" aria-live="polite">
            {loading && messages.length === 0 ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center px-4">
                <MessageSquare className="h-8 w-8 mb-3 text-muted-foreground/50" />
                <p className="text-sm font-medium">How can we help?</p>
                <p className="text-xs text-muted-foreground mt-1.5 leading-relaxed">
                  {needsDetails
                    ? "Ask about plans, scanning or anything else. Leave your email and we'll reply here and by email."
                    : "Tell us what you need. We'll reply here, and email you if you've already left."}
                </p>
              </div>
            ) : (
              <>
                {messages.map((msg) => {
                  const mine = msg.sender_type === "user";
                  return (
                    <div key={msg.id} className={cn("flex flex-col", mine ? "items-end" : "items-start")}>
                      <div
                        className={cn(
                          "max-w-[85%] rounded-xl px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap break-words",
                          mine
                            ? "bg-primary/15 border border-primary/25 rounded-br-sm"
                            : "bg-muted/50 border border-border rounded-bl-sm"
                        )}
                      >
                        {msg.message}
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-1 px-1">
                        {mine ? "You" : msg.sender_name || "CAZO Support"}
                        {formatTime(msg.created_at) && ` · ${formatTime(msg.created_at)}`}
                      </p>
                    </div>
                  );
                })}
                {messages[messages.length - 1]?.sender_type === "user" && (
                  <p className="text-center text-[11px] text-muted-foreground pt-1">
                    Sent. We&apos;ll reply here{mode === "guest" ? " and by email" : ""} as soon as we can.
                  </p>
                )}
                {status === "closed" && (
                  <p className="text-center text-[11px] text-muted-foreground pt-1">
                    This conversation was closed. Send a message to reopen it.
                  </p>
                )}
              </>
            )}
            <div ref={endRef} />
          </div>

          {/* Composer */}
          <div className="px-3 py-2.5 border-t border-border shrink-0 space-y-2">
            {error && (
              <p role="alert" className="text-xs text-destructive px-1">
                {error}
              </p>
            )}
            {needsDetails && (
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Name (optional)"
                  aria-label="Your name"
                  autoComplete="name"
                  maxLength={120}
                  className={fieldClass}
                />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Email"
                  aria-label="Your email address"
                  autoComplete="email"
                  required
                  maxLength={255}
                  className={fieldClass}
                />
                {/* Honeypot: hidden from people, tempting for bots. */}
                <input
                  type="text"
                  name="website"
                  value={website}
                  onChange={(e) => setWebsite(e.target.value)}
                  tabIndex={-1}
                  autoComplete="off"
                  aria-hidden="true"
                  className="hidden"
                />
              </div>
            )}
            <div className="flex items-end gap-2">
              <textarea
                ref={inputRef}
                rows={1}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type a message..."
                aria-label="Message"
                maxLength={MAX_MESSAGE_LENGTH}
                className={cn(fieldClass, "resize-none min-h-[38px]")}
              />
              <button
                onClick={handleSend}
                disabled={!canSend}
                aria-label="Send message"
                className={cn(
                  "h-[38px] w-[38px] shrink-0 flex items-center justify-center rounded-lg transition-colors",
                  canSend
                    ? "bg-primary text-primary-foreground hover:bg-primary/90"
                    : "bg-muted/30 text-muted-foreground cursor-not-allowed"
                )}
              >
                {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Launcher */}
      <button
        onClick={toggle}
        data-testid="support-chat-launcher"
        className={cn(
          "fixed bottom-5 right-5 z-50 flex items-center justify-center w-14 h-14 rounded-full transition-all duration-200 shadow-lg hover:shadow-xl hover:scale-105",
          isOpen
            ? "bg-card border border-border text-foreground"
            : "bg-card border-2 border-primary/70 shadow-primary/20 hover:border-primary"
        )}
        aria-label={
          isOpen ? "Close support chat" : unreadCount > 0 ? `Open support chat, ${unreadCount} new` : "Open support chat"
        }
        aria-expanded={isOpen}
      >
        {isOpen ? <X className="h-5 w-5" /> : <CazoMark className="h-9 w-9" />}
        {!isOpen && unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[20px] h-5 px-1 flex items-center justify-center rounded-full bg-foreground text-background text-[11px] font-semibold border-2 border-background">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>
    </>
  );
}
