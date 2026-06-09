"use client";

import type { ReactNode } from "react";

export function RankBadge({ rank }: { rank: number }) {
  if (rank === 1) return <span className="text-base">🥇</span>;
  if (rank === 2) return <span className="text-base">🥈</span>;
  if (rank === 3) return <span className="text-base">🥉</span>;
  return <span className="w-5 text-center text-sm text-[#5c5470] tabular-nums">{rank}</span>;
}

export function MiniBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.max((value / max) * 100, 0.5) : 0;
  return (
    <div className="flex-1 h-1 bg-[rgba(167,139,250,0.06)] rounded-full overflow-hidden min-w-[16px]">
      <div className="h-full rounded-full bar-grow" style={{ "--bar-width": `${pct}%`, backgroundColor: color } as React.CSSProperties} />
    </div>
  );
}

export function ScoreGauge({ label, value, color, delay = 0 }: { label: string; value: number; color: string; delay?: number }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="text-sm text-[#7e7594] w-7">{label}</span>
      <div className="flex-1 h-1.5 bg-[rgba(167,139,250,0.06)] rounded-full overflow-hidden">
        <div className={`h-full rounded-full bar-grow${delay ? ` bar-delay-${delay}` : ""}`}
          style={{ "--bar-width": `${(value / 10) * 100}%`, backgroundColor: color } as React.CSSProperties} />
      </div>
      <span className="text-sm tabular-nums font-medium w-7 text-right" style={{ color }}>{value.toFixed(1)}</span>
    </div>
  );
}

export function EmptyState({ emoji, title, desc }: { emoji: string; title: string; desc: string }) {
  return (
    <div className="cosmic-card rounded-xl border border-[rgba(167,139,250,0.06)] bg-[rgba(167,139,250,0.01)] flex flex-col items-center justify-center py-20 text-center">
      <p className="text-4xl mb-3">{emoji}</p>
      <p className="text-base font-medium text-[#c4bdd4] mb-1">{title}</p>
      {desc && <p className="text-sm text-[#5c5470]">{desc}</p>}
    </div>
  );
}

export function PageHeader({ title, subtitle, right }: { title: string; subtitle?: string; right?: ReactNode }) {
  return (
    <div className="px-5 md:px-8 pt-6 pb-3 flex items-center justify-between flex-wrap gap-3">
      <div>
        <h1 className="text-lg font-semibold tracking-tight text-[#eae4f0]">{title}</h1>
        {subtitle && <p className="text-sm text-[#7e7594] mt-0.5">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

// ── Cosmic Loading ──
export function LoadingScreen() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="flex flex-col items-center gap-4">
        {/* Spinning nebula */}
        <div className="relative w-12 h-12">
          <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-[#a78bfa] border-r-[rgba(167,139,250,0.3)] animate-spin" />
          <div className="absolute inset-1.5 rounded-full border-2 border-transparent border-b-[#38bdf8] border-l-[rgba(56,189,248,0.3)] animate-spin" style={{ animationDirection: "reverse", animationDuration: "1.5s" }} />
          <div className="absolute inset-3 rounded-full bg-[rgba(167,139,250,0.1)]" />
        </div>
        <p className="text-sm text-[#7e7594] animate-pulse">加载中...</p>
      </div>
    </div>
  );
}

export function LoadingTable() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="flex items-center gap-4 p-4">
        <div className="h-4 w-24 bg-[rgba(167,139,250,0.06)] rounded" />
        <div className="h-4 w-16 bg-[rgba(167,139,250,0.04)] rounded" />
        <div className="h-4 w-16 bg-[rgba(167,139,250,0.04)] rounded" />
      </div>
      {Array(6).fill(0).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4" style={{ opacity: 1 - i * 0.12 }}>
          <div className="h-3 w-5 bg-[rgba(167,139,250,0.04)] rounded" />
          <div className="h-3 w-28 bg-[rgba(167,139,250,0.06)] rounded" />
          <div className="h-3 w-16 bg-[rgba(167,139,250,0.04)] rounded" />
          <div className="h-3 w-16 bg-[rgba(167,139,250,0.04)] rounded" />
          <div className="h-3 w-12 bg-[rgba(167,139,250,0.03)] rounded ml-auto" />
        </div>
      ))}
    </div>
  );
}
