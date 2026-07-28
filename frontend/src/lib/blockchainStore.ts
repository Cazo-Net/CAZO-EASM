"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface WalletResult {
  wallet: any;
  attribution: any;
  risk: any;
}

interface TxListResult {
  items: any[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

interface BlockchainState {
  address: string;
  chain: string;
  walletData: WalletResult | null;
  walletLoading: boolean;
  walletError: string;
  txPage: number;
  txData: TxListResult | null;
  txLoading: boolean;
  searchQuery: string;
  searchResults: any[];
}

export const CHAIN_META: Record<string, { label: string; token: string; color: string; explorer: string }> = {
  ethereum: { label: "Ethereum", token: "ETH", color: "bg-blue-500", explorer: "etherscan.io" },
  bitcoin: { label: "Bitcoin", token: "BTC", color: "bg-orange-500", explorer: "blockstream.info" },
  solana: { label: "Solana", token: "SOL", color: "bg-purple-500", explorer: "solscan.io" },
  polygon: { label: "Polygon", token: "MATIC", color: "bg-violet-500", explorer: "polygonscan.com" },
  bsc: { label: "BNB Chain", token: "BNB", color: "bg-yellow-500", explorer: "bscscan.com" },
  arbitrum: { label: "Arbitrum", token: "ETH", color: "bg-cyan-500", explorer: "arbiscan.com" },
  optimism: { label: "Optimism", token: "ETH", color: "bg-red-500", explorer: "optimistic.etherscan.io" },
  base: { label: "Base", token: "ETH", color: "bg-blue-400", explorer: "basescan.org" },
  avalanche: { label: "Avalanche", token: "AVAX", color: "bg-red-400", explorer: "snowtrace.io" },
  tron: { label: "Tron", token: "TRX", color: "bg-red-600", explorer: "tronscan.org" },
};

const _listeners: Set<() => void> = new Set();
let _state: BlockchainState = {
  address: "",
  chain: "ethereum",
  walletData: null,
  walletLoading: false,
  walletError: "",
  txPage: 1,
  txData: null,
  txLoading: false,
  searchQuery: "",
  searchResults: [],
};

function _emit() {
  _listeners.forEach((l) => l());
}

export function useBlockchainStore() {
  const [, forceUpdate] = useState(0);

  useEffect(() => {
    const listener = () => forceUpdate((c) => c + 1);
    _listeners.add(listener);
    return () => {
      _listeners.delete(listener);
    };
  }, []);

  const lookupWallet = useCallback(async (address: string, chain: string) => {
    const trimmed = address.trim();
    if (!trimmed) return;

    _state = {
      ..._state,
      address: trimmed,
      chain,
      walletLoading: true,
      walletError: "",
      walletData: null,
      txData: null,
    };
    _emit();

    try {
      const res = await fetch(
        `${API_BASE}/api/v1/blockchain/wallet/${encodeURIComponent(trimmed)}?chain=${chain}`
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Request failed" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data: WalletResult = await res.json();
      _state = { ..._state, walletData: data, walletLoading: false };
    } catch (e: any) {
      _state = {
        ..._state,
        walletLoading: false,
        walletError: e?.message || "Failed to lookup wallet",
      };
    } finally {
      _emit();
    }
  }, []);

  const loadTransactions = useCallback(
    async (page: number = 1) => {
      if (!_state.address) return;

      _state = { ..._state, txLoading: true, txPage: page };
      _emit();

      try {
        const res = await fetch(
          `${API_BASE}/api/v1/blockchain/wallet/${encodeURIComponent(_state.address)}/transactions?chain=${_state.chain}&page=${page}&page_size=20`
        );
        if (!res.ok) throw new Error("Failed to load transactions");
        const data: TxListResult = await res.json();
        _state = { ..._state, txData: data, txLoading: false };
      } catch {
        _state = { ..._state, txLoading: false };
      } finally {
        _emit();
      }
    },
    []
  );

  const search = useCallback(async (query: string) => {
    _state = { ..._state, searchQuery: query, searchResults: [] };
    _emit();

    if (!query.trim()) return;

    try {
      const res = await fetch(
        `${API_BASE}/api/v1/blockchain/search?q=${encodeURIComponent(query)}`
      );
      if (!res.ok) throw new Error("Search failed");
      const data = await res.json();
      _state = { ..._state, searchResults: data.results || [] };
    } catch {
      // Silent
    } finally {
      _emit();
    }
  }, []);

  const setChain = useCallback((chain: string) => {
    _state = { ..._state, chain };
    _emit();
  }, []);

  const reset = useCallback(() => {
    _state = {
      address: "",
      chain: _state.chain,
      walletData: null,
      walletLoading: false,
      walletError: "",
      txPage: 1,
      txData: null,
      txLoading: false,
      searchQuery: "",
      searchResults: [],
    };
    _emit();
  }, []);

  return {
    ..._state,
    lookupWallet,
    loadTransactions,
    search,
    setChain,
    reset,
  };
}
