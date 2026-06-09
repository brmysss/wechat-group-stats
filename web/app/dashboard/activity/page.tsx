"use client";

import { useMemo, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useData } from "@/lib/data-context";
import { Input } from "@/components/ui/input";
import { MiniBar, PageHeader, LoadingScreen } from "../shared";

const TAG_CFG: Record<string, { dot: string; bar: string }> = {
  "🔥超活跃": { dot: "#f87171", bar: "#f87171" }, "🟢活跃": { dot: "#22d3a0", bar: "#22d3a0" },
  "🟡偶尔": { dot: "#fbbf24", bar: "#fbbf24" }, "🟠低频": { dot: "#818cf8", bar: "#6366f1" },
  "🔴沉水": { dot: "#a78bfa", bar: "#8b5cf6" }, "💀死号": { dot: "#52525b", bar: "#3f3f46" },
};
const TAG_ORDER = ["🔥超活跃", "🟢活跃", "🟡偶尔", "🟠低频", "🔴沉水", "💀死号"];
type SortField = "total" | "last_1month" | "last_3month" | "last_6month" | "name" | "last_seen";

export default function ActivityPage() {
  const { user, loading: authLoading } = useAuth();
  const { stats, loading: dataLoading } = useData();
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<{ field: SortField; asc: boolean }>({ field: "total", asc: false });
  const [filter, setFilter] = useState<"all" | "active" | "inactive">("all");

  const maxTotal = useMemo(() => Math.max(...(stats?.members.map(m => m.total) || [1]), 1), [stats]);
  const participation = stats && stats.total_members > 0 ? ((stats.total_members - stats.never_spoken) / stats.total_members) * 100 : 0;
  const tagBars = useMemo(() => stats ? TAG_ORDER.map(tag => ({ tag, count: stats.tag_distribution[tag] || 0, pct: stats.total_members > 0 ? (stats.tag_distribution[tag] || 0) / stats.total_members * 100 : 0 })) : [], [stats]);
  const maxTagCount = Math.max(...tagBars.map(t => t.count), 1);
  const filtered = useMemo(() => {
    if (!stats) return [];
    let ms = [...stats.members];
    if (filter === "active") ms = ms.filter(m => ["🔥超活跃","🟢活跃","🟡偶尔"].includes(m.tag));
    else if (filter === "inactive") ms = ms.filter(m => ["🟠低频","🔴沉水","💀死号"].includes(m.tag));
    if (search) { const q = search.toLowerCase(); ms = ms.filter(m => m.name.toLowerCase().includes(q)); }
    ms.sort((a, b) => { let va: any = a[sort.field], vb: any = b[sort.field]; if (typeof va === "string") va = va || ""; if (typeof vb === "string") vb = vb || ""; if (va < vb) return sort.asc ? 1 : -1; if (va > vb) return sort.asc ? -1 : 1; return 0; });
    return ms;
  }, [stats, filter, search, sort]);
  const toggleSort = (field: SortField) => setSort(prev => prev.field === field ? { field, asc: !prev.asc } : { field, asc: false });
  const sArrow = (f: SortField) => sort.field === f ? (sort.asc ? " ↑" : " ↓") : "";

  if (authLoading || !user) return null;
  if (dataLoading) return <LoadingScreen />;

  return (
    <div className="min-h-screen">
      <PageHeader title="活跃度" subtitle={stats ? `${stats.total_members} 名成员` : ""} />
      <div className="px-5 md:px-8 pb-10 space-y-4">
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
            {[{ label: "总成员", value: stats.total_members, color: "#eae4f0" },{ label: "总消息", value: stats.total_messages.toLocaleString(), color: "#22d3a0" },{ label: "参与率", value: `${participation.toFixed(0)}%`, color: "#fbbf24" },{ label: "近1月活跃", value: stats.active_1month, color: "#f87171" },{ label: "从未发言", value: stats.never_spoken, color: "#a78bfa" }].map(({ label, value, color }) => (
              <div key={label} className="cosmic-card rounded-lg border border-[rgba(167,139,250,0.06)] bg-[rgba(167,139,250,0.02)] p-3 text-center"><p className="text-xs uppercase tracking-wider text-[#5c5470] mb-1">{label}</p><p className="text-lg font-bold tabular-nums" style={{ color }}>{value}</p></div>
            ))}
          </div>
        )}
        {stats && (
          <div className="cosmic-card rounded-xl border border-[rgba(167,139,250,0.07)] bg-[rgba(167,139,250,0.01)] p-4">
            <p className="text-sm font-medium text-[#eae4f0] mb-3">活跃度分布</p>
            <div className="space-y-1.5">
              {tagBars.map(({ tag, count, pct }) => (
                <div key={tag} className="flex items-center gap-3 text-sm"><span className="w-[75px] text-right text-[#7e7594]">{tag}</span><div className="flex-1 h-5 bg-[rgba(167,139,250,0.04)] rounded-full overflow-hidden"><div className="h-full rounded-full flex items-center justify-end pr-2 bar-grow" style={{ "--bar-width": `${(count / maxTagCount) * 100}%`, backgroundColor: TAG_CFG[tag]?.bar || "#52525b", minWidth: count > 0 ? 20 : 0 } as React.CSSProperties}>{pct > 10 && <span className="text-xs font-medium text-white/90">{count}</span>}</div></div><span className="w-[75px] text-[#5c5470]">{count}人 {pct.toFixed(1)}%</span></div>
              ))}
            </div>
          </div>
        )}
        {stats && (
          <div className="cosmic-card rounded-xl border border-[rgba(167,139,250,0.07)] bg-[rgba(167,139,250,0.01)] overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2 gap-3 flex-wrap border-b border-[rgba(167,139,250,0.06)]">
              <div className="flex gap-0.5">
                {(["all","active","inactive"] as const).map(k => (<button key={k} onClick={() => setFilter(k)} className={`px-2.5 py-1 rounded-md text-sm font-medium transition-all ${filter === k ? "bg-[rgba(167,139,250,0.1)] text-[#eae4f0]" : "text-[#7e7594] hover:text-[#c4bdd4]"}`}>{k === "all" ? "全部" : k === "active" ? "活跃" : "不活跃"}</button>))}
              </div>
              <Input placeholder="搜索..." value={search} onChange={e => setSearch(e.target.value)} className="w-[140px] bg-[rgba(167,139,250,0.04)] border-[rgba(167,139,250,0.1)] text-[#c4bdd4] placeholder:text-[#5c5470] rounded-md h-7 text-sm" />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead><tr className="text-xs font-medium uppercase tracking-wider text-[#5c5470] border-b border-[rgba(167,139,250,0.06)]"><th className="text-left py-2 px-4 w-8">#</th><th className="text-left py-2 px-4 cursor-pointer hover:text-[#c4bdd4]" onClick={() => toggleSort("name")}>昵称{sArrow("name")}</th><th className="text-left py-2 px-4 cursor-pointer hover:text-[#c4bdd4]" onClick={() => toggleSort("total")}>发言{sArrow("total")}</th><th className="text-left py-2 px-4 cursor-pointer hover:text-[#c4bdd4] hidden sm:table-cell" onClick={() => toggleSort("last_1month")}>近1月{sArrow("last_1month")}</th><th className="text-left py-2 px-4 cursor-pointer hover:text-[#c4bdd4] hidden md:table-cell" onClick={() => toggleSort("last_3month")}>近3月{sArrow("last_3month")}</th><th className="text-left py-2 px-4">状态</th></tr></thead>
                <tbody className="text-sm">
                  {filtered.map((m, i) => { const isMe = user.username === m.name; const cfg = TAG_CFG[m.tag]; return (<tr key={m.name} className={`border-b border-[rgba(167,139,250,0.03)] ${isMe ? "bg-[rgba(167,139,250,0.05)]" : "hover:bg-[rgba(167,139,250,0.015)]"}`}><td className="py-1.5 px-4 text-[#5c5470] text-sm">{i + 1}</td><td className="py-1.5 px-4 font-medium whitespace-nowrap">{m.name}{isMe && <span className="ml-1 text-sm text-[#a78bfa]">你</span>}</td><td className="py-1.5 px-4"><div className="flex items-center gap-2 min-w-[70px]"><span className="tabular-nums text-[#c4bdd4]">{m.total.toLocaleString()}</span><MiniBar value={m.total} max={maxTotal} color="#22d3a0" /></div></td><td className="py-1.5 px-4 tabular-nums text-[#c4bdd4] hidden sm:table-cell">{m.last_1month}</td><td className="py-1.5 px-4 tabular-nums text-[#c4bdd4] hidden md:table-cell">{m.last_3month}</td><td className="py-1.5 px-4"><span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-[rgba(167,139,250,0.06)] text-[#7e7594]"><span className="w-1 h-1 rounded-full" style={{ backgroundColor: cfg?.dot }} />{m.tag}</span></td></tr>); })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
