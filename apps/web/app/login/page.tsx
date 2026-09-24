"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, useApi } from "@/lib/api";

const SEEDED = ["paul@savanna.vc", "amani@savanna.vc", "grace@savanna.vc", "tom@savanna.vc", "lena@harbor.capital"];

export default function LoginPage() {
  const router = useRouter();
  const { data: cfg } = useApi<{ devLogin: boolean; sso: boolean }>("/auth/config");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function devLogin(address: string) {
    setError(null);
    try {
      await api("/auth/dev-login", { method: "POST", json: { email: address } });
      router.push("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm rounded-2xl border border-line bg-white p-8 shadow-sm">
        <h1 className="text-xl font-semibold">
          first<span className="text-brand">look</span>
        </h1>
        <p className="mt-1 text-sm text-muted">Sign in to your firm&apos;s workspace.</p>

        {cfg?.sso && (
          <a href="/api/auth/workos/start" className="mt-6 block rounded-lg bg-brand px-3 py-2 text-center text-sm font-medium text-white">
            Continue with SSO
          </a>
        )}

        {cfg?.devLogin && (
          <>
            <form
              className="mt-6 space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                void devLogin(email);
              }}
            >
              <label className="block text-xs font-medium text-muted">Development sign-in</label>
              <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                type="email"
                placeholder="you@fund.vc"
                className="w-full rounded-lg border border-line px-3 py-2 text-sm"
              />
              <button type="submit" className="w-full rounded-lg bg-ink px-3 py-2 text-sm font-medium text-white">
                Sign in
              </button>
            </form>
            <div className="mt-5">
              <p className="text-xs text-muted">Seeded users (run make seed):</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {SEEDED.map((s) => (
                  <button key={s} onClick={() => devLogin(s)} className="rounded-full border border-line px-2 py-0.5 text-xs hover:bg-slate-50">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
        {error && <p className="mt-4 rounded-lg bg-rose-50 p-2 text-sm text-rose-800">{error}</p>}
        {cfg && !cfg.devLogin && !cfg.sso && <p className="mt-6 text-sm text-muted">No sign-in method is configured.</p>}
      </div>
    </div>
  );
}
