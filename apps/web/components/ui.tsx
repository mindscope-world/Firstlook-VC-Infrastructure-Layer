import Link from "next/link";
import type { ReactNode } from "react";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-7 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="display text-[34px] leading-tight">{title}</h1>
        {subtitle && <p className="mt-1.5 max-w-2xl text-[15px] text-muted">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Card({ title, children, actions, className = "" }: { title?: ReactNode; children: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <section
      className={`rounded-3xl bg-panel/90 shadow-[0_12px_40px_rgba(16,19,26,0.06),0_1px_2px_rgba(16,19,26,0.04)] backdrop-blur ${className}`}
    >
      {title && (
        <header className="flex items-center justify-between border-b border-line px-6 py-4">
          <h2 className="text-[15px] font-semibold tracking-[-0.01em]">{title}</h2>
          {actions}
        </header>
      )}
      <div className="px-6 py-5">{children}</div>
    </section>
  );
}

const TONES: Record<string, string> = {
  neutral: "bg-[#f1eeea] text-muted",
  brand: "bg-brand-soft text-brand-deep",
  warn: "bg-[#fdf0dc] text-[#9a5b12]",
  bad: "bg-[#fbe3df] text-[#a33a2c]",
  good: "bg-[#e5f0e8] text-[#2f6b45]",
  info: "bg-[#e3ebf4] text-[#39577a]",
};

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: keyof typeof TONES }) {
  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${TONES[tone]}`}>{children}</span>;
}

export function Strength({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-xs text-muted">—</span>;
  const pct = Math.round(value * 100);
  const color = value >= 0.6 ? "bg-brand" : value >= 0.35 ? "bg-[#f0b27a]" : "bg-[#d9d2cc]";
  return (
    <span className="inline-flex items-center gap-2" title={`Relationship strength ${value.toFixed(2)}`}>
      <span className="h-1.5 w-16 overflow-hidden rounded-full bg-[#efe9e3]">
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
    primary: "bg-ink text-white hover:bg-ink-soft",
    secondary: "bg-white text-ink shadow-[0_4px_14px_rgba(16,19,26,0.07),0_1px_2px_rgba(16,19,26,0.06)] hover:shadow-[0_8px_22px_rgba(16,19,26,0.1)]",
    danger: "bg-white text-[#a33a2c] shadow-[0_1px_2px_rgba(16,19,26,0.08)] hover:bg-[#fbe3df]",
    ghost: "text-muted hover:text-ink",
  }[variant];
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium transition active:scale-[0.98] disabled:opacity-50 ${styles}`}
    >
      {children}
    </button>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-6 text-center text-sm text-muted">{children}</p>;
}

export function Loading({ error }: { error?: string | null }) {
  if (error) return <p className="rounded-2xl bg-[#fbe3df] p-3 text-sm text-[#a33a2c]">{error}</p>;
  return <p className="py-6 text-center text-sm text-muted">Loading…</p>;
}

export function EntityLink({ type, id, children }: { type: "person" | "company"; id: string | null | undefined; children: ReactNode }) {
  if (!id) return <>{children}</>;
  return (
    <Link href={`/${type === "person" ? "people" : "companies"}/${id}`} className="font-medium text-ink decoration-brand decoration-2 underline-offset-4 hover:underline">
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
              <span className={person.internal ? "rounded-full bg-ink px-2.5 py-0.5 text-white [&_a]:text-white" : ""}>
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
