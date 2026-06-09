"use client";

import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useData } from "@/lib/data-context";
import { PageHeader, LoadingScreen } from "../shared";

export default function DragonsPage() {
  const { user, loading: authLoading } = useAuth();
  const { scores: scoresData, loading: dataLoading } = useData();
  if (authLoading || !user) return null;
  if (dataLoading) return <LoadingScreen />;
  const dh = scoresData?.scores.filter(s => s.dragonBalls > 0) || [];
  return (
    <div className="min-h-screen">
      <PageHeader title="龙珠榜" subtitle="龙珠得主" right={dh.length > 0 ? <span className="text-sm text-[#7e7594]">{dh.length} 位得主</span> : undefined} />
      <div className="px-5 md:px-8 pb-10">
        {dh.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {dh.map((s, i) => (
              <div key={s.userId} className="cosmic-card rounded-xl border border-[rgba(251,191,36,0.1)] bg-[rgba(251,191,36,0.015)] overflow-hidden dragon-glow hover-lift" style={{ transitionDelay: `${i * 100}ms` }}>
                <div className="p-4">
                  <div className="flex items-center justify-between mb-3"><div className="flex items-center gap-3"><div className="w-9 h-9 rounded-lg bg-gradient-to-br from-amber-400 to-orange-600 flex items-center justify-center text-base shadow-[0_0_14px_rgba(251,191,36,0.15)]">🐉</div><div><p className="text-sm font-semibold text-[#eae4f0]">{s.username}</p><p className="text-sm text-[#7e7594]">🐉 社群贡献者</p></div></div><p className="text-lg font-bold text-[#fbbf24] tabular-nums" style={{ textShadow: "0 0 14px rgba(251,191,36,0.12)" }}>{s.totalPoints}</p></div>
                  <div className="grid grid-cols-4 gap-2 mb-3">
                    {[{ label: "活跃", value: s.activePoints, color: "#22d3a0" },{ label: "分享", value: s.sharerPoints, color: "#fbbf24" },{ label: "研究", value: s.researcherPoints, color: "#a78bfa" },{ label: "协作", value: s.collaboratorPoints, color: "#38bdf8" }].map(({ label, value, color }) => (<div key={label} className="text-center"><p className="text-xs text-[#5c5470] mb-0.5">{label}</p><p className="text-sm font-semibold tabular-nums" style={{ color }}>{value}</p></div>))}
                  </div>
                  {s.dragonBallReason && (<div className="border-t border-[rgba(251,191,36,0.08)] pt-2.5"><p className="text-xs uppercase tracking-wider text-[#7e7594] mb-1">获奖理由</p><p className="text-sm text-[#fbbf24]/80 leading-relaxed">{s.dragonBallReason}</p></div>)}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="cosmic-card rounded-xl border border-[rgba(167,139,250,0.06)] bg-[rgba(167,139,250,0.01)] flex flex-col items-center justify-center py-20 text-center"><p className="text-4xl mb-3">🐉</p><p className="text-base font-medium text-[#c4bdd4] mb-1">{scoresData ? "本期暂无龙珠提名" : "等待 AI 评分完成"}</p><p className="text-sm text-[#5c5470]">积分排行前列将自动获得提名资格</p></div>
        )}
      </div>
    </div>
  );
}
