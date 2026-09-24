// Firstlook mark, identical to the landing page (apps/marketing/src/components/Logo.tsx).
export function LogoMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 22 22" aria-hidden="true">
      <circle cx="11" cy="11" r="8.7" fill="none" stroke="#E7893A" strokeWidth="3.2" />
      <circle cx="13.2" cy="8.4" r="2.5" fill="#10131A" />
    </svg>
  );
}

export function Wordmark() {
  return (
    <span className="inline-flex items-center gap-2.5">
      <LogoMark />
      <span className="text-[21px] font-bold tracking-[-0.03em] text-ink">Firstlook</span>
    </span>
  );
}
