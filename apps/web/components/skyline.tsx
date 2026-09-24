// Dawn-city skyline from the landing page hero (apps/marketing HeroSkyline),
// without the hero's buttons. Decorative.
import { useMemo } from "react";

type Step = [x0: number, x1: number, top: number];

// Far haze: pale mauve blocks against the peach horizon.
const HAZE_LIGHT: Step[] = [
  [380, 413, 774], [413, 430, 734], [430, 447, 723], [447, 484, 739], [484, 545, 785], [545, 598, 803],
  [598, 640, 771], [640, 700, 788], [700, 735, 757], [735, 800, 780], [800, 820, 740], [820, 836, 690],
  [836, 863, 748], [863, 990, 790], [990, 1028, 791], [1028, 1089, 780], [1089, 1153, 797],
  [1153, 1193, 766], [1193, 1227, 740], [1227, 1300, 768], [1300, 1340, 750],
];

// Middle haze: dustier mauve, lower.
const HAZE_MID: Step[] = [
  [370, 390, 734], [390, 440, 791], [484, 574, 817], [574, 650, 844], [650, 760, 856], [760, 900, 872],
  [900, 1000, 863], [1000, 1083, 849], [1083, 1151, 833], [1151, 1217, 805], [1217, 1239, 812],
  [1239, 1282, 782], [1282, 1308, 790], [1308, 1330, 748],
];

// Near centre: charcoal blocks with lit windows.
const CHARCOAL: Step[] = [
  [440, 485, 828], [485, 555, 860], [555, 645, 878], [645, 735, 895], [735, 920, 918], [920, 1010, 905],
  [1010, 1100, 888], [1100, 1170, 870], [1170, 1230, 845],
];

// Foreground towers on both sides.
const DARK: Step[] = [
  [0, 110, 597], [110, 160, 620], [160, 195, 654], [195, 266, 694], [266, 300, 671], [300, 370, 734],
  [370, 420, 803], [420, 440, 820], [440, 480, 850], [480, 520, 900], [520, 580, 930],
  [1090, 1110, 930], [1110, 1140, 910], [1140, 1170, 895], [1170, 1190, 873], [1190, 1215, 850],
  [1215, 1235, 820], [1235, 1282, 795], [1282, 1330, 760], [1330, 1376, 702], [1376, 1413, 679],
  [1413, 1457, 643], [1457, 1489, 621], [1489, 1539, 553], [1539, 1584, 565], [1584, 1650, 608],
];

const GROUND = 946;

// Deterministic pseudo-random in [0, 1) so the windows never flicker between renders.
function rand(a: number, b: number): number {
  const s = Math.sin(a * 12.9898 + b * 78.233) * 43758.5453;
  return s - Math.floor(s);
}

function windows(steps: Step[], palette: string[], seed: number) {
  const out: { x: number; y: number; fill: string }[] = [];
  steps.forEach(([x0, x1, top], i) => {
    for (let x = x0 + 7; x + 5 <= x1 - 4; x += 18.5) {
      for (let y = top + 14; y + 9 <= GROUND - 6; y += 25) {
        const r = rand(x + seed, y + i);
        if (r < 0.14) continue; // unlit
        const fill = r > 0.9 ? palette[2] : r > 0.72 ? palette[1] : palette[0];
        out.push({ x, y, fill });
      }
    }
  });
  return out;
}

function blocks(steps: Step[], fill: string) {
  return steps.map(([x0, x1, top]) => (
    <rect key={`${x0}-${top}`} x={x0} y={top} width={x1 - x0 + 0.5} height={GROUND - top} fill={fill} />
  ));
}

export function Skyline({ className = "" }: { className?: string }) {
  const darkWindows = useMemo(() => windows(DARK, ["#997656", "#c39e72", "#d9b788"], 1), []);
  const centreWindows = useMemo(() => windows(CHARCOAL, ["#8f7a6a", "#c8af90", "#e3c9a1"], 7), []);
  return (
    <div className={`pointer-events-none absolute inset-x-0 bottom-0 select-none ${className}`} aria-hidden="true">
      <svg
        viewBox="0 480 1650 552"
        preserveAspectRatio="xMidYMax slice"
        className="absolute inset-0 w-full h-full"
        xmlns="http://www.w3.org/2000/svg"
              >
        <defs>
          <linearGradient id="hazeLight" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#e9d8d0" />
            <stop offset="100%" stopColor="#e0c8bc" />
          </linearGradient>
          <linearGradient id="charcoal" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#4b4852" />
            <stop offset="100%" stopColor="#3a3742" />
          </linearGradient>
          <linearGradient id="road" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#1b1a22" />
            <stop offset="100%" stopColor="#15141b" />
          </linearGradient>
          <linearGradient id="trailGold" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#e39a55" stopOpacity="0.25" />
            <stop offset="45%" stopColor="#e39a55" stopOpacity="0.95" />
            <stop offset="100%" stopColor="#f0b070" stopOpacity="0.9" />
          </linearGradient>
          <linearGradient id="trailRed" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#b8453c" stopOpacity="0.2" />
            <stop offset="60%" stopColor="#c4493d" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#d0584a" stopOpacity="0.7" />
          </linearGradient>
        </defs>

        {blocks(HAZE_LIGHT, 'url(#hazeLight)')}
        {blocks(HAZE_MID, '#ad9ca3')}
        {blocks(CHARCOAL, 'url(#charcoal)')}
        {centreWindows.map((w, i) => (
          <rect key={`c${i}`} x={w.x} y={w.y} width="5" height="9" fill={w.fill} opacity="0.85" />
        ))}
        {blocks(DARK, '#2a2732')}
        {darkWindows.map((w, i) => (
          <rect key={`d${i}`} x={w.x} y={w.y} width="5" height="9" fill={w.fill} />
        ))}

        {/* Antennas */}
        <rect x="51" y="539" width="6" height="58" fill="#2a2732" />
        <rect x="1512" y="505" width="4" height="48" fill="#2a2732" />
        <rect x="826" y="660" width="4" height="30" fill="#e0cdc4" />

        {/* Road and light trails */}
        <rect x="0" y={GROUND} width="1650" height={1032 - GROUND} fill="url(#road)" />
        <path d="M0,1004 C420,996 900,986 1650,962" stroke="url(#trailGold)" strokeWidth="2.2" fill="none" />
        <path d="M0,1016 C500,1010 1000,1000 1650,978" stroke="url(#trailRed)" strokeWidth="1.6" fill="none" />
        <path d="M0,1024 C520,1019 1050,1010 1650,990" stroke="#f3e6da" strokeOpacity="0.35" strokeWidth="1" fill="none" />
        <path d="M0,996 C380,991 900,982 1650,954" stroke="#f3e6da" strokeOpacity="0.18" strokeWidth="1" fill="none" />
      </svg>
    </div>
  );
}
