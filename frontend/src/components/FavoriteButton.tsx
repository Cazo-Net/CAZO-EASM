"use client";

import { useState, useEffect } from "react";
import { Star } from "lucide-react";
import { cn } from "@/lib/utils";
import { addFavorite, removeFavorite, listFavorites } from "@/lib/api";

interface FavoriteButtonProps {
  assetType: string;
  assetId: string;
  size?: "sm" | "md";
}

export function FavoriteButton({ assetType, assetId, size = "sm" }: FavoriteButtonProps) {
  const [isFavorited, setIsFavorited] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    checkFavorite();
  }, [assetType, assetId]);

  const checkFavorite = async () => {
    try {
      const favorites = await listFavorites(assetType);
      setIsFavorited(favorites.some((f: any) => f.asset_id === assetId));
    } catch {
      // silently fail
    }
  };

  const toggle = async () => {
    setLoading(true);
    try {
      if (isFavorited) {
        await removeFavorite(assetType, assetId);
        setIsFavorited(false);
      } else {
        await addFavorite(assetType, assetId);
        setIsFavorited(true);
      }
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        toggle();
      }}
      disabled={loading}
      className={cn(
        "transition-all hover:scale-110",
        isFavorited ? "text-amber-400" : "text-muted-foreground/30 hover:text-muted-foreground",
        size === "sm" ? "h-4 w-4" : "h-5 w-5"
      )}
    >
      <Star className={cn("h-full w-full", isFavorited && "fill-current")} />
    </button>
  );
}
