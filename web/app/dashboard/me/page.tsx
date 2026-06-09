"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { useData } from "@/lib/data-context";
import { LoadingScreen } from "../shared";

interface ScoreData { userId: string; username: string; activePoints: number; sharerPoints: number; researcherPoints: number; collaboratorPoints: number; dragonBalls: number; totalPoints: number; dragonBallReason?: string; }

function ScoreGauge({ label, value, color, delay }: { label: string; value: number; color: string; delay: number }) {
  return (<div className="flex items-center gap-3"><span className="text-sm text-[#7e7594] w-12">{label}</span><div className="flex-1 h-1.5 bg-[rgba(167,139,250,0.06)] rounded-full overflow-hidden"><div className={`h-full rounded-full bar-grow bar-delay-${delay}`} style={{ "--bar-width": `${(value / 10) * 100}%`, backgroundColor: color } as React.CSSProperties} /></div><span className="text-sm tabular-nums font-semibold w-8 text-right" style={{ color }}>{value}</span></div>);
}

export default function MePage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const { scores: scoresData, loading: dataLoading } = useData();
  const [address, setAddress] = useState({ name: "", phone: "", fullAddress: "", evm: "" });
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (!authLoading && !user) router.push("/"); }, [authLoading, user, router]);
  useEffect(() => { if (!user) return; fetch("/api/me/address").then(r => r.json()).then(d => { if (d && !d.error) setAddress({ name: d.name || "", phone: d.phone || "", fullAddress: d.fullAddress || "", evm: d.evm || "" }); }); }, [user]);

  if (authLoading || !user) return null;
  if (dataLoading) return <LoadingScreen />;

  const myScore: ScoreData | null = scoresData?.scores.find((s: any) => s.username === user?.username) || null;
  const myRank = myScore ? scoresData!.scores.findIndex((s: any) => s.userId === myScore.userId) + 1 : null;
  const cycle = null;

  const saveAddress = async () => { setSaving(true); await fetch("/api/me/address", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(address) }); setSaving(false); };

  return (
    <div className="min-h-screen">
      <div className="px-5 md:px-8 pt-6 pb-3"><h1 className="text-lg font-semibold tracking-tight text-[#eae4f0]">个人中心</h1></div>
      <div className="px-5 md:px-8 pb-10 space-y-5 max-w-2xl">
        <div className="cosmic-card rounded-xl border border-[rgba(167,139,250,0.08)] bg-[rgba(167,139,250,0.02)] p-5 hover-lift">
          <div className="flex items-center gap-4">
            {user.avatarUrl ? (
              <img src={user.avatarUrl} alt="" className="w-14 h-14 rounded-lg object-cover shadow-[0_0_20px_rgba(167,139,250,0.2)]" />
            ) : (
              <div className="w-14 h-14 rounded-lg bg-gradient-to-br from-violet-400 via-purple-500 to-fuchsia-600 flex items-center justify-center text-xl font-bold text-white shadow-[0_0_20px_rgba(167,139,250,0.2)]">{user.username?.[0] || "?"}</div>
            )}<div><h2 className="text-lg font-semibold text-[#eae4f0]">{user.username}</h2><p className="text-sm text-[#7e7594]">{myRank ? `积分排行 #${myRank}` : "暂无排名"}</p></div></div>
        </div>
        {myScore && (
          <div className="cosmic-card rounded-xl border border-[rgba(167,139,250,0.08)] bg-[rgba(167,139,250,0.02)] p-5">
            <p className="text-sm font-medium text-[#eae4f0] mb-4">当前积分</p>
            <div className="grid grid-cols-2 gap-4 mb-4"><div className="rounded-lg border border-[rgba(167,139,250,0.08)] bg-[rgba(167,139,250,0.02)] p-3 text-center"><p className="text-xs uppercase tracking-wider text-[#5c5470] mb-1">排名</p><p className="text-2xl font-bold text-[#fbbf24]" style={{ textShadow: "0 0 20px rgba(251,191,36,0.15)" }}>#{myRank || "-"}</p></div><div className="rounded-lg border border-[rgba(167,139,250,0.08)] bg-[rgba(167,139,250,0.02)] p-3 text-center"><p className="text-xs uppercase tracking-wider text-[#5c5470] mb-1">总积分</p><p className="text-2xl font-bold tabular-nums text-[#eae4f0]">{myScore.totalPoints}</p></div></div>
            <div className="space-y-2"><ScoreGauge label="活跃" value={myScore.activePoints} color="#22d3a0" delay={1} /><ScoreGauge label="分享" value={myScore.sharerPoints} color="#fbbf24" delay={2} /><ScoreGauge label="研究" value={myScore.researcherPoints} color="#a78bfa" delay={3} /><ScoreGauge label="协作" value={myScore.collaboratorPoints} color="#38bdf8" delay={4} /></div>
            {myScore.dragonBalls > 0 && (<div className="mt-4 rounded-lg border border-[rgba(251,191,36,0.12)] bg-[rgba(251,191,36,0.03)] p-4 text-center dragon-glow"><p className="text-2xl mb-1">🐉</p><p className="text-sm font-semibold text-[#fbbf24]">龙珠提名</p>{myScore.dragonBallReason && <p className="text-sm text-[#fbbf24]/70 mt-1.5 leading-relaxed">{myScore.dragonBallReason}</p>}</div>)}
          </div>
        )}
        <div className="cosmic-card rounded-xl border border-[rgba(167,139,250,0.08)] bg-[rgba(167,139,250,0.02)] p-5">
          <p className="text-sm font-medium text-[#eae4f0] mb-4">收货地址 & 钱包</p>
          <div className="space-y-3">
            {[{ label: "收货人", key: "name", ph: "姓名" },{ label: "手机号", key: "phone", ph: "手机号" },{ label: "详细地址", key: "fullAddress", ph: "省市区 + 详细地址" },{ label: "EVM 钱包（抽奖用）", key: "evm", ph: "0x...", mono: true }].map(({ label, key, ph, mono }) => (<div key={key}><label className="text-sm text-[#7e7594] block mb-1">{label}</label><input value={(address as any)[key]} onChange={e => setAddress({ ...address, [key]: e.target.value })} className={`w-full rounded-md border border-[rgba(167,139,250,0.1)] bg-[rgba(167,139,250,0.03)] px-3 py-2 text-sm text-[#c4bdd4] outline-none focus:border-[rgba(167,139,250,0.25)] transition-all ${mono ? "font-mono" : ""}`} placeholder={ph} /></div>))}
          </div>
          <Button onClick={saveAddress} disabled={saving} className="mt-4 w-full rounded-md bg-[rgba(167,139,250,0.15)] hover:bg-[rgba(167,139,250,0.25)] text-[#c4bdd4] hover:text-[#eae4f0] text-sm font-medium py-2 h-auto transition-all border border-[rgba(167,139,250,0.15)]">{saving ? "保存中..." : "保存地址"}</Button>
        </div>
      </div>
    </div>
  );
}
