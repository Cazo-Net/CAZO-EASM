"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE = "";

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
  tokens: any[];
  tokensLoading: boolean;
  intel: any;
  intelLoading: boolean;
  sanctions: any;
  sanctionsLoading: boolean;
  contractDetail: any;
  searchQuery: string;
  searchResults: any[];
}

export const CHAIN_META: Record<string, { label: string; token: string; color: string; explorer: string }> = {
  ethereum: { label: "Ethereum", token: "ETH", color: "bg-blue-500", explorer: "etherscan.io" },
  bitcoin: { label: "Bitcoin", token: "BTC", color: "bg-orange-500", explorer: "blockstream.info" },
  solana: { label: "Solana", token: "SOL", color: "bg-purple-500", explorer: "solscan.io" },
  polygon: { label: "Polygon", token: "MATIC", color: "bg-violet-500", explorer: "polygonscan.com" },
  bnb: { label: "BNB Chain", token: "BNB", color: "bg-yellow-500", explorer: "bscscan.com" },
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
  tokens: [],
  tokensLoading: false,
  intel: null,
  intelLoading: false,
  sanctions: null,
  sanctionsLoading: false,
  contractDetail: null,
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
      tokens: [],
      intel: null,
      sanctions: null,
      contractDetail: null,
    };
    _emit();

    try {
      const base = `${API_BASE}/api/v1/blockchain`;
      const addr = encodeURIComponent(trimmed);
      const params = `chain=${chain}`;

      const [walletRes, txRes, tokensRes, intelRes, sanctionsRes, contractRes] = await Promise.allSettled([
        fetch(`${base}/wallet/${addr}?${params}`),
        fetch(`${base}/wallet/${addr}/transactions?${params}&page=1&page_size=10`),
        fetch(`${base}/wallet/${addr}/tokens?${params}`),
        fetch(`${base}/wallet/${addr}/intel?${params}`),
        fetch(`${base}/wallet/${addr}/sanctions?${params}`),
        fetch(`${base}/contract/${addr}?${params}`),
      ]);

      if (walletRes.status === "fulfilled" && walletRes.value.ok) {
        const data: WalletResult = await walletRes.value.json();
        _state = { ..._state, walletData: data };
      } else if (walletRes.status === "fulfilled") {
        const err = await walletRes.value.json().catch(() => ({ detail: "Request failed" }));
        throw new Error(err.detail || `HTTP ${walletRes.value.status}`);
      } else {
        throw walletRes.reason;
      }

      if (txRes.status === "fulfilled" && txRes.value.ok) {
        const txData: TxListResult = await txRes.value.json();
        _state = { ..._state, txData };
      }

      if (tokensRes.status === "fulfilled" && tokensRes.value.ok) {
        const tokData = await tokensRes.value.json();
        _state = { ..._state, tokens: Array.isArray(tokData) ? tokData : tokData.tokens || [] };
      }

      if (intelRes.status === "fulfilled" && intelRes.value.ok) {
        _state = { ..._state, intel: await intelRes.value.json() };
      }

      if (sanctionsRes.status === "fulfilled" && sanctionsRes.value.ok) {
        _state = { ..._state, sanctions: await sanctionsRes.value.json() };
      }

      if (contractRes.status === "fulfilled" && contractRes.value.ok) {
        _state = { ..._state, contractDetail: await contractRes.value.json() };
      }

      _state = { ..._state, walletLoading: false };
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
      tokens: [],
      tokensLoading: false,
      intel: null,
      intelLoading: false,
      sanctions: null,
      sanctionsLoading: false,
      contractDetail: null,
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
