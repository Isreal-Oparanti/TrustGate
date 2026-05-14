"use client";

import { useEffect, useState } from "react";
import { animate, motion, useMotionValue, useMotionValueEvent, useTransform } from "framer-motion";
import { getScoreColor } from "@/lib/utils";

interface ScoreRingProps {
  score: number;
  size?: "sm" | "md" | "lg";
}

const sizes = {
  sm: { box: 64, stroke: 6, label: "text-[20px]", sub: "text-[10px]" },
  md: { box: 96, stroke: 8, label: "text-[28px]", sub: "text-[11px]" },
  lg: { box: 128, stroke: 10, label: "text-[36px]", sub: "text-[12px]" },
};

export function ScoreRing({ score, size = "md" }: ScoreRingProps) {
  const config = sizes[size];
  const radius = (config.box - config.stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const scoreValue = Math.max(0, Math.min(100, score));
  const color = getScoreColor(scoreValue);
  const motionScore = useMotionValue(0);
  const rounded = useTransform(motionScore, (latest) => Math.round(latest));
  const [displayScore, setDisplayScore] = useState(0);

  useMotionValueEvent(rounded, "change", (latest) => setDisplayScore(latest));

  useEffect(() => {
    const controls = animate(motionScore, scoreValue, {
      duration: 1.2,
      ease: "easeOut",
    });
    return controls.stop;
  }, [motionScore, scoreValue]);

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: config.box, height: config.box }}>
      <svg className="-rotate-90" width={config.box} height={config.box} viewBox={`0 0 ${config.box} ${config.box}`}>
        <circle
          cx={config.box / 2}
          cy={config.box / 2}
          r={radius}
          fill="none"
          stroke="#E8EEF2"
          strokeWidth={config.stroke}
        />
        <motion.circle
          cx={config.box / 2}
          cy={config.box / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeLinecap="round"
          strokeWidth={config.stroke}
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference * (1 - scoreValue / 100) }}
          transition={{ duration: 1.2, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <span className={`${config.label} font-bold leading-none text-[#0B3142]`}>{displayScore}</span>
        <span className={`${config.sub} font-medium leading-normal text-[#8FA3AF]`}>/ 100</span>
      </div>
    </div>
  );
}
