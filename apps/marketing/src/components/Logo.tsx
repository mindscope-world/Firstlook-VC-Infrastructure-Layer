import React from 'react';

// Firstlook mark from the Hero design: an orange ring with an off-centre
// "pupil", like an eye glancing up and right.
export const LogoMark: React.FC<{ size?: number; className?: string }> = ({ size = 22, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 22 22" className={className} aria-hidden="true">
    <circle cx="11" cy="11" r="8.7" fill="none" stroke="#E7893A" strokeWidth="3.2" />
    <circle cx="13.2" cy="8.4" r="2.5" fill="#10131A" />
  </svg>
);

export const Wordmark: React.FC<{ className?: string }> = ({ className = '' }) => (
  <span className={`inline-flex items-center gap-2.5 ${className}`}>
    <LogoMark />
    <span className="text-[21px] font-bold tracking-[-0.03em] text-[#10131A]">Firstlook</span>
  </span>
);
