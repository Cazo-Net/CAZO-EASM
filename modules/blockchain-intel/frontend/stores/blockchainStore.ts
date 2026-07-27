/**
 * Blockchain Intelligence — page-level state store.
 * Survives React unmount when navigating away and back.
 */

export interface WalletData {
  wallet: any;
  attribution: any;
  risk: any;
}

export interface TxData {
  hash: string;
  chain: string;
  status: string;
  block_number: number | null;
  timestamp: string | null;
  from_address: string;
  to_address: string;
  value: string;
  fee: string | null;
  decoded_method: string | null;
}

interface BlockchainState {
  // Wallet lookup
  address: string;
  chain: string;
  walletData: WalletData | null;
  walletLoading: boolean;
  walletError: string | null;

  // Transactions
  txPage: number;
  txData: any | null;
  txLoading: boolean;

  // Search
  searchQuery: string;
  searchResults: any[];

  // Actions
  setAddress: (address: string) => void;
  setChain: (chain: string) => void;
  lookupWallet: () => Promise<void>;
  loadTransactions: (page?: number) => Promise<void>;
  search: (query: string) => Promise<void>;
  reset: () => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let _state: BlockchainState | null = null;
let _listeners: Set<() => void> = new Set();

function _notify() {
  _listeners.forEach((l) => l());
}

function _getInitialState(): BlockchainState {
  return {
    address: "",
    chain: "ethereum",
    walletData: null,
    walletLoading: false,
    walletError: null,
    txPage: 1,
    txData: null,
    txLoading: false,
    searchQuery: "",
    searchResults: [],
    setAddress: (address) => {
      if (_state) {
        _state.address = address;
        _notify();
      }
    },
    setChain: (chain) => {
      if (_state) {
        _state.chain = chain;
        _notify();
      }
    },
    lookupWallet: async () => {
      if (!_state || !_state.address) return;
      _state.walletLoading = true;
      _state.walletError = null;
      _notify();

      try {
        const params = new URLSearchParams({
          address: _state.address,
          chain: _state.chain,
        });
        const res = await fetch(`${API_BASE}/api/v1/blockchain/wallet/${_state.address}?chain=${_state.chain}`);
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: "Request failed" }));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const data = await res.json();
        if (_state) {
          _state.walletData = data;
          _state.walletLoading = false;
          _state.walletError = null;
          _notify();
        }
      } catch (e: any) {
        if (_state) {
          _state.walletLoading = false;
          _state.walletError = e.message || "Failed to lookup wallet";
          _notify();
        }
      }
    },
    loadTransactions: async (page = 1) => {
      if (!_state || !_state.address) return;
      _state.txLoading = true;
      _state.txPage = page;
      _notify();

      try {
        const res = await fetch(
          `${API_BASE}/api/v1/blockchain/wallet/${_state.address}/transactions?chain=${_state.chain}&page=${page}&page_size=20`
        );
        if (!res.ok) throw new Error("Failed to load transactions");
        const data = await res.json();
        if (_state) {
          _state.txData = data;
          _state.txLoading = false;
          _notify();
        }
      } catch (e: any) {
        if (_state) {
          _state.txLoading = false;
          _notify();
        }
      }
    },
    search: async (query) => {
      if (!_state) return;
      _state.searchQuery = query;
      _state.searchResults = [];
      _notify();

      try {
        const res = await fetch(`${API_BASE}/api/v1/blockchain/search?q=${encodeURIComponent(query)}`);
        if (!res.ok) throw new Error("Search failed");
        const data = await res.json();
        if (_state) {
          _state.searchResults = data.results || [];
          _notify();
        }
      } catch {
        // Silent fail for search
      }
    },
    reset: () => {
      if (_state) {
        _state.address = "";
        _state.walletData = null;
        _state.walletError = null;
        _state.txData = null;
        _state.searchResults = [];
        _notify();
      }
    },
  };
}

export function useBlockchainStore(): BlockchainState {
  // Lazy init (only on client)
  if (typeof window === "undefined") {
    return _getInitialState();
  }

  if (!_state) {
    _state = _getInitialState();
  }

  // Subscribe to changes (React will re-render when _notify is called)
  const [, setTick] = __import__("react").useState(0);
  __import("react").useEffect(() => {
    const listener = () => setTick((t) => t + 1);
    _listeners.add(listener);
    return () => {
      _listeners.delete(listener);
    };
  }, []);

  return _state;
}
