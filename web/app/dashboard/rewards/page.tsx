"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { useData } from "@/lib/data-context";
import { LoadingScreen } from "../shared";

const TYPE_CFG: Record<string, { label: string; icon: string }> = { merch: { label: "周边", icon: "👕" }, physical: { label: "实物", icon: "📦" }, lottery: { label: "抽奖", icon: "🎰" } };

export default function RewardsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const { rewards, myPoints, redemptions, rewardsLoading, refreshRewards } = useData();
  const [activeTab, setActiveTab] = useState<"store" | "history">("store");
  const [redeeming, setRedeeming] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);

  if (authLoading || !user) return null;

  async function handleRedeem(reward: typeof rewards[0]) {
    setMsg(null); setRedeeming(reward.id);
    try {
      const res = await fetch("/api/rewards/redeem", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ rewardId: reward.id }) });
      const data = await res.json();
      if (res.ok) { setMsg({ text: `兑换成功 — ${data.redemption.rewardName} · 消耗 ${data.redemption.pointsSpent} 积分`, ok: true }); refreshRewards(); }
      else { setMsg({ text: data.error || "兑换失败", ok: false }); if (data.code === "NEED_ADDRESS") router.push("/dashboard/me"); if (data.code === "NEED_ETH") router.push("/dashboard/me"); }
    } catch { setMsg({ text: "网络错误", ok: false }); }
    setRedeeming(null);
  }

  if (rewardsLoading) return <LoadingScreen />;

  const merch = rewards.filter(r => r.type === "merch" || r.type === "physical");
  const lottery = rewards.filter(r => r.type === "lottery");

  return (
    <div className="min-h-screen">
      <div className="px-5 md:px-8 pt-6 pb-3 flex items-center justify-between flex-wrap gap-3">
        <div><h1 className="text-lg font-semibold tracking-tight text-[#eae4f0]">积分商城</h1><p className="text-sm text-[#7e7594] mt-0.5">我的积分: <span className="text-[#fbbf24] font-semibold">{myPoints}</span></p></div>
        <div className="flex gap-0.5 rounded-lg bg-[rgba(167,139,250,0.03)] border border-[rgba(167,139,250,0.06)] p-1">
          {(["store", "history"] as const).map(k => (<button key={k} onClick={() => setActiveTab(k)} className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${activeTab === k ? "bg-[rgba(167,139,250,0.1)] text-[#eae4f0]" : "text-[#7e7594] hover:text-[#c4bdd4]"}`}>{k === "store" ? "商城" : "兑换记录"}</button>))}
        </div>
      </div>
      <div className="px-5 md:px-8 pb-10 space-y-5">
        {msg && (<div className={`rounded-lg px-4 py-3 text-sm font-medium ${msg.ok ? "bg-[rgba(34,211,160,0.06)] border border-[rgba(34,211,160,0.12)] text-[#22d3a0]" : "bg-[rgba(248,113,113,0.06)] border border-[rgba(248,113,113,0.12)] text-[#f87171]"}`}>{msg.text}</div>)}
        {activeTab === "store" ? (
          <div className="space-y-5">
            {merch.length > 0 && (
              <div>
                <p className="text-xs uppercase tracking-[0.15em] text-[#5c5470] mb-3">实物 & 周边</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {merch.map(r => {
                    const canAfford = myPoints >= r.costPoints; const soldOut = r.stock <= 0;
                    return (
                      <div key={r.id} className="cosmic-card rounded-xl border border-[rgba(167,139,250,0.07)] bg-[rgba(167,139,250,0.015)] p-4 hover-lift">
                        <div className="flex items-start justify-between mb-3"><div><div className="flex items-center gap-2 mb-1"><span className="text-lg">{TYPE_CFG[r.type]?.icon || "🎁"}</span><span className="text-xs text-[#7e7594]">{TYPE_CFG[r.type]?.label}</span></div><p className="text-sm font-semibold text-[#eae4f0]">{r.name}</p></div><span className="text-sm font-bold text-[#fbbf24] tabular-nums">{r.costPoints}</span></div>
                        {r.description && <p className="text-sm text-[#7e7594] mb-3 leading-relaxed">{r.description}</p>}
                        <Button onClick={() => handleRedeem(r)} disabled={!canAfford || soldOut || redeeming === r.id} className={`w-full rounded-md text-sm font-medium py-2 h-auto transition-all ${canAfford && !soldOut ? "bg-[rgba(167,139,250,0.15)] hover:bg-[rgba(167,139,250,0.25)] text-[#c4bdd4] hover:text-[#eae4f0] border border-[rgba(167,139,250,0.15)]" : "bg-[rgba(167,139,250,0.03)] text-[#5c5470] cursor-not-allowed border border-[rgba(167,139,250,0.06)]"}`}>{redeeming === r.id ? "兑换中..." : soldOut ? "已售罄" : canAfford ? "立即兑换" : `还差 ${r.costPoints - myPoints} 分`}</Button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
            {lottery.length > 0 && (
              <div>
                <p className="text-xs uppercase tracking-[0.15em] text-[#5c5470] mb-3">抽奖</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {lottery.map(r => {
                    const canAfford = myPoints >= r.costPoints;
                    return (
                      <div key={r.id} className="rounded-xl border border-[rgba(251,191,36,0.08)] bg-[rgba(251,191,36,0.015)] p-4 dragon-glow hover-lift">
                        <div className="flex items-start justify-between mb-3"><div><div className="flex items-center gap-2 mb-1"><span className="text-lg">🎰</span><span className="text-xs text-[#7e7594]">抽奖</span></div><p className="text-sm font-semibold text-[#eae4f0]">{r.name}</p></div><span className="text-sm font-bold text-[#fbbf24] tabular-nums">{r.costPoints}</span></div>
                        <Button onClick={() => handleRedeem(r)} disabled={!canAfford || redeeming === r.id} className={`w-full rounded-md text-sm font-medium py-2 h-auto transition-all ${canAfford ? "bg-[rgba(251,191,36,0.12)] hover:bg-[rgba(251,191,36,0.2)] text-[#fbbf24] border border-[rgba(251,191,36,0.15)]" : "bg-[rgba(167,139,250,0.03)] text-[#5c5470] cursor-not-allowed border border-[rgba(167,139,250,0.06)]"}`}>{redeeming === r.id ? "抽奖中..." : canAfford ? "🎲 参与抽奖" : `还差 ${r.costPoints - myPoints} 分`}</Button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="cosmic-card rounded-xl border border-[rgba(167,139,250,0.07)] bg-[rgba(167,139,250,0.01)] overflow-hidden">
            {redemptions.length > 0 ? (
              <table className="w-full">
                <thead><tr className="text-xs font-medium uppercase tracking-wider text-[#5c5470] border-b border-[rgba(167,139,250,0.06)]"><th className="text-left py-3 px-5">奖品</th><th className="text-left py-3 px-5">类型</th><th className="text-left py-3 px-5">积分</th><th className="text-left py-3 px-5">状态</th><th className="text-left py-3 px-5">时间</th></tr></thead>
                <tbody className="text-sm">{redemptions.map(r => (<tr key={r.id} className="border-b border-[rgba(167,139,250,0.03)]"><td className="py-2.5 px-5 font-medium text-[#c4bdd4]">{r.rewardName}</td><td className="py-2.5 px-5 text-[#7e7594]">{r.rewardType}</td><td className="py-2.5 px-5 tabular-nums text-[#c4bdd4]">{r.pointsSpent}</td><td className="py-2.5 px-5"><span className={`text-xs font-medium ${r.status === "fulfilled" ? "text-[#22d3a0]" : "text-[#7e7594]"}`}>{r.status === "fulfilled" ? "已发放" : r.status === "pending" ? "处理中" : r.status}</span></td><td className="py-2.5 px-5 text-[#5c5470] text-sm">{new Date(r.createdAt).toLocaleDateString("zh-CN")}</td></tr>))}</tbody>
              </table>
            ) : (<div className="py-16 text-center"><p className="text-3xl mb-2">📭</p><p className="text-sm text-[#5c5470]">暂无兑换记录</p></div>)}
          </div>
        )}
      </div>
    </div>
  );
}
