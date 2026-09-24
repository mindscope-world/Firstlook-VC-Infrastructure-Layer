import React, { useMemo } from 'react';

interface HeroSkylineProps {
  onScrollClick: () => void;
}

export const HeroSkyline: React.FC<HeroSkylineProps> = ({ onScrollClick }) => {
  // Precompute building blocks and window states for deterministic, beautiful pixel skyline
  const buildings = useMemo(() => {
    // Left cluster buildings (stepped down toward center)
    const leftBuildings = [
      { x: 0, width: 70, height: 260, cols: 7, rows: 26 },
      { x: 65, width: 60, height: 320, cols: 6, rows: 32 },
      { x: 120, width: 85, height: 280, cols: 8, rows: 28 },
      { x: 200, width: 75, height: 240, cols: 7, rows: 24 },
      { x: 270, width: 90, height: 200, cols: 9, rows: 20 },
      { x: 355, width: 70, height: 160, cols: 7, rows: 16 },
      { x: 420, width: 80, height: 120, cols: 8, rows: 12 },
      { x: 495, width: 75, height: 90, cols: 7, rows: 9 },
      { x: 565, width: 65, height: 60, cols: 6, rows: 6 },
    ];

    // Right cluster buildings (rising up from center toward far right)
    const rightBuildings = [
      { x: 780, width: 65, height: 70, cols: 6, rows: 7 },
      { x: 840, width: 75, height: 110, cols: 7, rows: 11 },
      { x: 910, width: 85, height: 150, cols: 8, rows: 15 },
      { x: 990, width: 70, height: 190, cols: 7, rows: 19 },
      { x: 1055, width: 95, height: 230, cols: 9, rows: 23 },
      { x: 1145, width: 80, height: 270, cols: 8, rows: 27 },
      { x: 1220, width: 90, height: 310, cols: 9, rows: 31 },
      { x: 1305, width: 70, height: 340, cols: 7, rows: 34 },
      { x: 1370, width: 80, height: 290, cols: 8, rows: 29 },
    ];

    return [...leftBuildings, ...rightBuildings];
  }, []);

  return (
    <div className="relative w-full h-[260px] sm:h-[320px] md:h-[380px] overflow-hidden select-none pointer-events-none mt-auto">
      {/* Cityscape SVG with pixel window lights */}
      <svg
        viewBox="0 0 1440 380"
        className="w-full h-full object-cover object-bottom"
        preserveAspectRatio="xMidYMax slice"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <linearGradient id="buildingGradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#1e2029" />
            <stop offset="100%" stopColor="#0d0e12" />
          </linearGradient>
          
          <linearGradient id="rearBuildingGradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#2a2d38" stopOpacity="0.7" />
            <stop offset="100%" stopColor="#14151c" stopOpacity="0.9" />
          </linearGradient>

          <linearGradient id="highwayGold1" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#ff8a00" stopOpacity="0" />
            <stop offset="15%" stopColor="#ff9d1c" stopOpacity="0.8" />
            <stop offset="50%" stopColor="#ffc043" stopOpacity="1" />
            <stop offset="85%" stopColor="#ff9d1c" stopOpacity="0.8" />
            <stop offset="100%" stopColor="#ff8a00" stopOpacity="0" />
          </linearGradient>

          <linearGradient id="highwayGold2" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#f59e0b" stopOpacity="0" />
            <stop offset="25%" stopColor="#f59e0b" stopOpacity="0.9" />
            <stop offset="75%" stopColor="#fbbf24" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#f59e0b" stopOpacity="0" />
          </linearGradient>

          {/* Stepped pixel roof antenna */}
          <pattern id="dotGrid" x="0" y="0" width="10" height="10" patternUnits="userSpaceOnUse">
            <rect x="2" y="2" width="2.5" height="2.5" fill="#fcd34d" opacity="0.6" />
          </pattern>
        </defs>

        {/* Ambient horizon warmth */}
        <ellipse cx="720" cy="380" rx="600" ry="120" fill="rgba(245, 158, 11, 0.08)" />

        {/* Back silhouette layers for architectural depth */}
        <path
          d="M0,380 L0,220 L40,220 L40,180 L90,180 L90,140 L160,140 L160,200 L240,200 L240,250 L340,250 L340,300 L440,300 L440,380 Z"
          fill="url(#rearBuildingGradient)"
        />
        <path
          d="M1440,380 L1440,200 L1380,200 L1380,150 L1300,150 L1300,120 L1220,120 L1220,180 L1130,180 L1130,240 L1030,240 L1030,290 L950,290 L950,380 Z"
          fill="url(#rearBuildingGradient)"
        />

        {/* Foreground pixel buildings with windows */}
        {buildings.map((b, bIdx) => {
          const startY = 380 - b.height;
          const windowW = 3.5;
          const windowH = 3.5;
          const gapX = (b.width - b.cols * windowW) / (b.cols + 1);
          const gapY = (b.height - b.rows * windowH) / (b.rows + 1);

          // Render windows
          const windowElements = [];
          for (let r = 0; r < b.rows; r++) {
            for (let c = 0; c < b.cols; c++) {
              // Deterministic pseudo-randomness for window light state
              const hash = (bIdx * 137 + r * 31 + c * 17) % 100;
              const isLit = hash > 32;
              const isAmber = hash > 82;
              const isSoftWhite = hash > 45 && hash <= 82;

              if (isLit) {
                const wx = b.x + gapX + c * (windowW + gapX);
                const wy = startY + gapY + r * (windowH + gapY);
                const color = isAmber ? '#FBBF24' : isSoftWhite ? '#FEF3C7' : '#F59E0B';
                const opacity = 0.55 + ((hash % 40) / 100);

                windowElements.push(
                  <rect
                    key={`${bIdx}-${r}-${c}`}
                    x={wx}
                    y={wy}
                    width={windowW}
                    height={windowH}
                    fill={color}
                    opacity={opacity}
                    rx="0.5"
                  />
                );
              }
            }
          }

          return (
            <g key={bIdx}>
              {/* Building structure */}
              <rect
                x={b.x}
                y={startY}
                width={b.width}
                height={b.height}
                fill="url(#buildingGradient)"
                stroke="#2a2c36"
                strokeWidth="0.75"
              />
              {/* Building rooftop antenna or decorative spire if prominent */}
              {b.height > 290 && (
                <line
                  x1={b.x + b.width / 2}
                  y1={startY}
                  x2={b.x + b.width / 2}
                  y2={startY - 25}
                  stroke="#fbbf24"
                  strokeWidth="1.5"
                />
              )}
              {b.height > 290 && (
                <circle
                  cx={b.x + b.width / 2}
                  cy={startY - 25}
                  r="2"
                  fill="#ef4444"
                  className="animate-pulse"
                />
              )}
              {/* Windows */}
              {windowElements}
            </g>
          );
        })}

        {/* Highway glowing light ribbons across the bottom */}
        <path
          d="M-50,368 C350,366 550,360 720,358 C890,356 1150,364 1490,368"
          stroke="url(#highwayGold1)"
          strokeWidth="2.5"
          fill="none"
        />
        <path
          d="M-50,373 C300,372 600,366 720,365 C840,364 1200,371 1490,375"
          stroke="url(#highwayGold2)"
          strokeWidth="1.75"
          fill="none"
        />
        <path
          d="M100,377 C450,375 620,371 720,370 C820,369 1100,374 1400,379"
          stroke="rgba(251, 191, 36, 0.4)"
          strokeWidth="1.2"
          fill="none"
        />
      </svg>

      {/* Central "SCROLL ↓" badge from PDF */}
      <div className="absolute bottom-4 sm:bottom-6 left-1/2 -translate-x-1/2 z-20 pointer-events-auto">
        <button
          onClick={onScrollClick}
          aria-label="Scroll to next section"
          className="group flex items-center gap-1.5 px-3.5 py-1 text-[11px] font-semibold tracking-wider uppercase text-neutral-300 hover:text-white bg-[#16181f]/85 hover:bg-[#1f222b] backdrop-blur-md rounded-full border border-neutral-700/60 shadow-lg transition-all duration-200 hover:scale-105 active:scale-95"
        >
          <span>SCROLL</span>
          <span className="text-amber-400 group-hover:translate-y-0.5 transition-transform duration-200">↓</span>
        </button>
      </div>
    </div>
  );
};
