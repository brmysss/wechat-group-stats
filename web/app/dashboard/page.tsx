"use client";

import { useMemo } from "react";
import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useData } from "@/lib/data-context";
import { RankBadge, MiniBar, ScoreGauge, PageHeader, LoadingScreen } from "./shared";

export default function ScoresPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const { scores: scoresData, loading: dataLoading } = useData();
  const myScore = useMemo(() => {
    if (!scoresData || !user) return null;
    return scoresData.scores.find(s => s.username === user.username) || null;
  }, [scoresData, user]);

  if (authLoading || !user) return null;
  if (dataLoading) return <LoadingScreen />;
  if (!scoresData || scoresData.scores.length === 0) {
    return <div className="min-h-screen"><PageHeader title="积分排行" subtitle="双周积分周期" /><div className="px-5 md:px-8 pb-10"><div className="cosmic-card rounded-xl border border-[rgba(167,139,250,0.06)] bg-[rgba(167,139,250,0.01)] flex flex-col items-center justify-center py-20 text-center"><p className="text-4xl mb-3">🤖</p><p className="text-base font-medium text-[#c4bdd4] mb-1">AI 评分尚未生成</p><p className="text-sm text-[#5c5470]">等待下周结算</p></div></div></div>;
  }

  const myRank = scoresData.scores.findIndex(s => s.userId === myScore?.userId) + 1;

  return (
    <div className="min-h-screen">
      <PageHeader title="积分排行"
        right={<div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-[rgba(167,139,250,0.04)] border border-[rgba(167,139,250,0.08)]">{user.avatarUrl ? <img src={user.avatarUrl} alt="" className="w-4 h-4 rounded-full object-cover" /> : <div className="w-4 h-4 rounded bg-gradient-to-br from-violet-400 to-fuchsia-600 flex items-center justify-center text-xs font-bold text-white shadow-[0_0_6px_rgba(167,139,250,0.15)]">{user.username?.[0] || "?"}</div>}<span className="text-sm text-[#c4bdd4]">{user.username}</span></div>}
      />
      <div className="px-5 md:px-8 pb-10 space-y-4">
        <div className="cosmic-card rounded-xl border border-[rgba(167,139,250,0.08)] bg-[rgba(167,139,250,0.02)] p-4 flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-3">
            {myScore?.avatarUrl ? (
              <img src={myScore.avatarUrl} alt="" className="w-8 h-8 rounded-full object-cover" />
            ) : (
              <div className="w-8 h-8 rounded-md bg-gradient-to-br from-violet-400 via-purple-500 to-fuchsia-600 flex items-center justify-center text-sm font-bold text-white shadow-[0_0_12px_rgba(167,139,250,0.15)]">{user.username?.[0] || "?"}</div>
            )}<div><p className="text-sm font-semibold text-[#eae4f0]">{user.username}</p><p className="text-sm text-[#7e7594]">第 {myRank || "-"} 名</p></div></div>
          <div className="flex items-center gap-6">
            <div className="text-center"><p className="text-xs uppercase tracking-wider text-[#5c5470]">排名</p><p className="text-xl font-bold text-[#fbbf24]" style={{ textShadow: "0 0 16px rgba(251,191,36,0.12)" }}>#{myRank || "-"}</p></div>
            <div className="text-center"><p className="text-xs uppercase tracking-wider text-[#5c5470]">积分</p><p className="text-xl font-bold tabular-nums text-[#eae4f0]">{myScore?.totalPoints || 0}</p></div>
            {myScore && myScore.dragonBalls > 0 && (<div className="rounded-md bg-[rgba(251,191,36,0.05)] border border-[rgba(251,191,36,0.1)] px-3 py-1.5 text-center dragon-glow"><p className="text-sm">🐉</p><p className="text-xs text-[#fbbf24] font-medium">龙珠</p></div>)}
            <div className="hidden md:flex flex-col gap-0.5 min-w-[140px]"><ScoreGauge label="活跃" value={myScore?.activePoints || 0} color="#22d3a0" delay={1} /><ScoreGauge label="分享" value={myScore?.sharerPoints || 0} color="#fbbf24" delay={2} /><ScoreGauge label="研究" value={myScore?.researcherPoints || 0} color="#a78bfa" delay={3} /><ScoreGauge label="协作" value={myScore?.collaboratorPoints || 0} color="#38bdf8" delay={4} /></div>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {[{ label: "参评人数", value: scoresData.scores.length, color: "#22d3a0" },{ label: "龙珠提名", value: scoresData.dragonBallCount, color: "#fbbf24" },{ label: "平均分", value: (scoresData.scores.reduce((s, sc) => s + sc.totalPoints, 0) / scoresData.scores.length).toFixed(1), color: "#c4bdd4" },{ label: "最高分", value: scoresData.scores[0]?.totalPoints || 0, color: "#a78bfa" }].map(({ label, value, color }) => (
            <div key={label} className="cosmic-card rounded-lg border border-[rgba(167,139,250,0.06)] bg-[rgba(167,139,250,0.02)] p-3 text-center"><p className="text-xs uppercase tracking-wider text-[#5c5470] mb-1">{label}</p><p className="text-lg font-bold tabular-nums" style={{ color }}>{value}</p></div>
          ))}
        </div>
        <div className="cosmic-card rounded-xl border border-[rgba(167,139,250,0.07)] bg-[rgba(167,139,250,0.01)] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead><tr className="text-xs font-medium uppercase tracking-wider text-[#5c5470] border-b border-[rgba(167,139,250,0.06)]"><th className="text-left py-2.5 px-4 w-10">#</th><th className="text-left py-2.5 px-4">成员</th><th className="text-left py-2.5 px-3 hidden sm:table-cell">活跃</th><th className="text-left py-2.5 px-3 hidden sm:table-cell">分享</th><th className="text-left py-2.5 px-3 hidden md:table-cell">研究</th><th className="text-left py-2.5 px-3 hidden md:table-cell">协作</th><th className="text-right py-2.5 px-4">总分</th></tr></thead>
              <tbody className="text-sm">
                {scoresData.scores.map((s, i) => {
                  const isMe = user.username === s.username;
                  const topColor = i === 0 ? "#fbbf24" : i === 1 ? "#94a3b8" : i === 2 ? "#d97706" : undefined;
                  return (<tr key={s.userId} className={`border-b border-[rgba(167,139,250,0.03)] transition-colors ${isMe ? "bg-[rgba(167,139,250,0.05)]" : "hover:bg-[rgba(167,139,250,0.015)]"}`}><td className="py-2 px-4"><RankBadge rank={i + 1} /></td><td className="py-2 px-4 font-medium whitespace-nowrap flex items-center gap-2">{s.avatarUrl ? <img src={s.avatarUrl} alt="" className="w-5 h-5 rounded-full object-cover shrink-0" /> : <div className="w-5 h-5 rounded-full bg-gradient-to-br from-violet-400 to-purple-600 flex items-center justify-center text-[10px] font-bold text-white shrink-0">{(s.username || "?")[0]}</div>}{s.username}{isMe && <span className="ml-1 text-sm text-[#a78bfa]">你</span>}{s.dragonBalls > 0 && <span className="ml-0.5">🐉</span>}</td><td className="py-2 px-3 tabular-nums hidden sm:table-cell" style={{ color: s.activePoints >= 7 ? "#22d3a0" : s.activePoints >= 4 ? "#c4bdd4" : "#5c5470" }}>{s.activePoints}</td><td className="py-2 px-3 tabular-nums hidden sm:table-cell" style={{ color: s.sharerPoints >= 7 ? "#fbbf24" : s.sharerPoints >= 4 ? "#c4bdd4" : "#5c5470" }}>{s.sharerPoints}</td><td className="py-2 px-3 tabular-nums hidden md:table-cell" style={{ color: s.researcherPoints >= 7 ? "#a78bfa" : s.researcherPoints >= 4 ? "#c4bdd4" : "#5c5470" }}>{s.researcherPoints}</td><td className="py-2 px-3 tabular-nums hidden md:table-cell" style={{ color: s.collaboratorPoints >= 7 ? "#38bdf8" : s.collaboratorPoints >= 4 ? "#c4bdd4" : "#5c5470" }}>{s.collaboratorPoints}</td><td className="py-2 px-4 text-right tabular-nums font-semibold" style={{ color: topColor || "#eae4f0" }}><div className="flex items-center justify-end gap-2"><span>{s.totalPoints}</span><div className="w-8 hidden sm:block"><MiniBar value={s.totalPoints} max={scoresData.scores[0]?.totalPoints || 1} color={i === 0 ? "#fbbf24" : "#22d3a0"} /></div></div></td></tr>);
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
