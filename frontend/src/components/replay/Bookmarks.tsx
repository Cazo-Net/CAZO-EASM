"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { useReplay } from "./ReplayProvider";
import { Bookmark, Plus, Trash2, Clock } from "lucide-react";

export function Bookmarks() {
  const { state, addBookmark, removeBookmark, setTimestamp } = useReplay();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [notes, setNotes] = useState("");

  const handleAdd = () => {
    if (!name.trim()) return;
    addBookmark(name.trim(), notes.trim());
    setName("");
    setNotes("");
    setShowForm(false);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          <Bookmark className="h-4 w-4 text-accent-2" />
          Bookmarks
        </h3>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1 text-xs text-brand hover:text-brand/80 transition-colors"
        >
          <Plus className="h-3 w-3" />
          Save Current
        </button>
      </div>

      <AnimatePresence>
        {showForm && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="space-y-2 rounded-lg border border-border/30 bg-card/10 p-3">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Bookmark name..."
                className="w-full rounded-lg border border-border/30 bg-background px-3 py-1.5 text-xs outline-none focus:border-brand/50"
              />
              <input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Notes (optional)..."
                className="w-full rounded-lg border border-border/30 bg-background px-3 py-1.5 text-xs outline-none focus:border-brand/50"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleAdd}
                  disabled={!name.trim()}
                  className="rounded-lg bg-brand px-3 py-1.5 text-xs font-medium text-white hover:bg-brand/90 disabled:opacity-30"
                >
                  Save
                </button>
                <button
                  onClick={() => setShowForm(false)}
                  className="rounded-lg px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground"
                >
                  Cancel
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="space-y-1">
        {state.bookmarks.length === 0 ? (
          <p className="text-xs text-muted-foreground py-4 text-center">
            No bookmarks yet. Save key moments in your replay timeline.
          </p>
        ) : (
          state.bookmarks.map((b) => (
            <div
              key={b.id}
              className="flex items-center gap-2 rounded-lg bg-card/10 px-3 py-2 group hover:bg-card/20 transition-colors cursor-pointer"
              onClick={() => setTimestamp(b.timestamp)}
            >
              <Clock className="h-3 w-3 text-accent-2 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium truncate">{b.name}</p>
                <p className="text-[10px] text-muted-foreground">
                  {new Date(b.timestamp).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                </p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  removeBookmark(b.id);
                }}
                className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
