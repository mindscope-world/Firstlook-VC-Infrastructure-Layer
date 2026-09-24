"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import {
  Briefcase,
  Building2,
  GitMerge,
  Inbox,
  LayoutDashboard,
  LogOut,
  Mail,
  Plug,
  Search,
  Settings,
  Users,
} from "lucide-react";
import { api, useApi } from "@/lib/api";

export interface Me {
  userId: string;
  tenantId: string;
  role: string;
  email: string;
  name: string;
  tenant_name: string;
}

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/inbox", label: "Inbox", icon: Inbox },
  { href: "/interactions", label: "Interactions", icon: Mail },
  { href: "/people", label: "People", icon: Users },
  { href: "/companies", label: "Companies", icon: Building2 },
  { href: "/deals", label: "Deals", icon: Briefcase },
  { href: "/review", label: "Review queue", icon: GitMerge },
  { href: "/connections", label: "Connections", icon: Plug },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: me } = useApi<Me>("/me");
  const [q, setQ] = useState("");

  async function logout() {
    await api("/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r border-line bg-white">
        <div className="px-5 py-5">
          <Link href="/" className="text-lg font-semibold tracking-tight">
            first<span className="text-brand">look</span>
          </Link>
          {me && <p className="mt-0.5 truncate text-xs text-muted">{me.tenant_name}</p>}
        </div>
        <form
          className="px-3 pb-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (q.trim()) router.push(`/search?q=${encodeURIComponent(q.trim())}`);
          }}
        >
          <label className="flex items-center gap-2 rounded-lg border border-line px-2.5 py-1.5 text-sm">
            <Search size={14} className="text-muted" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search" className="w-full bg-transparent outline-none" />
          </label>
        </form>
        <nav className="flex-1 space-y-0.5 px-3">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-sm ${
                  active ? "bg-slate-100 font-medium text-ink" : "text-slate-600 hover:bg-slate-50"
                }`}
              >
                <Icon size={16} />
                {label}
              </Link>
            );
          })}
        </nav>
        {me && (
          <div className="border-t border-line px-4 py-3 text-sm">
            <p className="truncate font-medium">{me.name}</p>
            <p className="truncate text-xs text-muted">
              {me.email} · {me.role}
            </p>
            <button onClick={logout} className="mt-2 inline-flex items-center gap-1 text-xs text-muted hover:text-ink">
              <LogOut size={12} /> Sign out
            </button>
          </div>
        )}
      </aside>
      <main className="min-w-0 flex-1 px-8 py-8">
        <div className="mx-auto max-w-6xl">{children}</div>
      </main>
    </div>
  );
}
