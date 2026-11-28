"use client";

import { CazoMark } from "@/components/CazoMark";
import { useState } from "react";
import { useRouter } from "next/navigation";
import api, { getErrorMessage } from "@/lib/api";
import { Loader2, Eye, EyeOff } from "lucide-react";


export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await api.post("/auth/login", { email, password });
      localStorage.setItem("admin_token", res.data.access_token);
      router.push("/");
    } catch (e: any) {
      setError(getErrorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <CazoMark className="h-14 w-14 mx-auto mb-4" />
          <h1 className="text-2xl font-semibold tracking-tight">CAZO <span className="text-zinc-500 font-medium">EASM</span> Admin</h1>
          <p className="text-sm text-zinc-500 mt-1">Staff sign-in. Access is logged.</p>
        </div>

        <form onSubmit={handleLogin} className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium mb-1.5">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="you@cazoeasm.io" autoComplete="username"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1.5">Password</label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 pr-10"
                placeholder="Enter password" autoComplete="current-password"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Sign in
          </button>
        </form>
      </div>
    </div>
  );
}
