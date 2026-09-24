import Link from "next/link";
import type { ReactNode } from "react";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Card({ title, children, actions, className = "" }: { title?: ReactNode; children: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-line bg-panel ${className}`}>
      {title && (
        <header className="flex items-center justify-between border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold">{title}</h2>
          {actions}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

const TONES: Record<string, string> = {
  neutral: "bg-slate-100 text-slate-700",
  brand: "bg-brand-soft text-teal-900",
  warn: "bg-amber-100 text-amber-900",
  bad: "bg-rose-100 text-rose-800",
  good: "bg-emerald-100 text-emerald-800",
  info: "bg-sky-100 text-sky-800",
};

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: keyof typeof TONES }) {
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${TONES[tone]}`}>{children}</span>;
}

export function Strength({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-xs text-muted">—</span>;
  const pct = Math.round(value * 100);
  const color = value >= 0.6 ? "bg-emerald-500" : value >= 0.35 ? "bg-amber-400" : "bg-slate-300";
  return (
    <span className="inline-flex items-center gap-2" title={`Relationship strength ${value.toFixed(2)}`}>
      <span className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
        <span className={`block h-full ${color}`} style={{ width: `${pct}%` }} />
      </span>
      <span className="text-xs tabular-nums text-muted">{value.toFixed(2)}</span>
    </span>
  );
}

export function Button({
  children,
  onClick,
  variant = "primary",
  disabled,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "danger" | "ghost";
  disabled?: boolean;
  type?: "button" | "submit";
}) {
  const styles = {
    primary: "bg-brand text-white hover:bg-teal-800",
    secondary: "border border-line bg-white hover:bg-slate-50",
    danger: "border border-rose-200 bg-white text-rose-700 hover:bg-rose-50",
    ghost: "text-muted hover:text-ink",
  }[variant];
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:opacity-50 ${styles}`}
    >
      {children}
    </button>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-6 text-center text-sm text-muted">{children}</p>;
}

export function Loading({ error }: { error?: string | null }) {
  if (error) return <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{error}</p>;
  return <p className="py-6 text-center text-sm text-muted">Loading…</p>;
}

export function EntityLink({ type, id, children }: { type: "person" | "company"; id: string | null | undefined; children: ReactNode }) {
  if (!id) return <>{children}</>;
  return (
    <Link href={`/${type === "person" ? "people" : "companies"}/${id}`} className="font-medium text-ink hover:text-brand hover:underline">
      {children}
    </Link>
  );
}

export interface PathPerson {
  id: string;
  name: string;
  internal: boolean;
  title: string | null;
}
export interface WarmPath {
  path: string[];
  score: number;
  hops: number;
  edge_types: string[];
  people: PathPerson[];
}

export function WarmPaths({ paths }: { paths: WarmPath[] }) {
  if (paths.length === 0) return <Empty>No warm path from the team yet.</Empty>;
  return (
    <ol className="space-y-2">
      {paths.map((p) => (
        <li key={p.path.join("-")} className="flex flex-wrap items-center gap-1.5 text-sm">
          {p.people.map((person, i) => (
            <span key={person.id} className="inline-flex items-center gap-1.5">
              {i > 0 && (
                <span className="text-xs text-muted" title={p.edge_types[i - 1]}>
                  →
                </span>
              )}
              <span className={person.internal ? "rounded bg-brand-soft px-1.5 py-0.5 text-teal-900" : ""}>
                <EntityLink type="person" id={person.id}>
                  {person.name}
                </EntityLink>
              </span>
            </span>
          ))}
          <span className="ml-auto">
            <Strength value={p.score} />
          </span>
        </li>
      ))}
    </ol>
  );
}

/** Body text with each citation highlighted. */
export function CitedText({ text, spans }: { text: string; spans: { start: number; end: number }[] }) {
  const sorted = [...spans].sort((a, b) => a.start - b.start).filter((s, i, arr) => i === 0 || s.start >= arr[i - 1]!.end);
  const parts: ReactNode[] = [];
  let cursor = 0;
  sorted.forEach((s, i) => {
    parts.push(text.slice(cursor, s.start));
    parts.push(
      <mark key={i} className="cite" id={`cite-${s.start}`}>
        {text.slice(s.start, s.end)}
      </mark>,
    );
    cursor = s.end;
  });
  parts.push(text.slice(cursor));
  return <div className="whitespace-pre-wrap text-sm leading-relaxed">{parts}</div>;
}
