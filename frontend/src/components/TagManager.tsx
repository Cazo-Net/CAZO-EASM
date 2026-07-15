"use client";

import { useEffect, useState } from "react";
import { Plus, X, Tag, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  createTag,
  listTags,
  deleteTag,
  addTagToAsset,
  removeTagFromAsset,
  getAssetTags,
} from "@/lib/api";
import type { Tag as TagType } from "@/types";

const PRESET_COLORS = [
  "#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6",
  "#EC4899", "#06B6D4", "#84CC16", "#F97316", "#6366F1",
];

interface TagManagerProps {
  assetType: string;
  assetId: string;
  onTagsChanged?: () => void;
}

export function TagManager({ assetType, assetId, onTagsChanged }: TagManagerProps) {
  const [allTags, setAllTags] = useState<TagType[]>([]);
  const [assetTags, setAssetTags] = useState<TagType[]>([]);
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newColor, setNewColor] = useState(PRESET_COLORS[0]);

  useEffect(() => {
    loadTags();
  }, [assetType, assetId]);

  const loadTags = async () => {
    setLoading(true);
    try {
      const [all, attached] = await Promise.all([listTags(), getAssetTags(assetType, assetId)]);
      setAllTags(all);
      setAssetTags(attached);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    try {
      const tag = await createTag({ name: newName.trim(), color: newColor });
      setAllTags((prev) => [...prev, tag]);
      setNewName("");
      setShowCreate(false);
      await loadTags();
    } catch {
      // silently fail
    }
  };

  const handleToggle = async (tag: TagType) => {
    const isAttached = assetTags.some((t) => t.id === tag.id);
    try {
      if (isAttached) {
        await removeTagFromAsset(assetType, assetId, tag.id);
        setAssetTags((prev) => prev.filter((t) => t.id !== tag.id));
      } else {
        await addTagToAsset(assetType, assetId, tag.id);
        setAssetTags((prev) => [...prev, tag]);
      }
      onTagsChanged?.();
    } catch {
      // silently fail
    }
  };

  const handleDelete = async (tagId: string) => {
    try {
      await deleteTag(tagId);
      setAllTags((prev) => prev.filter((t) => t.id !== tagId));
      setAssetTags((prev) => prev.filter((t) => t.id !== tagId));
    } catch {
      // silently fail
    }
  };

  const isAttached = (tagId: string) => assetTags.some((t) => t.id === tagId);

  return (
    <div className="space-y-2">
      {loading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-3 w-3 animate-spin" /> Loading tags...
        </div>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {allTags.map((tag) => (
            <button
              key={tag.id}
              onClick={() => handleToggle(tag)}
              className={cn(
                "group flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition-all",
                isAttached(tag.id)
                  ? "text-white"
                  : "text-muted-foreground bg-muted/50 hover:bg-muted"
              )}
              style={isAttached(tag.id) ? { backgroundColor: tag.color } : undefined}
            >
              <Tag className="h-3 w-3" />
              {tag.name}
              {isAttached(tag.id) && (
                <X className="h-3 w-3 opacity-70 group-hover:opacity-100" />
              )}
            </button>
          ))}
          {allTags.length === 0 && !showCreate && (
            <span className="text-xs text-muted-foreground">No tags yet</span>
          )}
        </div>
      )}

      {showCreate ? (
        <div className="flex items-center gap-2">
          <Input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Tag name"
            className="h-7 text-xs"
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            autoFocus
          />
          <div className="flex gap-1">
            {PRESET_COLORS.slice(0, 5).map((c) => (
              <button
                key={c}
                onClick={() => setNewColor(c)}
                className={cn(
                  "h-5 w-5 rounded-full border-2",
                  newColor === c ? "border-foreground" : "border-transparent"
                )}
                style={{ backgroundColor: c }}
              />
            ))}
          </div>
          <Button size="sm" className="h-7 text-xs" onClick={handleCreate}>
            Add
          </Button>
          <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setShowCreate(false)}>
            <X className="h-3 w-3" />
          </Button>
        </div>
      ) : (
        <Button
          variant="ghost"
          size="sm"
          className="h-6 text-xs gap-1 text-muted-foreground"
          onClick={() => setShowCreate(true)}
        >
          <Plus className="h-3 w-3" /> Add tag
        </Button>
      )}
    </div>
  );
}
