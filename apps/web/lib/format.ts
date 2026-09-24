export function date(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function relative(value: string | null | undefined): string {
  if (!value) return "never";
  const days = Math.round((Date.now() - new Date(value).getTime()) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.round(days / 30)}mo ago`;
  return `${Math.round(days / 365)}y ago`;
}

export function usd(value: number | null | undefined): string {
  if (!value) return "—";
  return value >= 1_000_000 ? `$${(value / 1_000_000).toFixed(1)}M` : `$${Math.round(value / 1000)}k`;
}

export const STAGES = ["sourced", "screening", "diligence", "ic", "term_sheet", "invested", "passed"] as const;
export const STAGE_LABEL: Record<string, string> = {
  sourced: "Sourced",
  screening: "Screening",
  diligence: "Diligence",
  ic: "IC",
  term_sheet: "Term sheet",
  invested: "Invested",
  passed: "Passed",
};
