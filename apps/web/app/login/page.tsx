"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, useApi } from "@/lib/api";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:13001";
const SEEDED = ["paul@savanna.vc", "amani@savanna.vc", "grace@savanna.vc", "tom@savanna.vc", "lena@harbor.capital"];

export default function LoginPage() {
  const router = useRouter();
  const { data: cfg } = useApi<{ devLogin: boolean; sso: boolean }>("/auth/config");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [checking, setChecking] = useState(true);

  // Already signed in: go straight to the app. Coming from the landing page
  // with ?email=..., sign in with it right away.
  useEffect(() => {
    const handed = new URLSearchParams(window.location.search).get("email");
    fetch("/api/me", { credentials: "same-origin" })
      .then((r) => {
        if (r.ok) {
          router.replace("/");
          return;
        }
        if (handed) {
          setEmail(handed);
          void devLogin(handed);
        }
        setChecking(false);
      })
      .catch(() => setChecking(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function devLogin(address: string) {
    setError(null);
    try {
      await api("/auth/dev-login", { method: "POST", json: { email: address } });
      router.push("/");
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      setError(
        status === 404
          ? `No user with the email ${address}. Add yourself with: make add-user EMAIL=${address} NAME="Your Name". Or pick a seeded user below.`
          : status === 0 || status >= 500
            ? "Couldn't reach the Firstlook API. Is `make dev` running?"
            : e instanceof Error
              ? e.message
              : String(e),
      );
    }
  }

  if (checking) {
    return <div className="flex min-h-screen items-center justify-center text-sm text-muted">Signing in…</div>;
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6">
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
              <p className="text-xs text-muted">Signs you in immediately as an existing user. No email is sent.</p>
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
      <a href={SITE_URL} className="text-xs text-muted hover:text-ink">
        ← Back to firstlook site
      </a>
    </div>
  );
}
