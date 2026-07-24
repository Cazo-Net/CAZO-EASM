"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import api, { login as apiLogin, register as apiRegister, logout as apiLogout, getToken, loginWithGoogle as apiLoginWithGoogle } from "@/lib/api";
import type { User } from "@/types";

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  loginWithGoogle: (credential: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  isAuthenticated: boolean;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const fetchUser = useCallback(async () => {
    const storedToken = getToken();
    if (!storedToken) {
      setUser(null);
      setToken(null);
      setLoading(false);
      return;
    }
    try {
      const response = await api.get("/auth/me");
      setUser(response.data);
      setToken(storedToken);
    } catch {
      apiLogout();
      setToken(null);
      setUser(null);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  useEffect(() => {
    const interceptor = api.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;
        if (
          error.response?.status === 401 &&
          !originalRequest._retry &&
          !originalRequest.url?.includes("/auth/refresh") &&
          !originalRequest.url?.includes("/auth/me") &&
          (localStorage.getItem("refresh_token") || sessionStorage.getItem("refresh_token"))
        ) {
          originalRequest._retry = true;
          try {
            const refreshToken = localStorage.getItem("refresh_token") || sessionStorage.getItem("refresh_token");
            const { data } = await api.post("/auth/refresh", { refresh_token: refreshToken });
            const storage = localStorage.getItem("access_token") ? localStorage : sessionStorage;
            storage.setItem("access_token", data.access_token);
            if (data.refresh_token) {
              storage.setItem("refresh_token", data.refresh_token);
            }
            setToken(data.access_token);
            originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
            return api(originalRequest);
          } catch {
            apiLogout();
            setToken(null);
            setUser(null);
            router.push("/login");
          }
        }
        return Promise.reject(error);
      }
    );
    return () => {
      api.interceptors.response.eject(interceptor);
    };
  }, [router]);

  const login = async (email: string, password: string, rememberMe = true) => {
    const data = await apiLogin(email, password, rememberMe);
    setToken(data.access_token);
    const storage = rememberMe ? localStorage : sessionStorage;
    storage.setItem("access_token", data.access_token);
    storage.setItem("refresh_token", data.refresh_token);
    await fetchUser();
  };

  const register = async (email: string, password: string, fullName?: string) => {
    await apiRegister(email, password, fullName);
    await login(email, password);
  };

  const loginWithGoogle = async (credential: string) => {
    const data = await apiLoginWithGoogle(credential);
    setToken(data.access_token);
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    await fetchUser();
  };

  const logout = () => {
    apiLogout();
    setToken(null);
    setUser(null);
    router.push("/");
  };

  const refreshUser = async () => {
    const storedToken = getToken();
    if (!storedToken) return;
    try {
      const response = await api.get("/auth/me");
      setUser(response.data);
    } catch {
      // silently fail
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        login,
        register,
        loginWithGoogle,
        logout,
        refreshUser,
        isAuthenticated: !!user,
        loading,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
