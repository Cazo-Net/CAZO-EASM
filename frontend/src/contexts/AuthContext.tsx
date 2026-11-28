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
import api, {
  login as apiLogin,
  register as apiRegister,
  logout as apiLogout,
  getToken,
  loginWithGoogle as apiLoginWithGoogle,
  loginWithSso as apiLoginWithSso,
  verifyTwoFactorLogin as apiVerifyTwoFactorLogin,
} from "@/lib/api";

// Kept between the password step and the 2FA step (also survives the Google
// callback redirect). Holds only the short-lived mfa_token, never session tokens.
const MFA_PENDING_KEY = "_mfa_pending";

export interface SignInResult {
  requires2fa: boolean;
}

export function hasPendingTwoFactor(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return !!sessionStorage.getItem(MFA_PENDING_KEY);
  } catch {
    return false;
  }
}
import type { User } from "@/types";

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (email: string, password: string, rememberMe?: boolean) => Promise<SignInResult>;
  verifyTwoFactor: (code: string) => Promise<void>;
  cancelTwoFactor: () => void;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  loginWithGoogle: (credential: string) => Promise<SignInResult>;
  loginWithSso: (code: string) => Promise<SignInResult>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  updateOnboardingState: (patch: Record<string, any>) => Promise<void>;
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
        if (error.response?.status === 401 && !originalRequest._retry && !originalRequest.url?.includes("/auth/refresh") && !originalRequest.url?.includes("/auth/me")) {
          const refreshToken = localStorage.getItem("refresh_token") || sessionStorage.getItem("refresh_token");
          if (refreshToken) {
            originalRequest._retry = true;
            try {
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
          } else {
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

  const login = async (email: string, password: string, rememberMe = true): Promise<SignInResult> => {
    const data = await apiLogin(email, password, rememberMe);
    if (data.requires_2fa && data.mfa_token) {
      sessionStorage.setItem(MFA_PENDING_KEY, JSON.stringify({ mfaToken: data.mfa_token, rememberMe }));
      return { requires2fa: true };
    }
    setToken(data.access_token);
    await fetchUser();
    return { requires2fa: false };
  };

  const verifyTwoFactor = async (code: string) => {
    const raw = sessionStorage.getItem(MFA_PENDING_KEY);
    if (!raw) throw new Error("Your sign-in expired. Please enter your password again.");
    const { mfaToken, rememberMe } = JSON.parse(raw);
    const data = await apiVerifyTwoFactorLogin(mfaToken, code, rememberMe);
    sessionStorage.removeItem(MFA_PENDING_KEY);
    setToken(data.access_token);
    await fetchUser();
  };

  const cancelTwoFactor = () => {
    try {
      sessionStorage.removeItem(MFA_PENDING_KEY);
    } catch {}
  };

  const register = async (email: string, password: string, fullName?: string) => {
    await apiRegister(email, password, fullName);
    await login(email, password);
  };

  const loginWithGoogle = async (credential: string): Promise<SignInResult> => {
    const data = await apiLoginWithGoogle(credential);
    if (data.requires_2fa && data.mfa_token) {
      sessionStorage.setItem(MFA_PENDING_KEY, JSON.stringify({ mfaToken: data.mfa_token, rememberMe: true }));
      return { requires2fa: true };
    }
    setToken(data.access_token);
    await fetchUser();
    return { requires2fa: false };
  };

  const loginWithSso = async (code: string): Promise<SignInResult> => {
    const data = await apiLoginWithSso(code);
    if (data.requires_2fa && data.mfa_token) {
      sessionStorage.setItem(MFA_PENDING_KEY, JSON.stringify({ mfaToken: data.mfa_token, rememberMe: true }));
      return { requires2fa: true };
    }
    setToken(data.access_token);
    await fetchUser();
    return { requires2fa: false };
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

  const updateOnboardingState = async (patch: Record<string, any>) => {
    try {
      const currentPrefs = (user?.preferences as any) || {};
      const currentOnboarding = currentPrefs.onboarding || {};
      const updatedPrefs = {
        ...currentPrefs,
        onboarding: { ...currentOnboarding, ...patch },
      };
      await api.put("/users/me/preferences", updatedPrefs);
      setUser((prev) =>
        prev ? { ...prev, preferences: updatedPrefs as any } : prev
      );
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
        verifyTwoFactor,
        cancelTwoFactor,
        register,
        loginWithGoogle,
        loginWithSso,
        logout,
        refreshUser,
        updateOnboardingState,
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
