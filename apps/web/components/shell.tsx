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
  Radar,
  Search,
  Settings,
  Users,
} from "lucide-react";
import { api, useApi } from "@/lib/api";
import { Wordmark } from "@/components/logo";

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
  { href: "/sourcing", label: "Sourcing", icon: Radar },
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
      <aside className="sticky top-0 h-screen w-[264px] shrink-0 p-4">
        <div className="flex h-full flex-col rounded-[28px] bg-white/85 shadow-[0_12px_40px_rgba(16,19,26,0.08),0_1px_2px_rgba(16,19,26,0.04)] backdrop-blur-md">
          <div className="px-6 pb-4 pt-6">
            <Link href="/" aria-label="Firstlook home">
              <Wordmark />
            </Link>
            {me && <p className="mt-1.5 truncate pl-[32px] text-xs text-faint">{me.tenant_name}</p>}
          </div>
          <form
            className="px-4 pb-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (q.trim()) router.push(`/search?q=${encodeURIComponent(q.trim())}`);
            }}
          >
            <label className="flex items-center gap-2 rounded-full bg-[#f4f1ed] px-3.5 py-2 text-sm">
              <Search size={15} className="text-faint" />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search people, companies" className="w-full bg-transparent outline-none placeholder:text-faint" />
            </label>
          </form>
          <nav className="flex-1 space-y-1 overflow-y-auto px-4">
            {NAV.map(({ href, label, icon: Icon }) => {
              const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={`flex items-center gap-3 rounded-full px-3.5 py-2 text-[15px] font-medium transition ${
                    active ? "bg-ink text-white" : "text-muted hover:bg-[#f4f1ed] hover:text-ink"
                  }`}
                >
                  <Icon size={17} strokeWidth={active ? 2.2 : 1.9} />
                  {label}
                </Link>
              );
            })}
          </nav>
          {me && (
            <div className="m-4 rounded-2xl bg-[#f7f4f0] px-4 py-3 text-sm">
              <p className="truncate font-semibold">{me.name}</p>
              <p className="truncate text-xs text-faint">
                {me.email} · {me.role}
              </p>
              <button onClick={logout} className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-muted hover:text-ink">
                <LogOut size={12} /> Sign out
              </button>
            </div>
          )}
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-6 py-10 lg:px-10">
        <div className="mx-auto max-w-6xl">{children}</div>
      </main>
    </div>
  );
}
