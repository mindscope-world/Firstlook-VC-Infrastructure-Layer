"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, useApi } from "@/lib/api";
import { LogoMark } from "@/components/logo";
import { Skyline } from "@/components/skyline";

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

  const sky = {
    background: "linear-gradient(180deg, #d4e1ee 0%, #e2e8ef 18%, #eceef2 30%, #f3efec 47%, #f7e9dc 60%, #f7dcc6 78%, #f4d4bc 100%)",
  };

  if (checking) {
    return (
      <div className="relative flex h-screen items-center justify-center overflow-hidden text-sm text-muted" style={sky}>
        Signing in…
        <Skyline className="h-[45%]" />
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen flex-col items-center overflow-hidden px-6 pt-[14vh]" style={sky}>
      <a href={SITE_URL} className="mb-7 inline-flex items-center gap-2.5" aria-label="Firstlook site">
        <LogoMark size={26} />
        <span className="text-[24px] font-bold tracking-[-0.03em]">Firstlook</span>
      </a>
      <div className="relative z-10 w-full max-w-[420px] rounded-[28px] bg-white/90 p-8 shadow-[0_20px_60px_rgba(16,19,26,0.10),0_1px_2px_rgba(16,19,26,0.05)] backdrop-blur-md">
        <h1 className="display text-[30px] leading-tight">Sign in</h1>
        <p className="mt-1 text-[15px] text-muted">to your firm&apos;s Firstlook workspace.</p>

        {cfg?.sso && (
          <a href="/api/auth/workos/start" className="mt-6 flex h-12 items-center justify-center rounded-full bg-ink text-[15px] font-medium text-white hover:bg-ink-soft">
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
              <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-faint">Development sign-in</label>
              <p className="text-xs text-muted">Signs you in immediately as an existing user. No email is sent.</p>
              <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                type="email"
                placeholder="you@fund.vc"
                className="h-12 w-full rounded-full border border-line bg-white px-5 text-[15px] outline-none focus:border-brand focus:ring-4 focus:ring-brand/15"
              />
              <button type="submit" className="flex h-12 w-full items-center justify-center rounded-full bg-ink text-[15px] font-medium text-white hover:bg-ink-soft">
                Sign in
              </button>
            </form>
            <div className="mt-6">
              <p className="text-xs text-faint">Seeded users (run make seed):</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {SEEDED.map((s) => (
                  <button key={s} onClick={() => devLogin(s)} className="rounded-full bg-[#f4f1ed] px-3 py-1 text-xs text-muted hover:bg-brand-soft hover:text-ink">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
        {error && <p className="mt-4 rounded-2xl bg-[#fbe3df] p-3 text-sm text-[#a33a2c]">{error}</p>}
        {cfg && !cfg.devLogin && !cfg.sso && <p className="mt-6 text-sm text-muted">No sign-in method is configured.</p>}
      </div>
      <a href={SITE_URL} className="relative z-10 mt-5 text-sm font-medium text-muted hover:text-ink">
        ← Back to firstlook site
      </a>
      <Skyline className="h-[42%]" />
    </div>
  );
}
