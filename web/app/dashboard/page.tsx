"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";

interface Member {
  name: string;
  total: number;
  last_1month: number;
  last_3month: number;
  last_6month: number;
  last_seen: string | null;
  tag: string;
}

interface Stats {
  total_messages: number;
  total_speakers: number;
  never_spoken: number;
  members: Member[];
  myWxid: string | null;
}

export default function DashboardPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [stats, setStats] = useState<Stats | null>(null);
  const [search, setSearch] = useState("");
  const [groupId, setGroupId] = useState("");
  const [groups, setGroups] = useState<{ id: string; name: string }[]>([]);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/");
    }
  }, [loading, user, router]);

  useEffect(() => {
    if (!user) return;
    // 获取群列表
    fetch("/api/stats")
      .then((r) => r.json())
      .then((data) => {
        if (data.groups?.length > 0) {
          setGroups(data.groups);
          setGroupId(data.groups[0].id);
        }
      });
  }, [user]);

  useEffect(() => {
    if (!groupId) return;
    fetch(`/api/stats?groupId=${groupId}`)
      .then((r) => r.json())
      .then(setStats);
  }, [groupId]);

  if (loading || !user) return null;

  const filtered = stats?.members.filter((m) =>
    m.name.toLowerCase().includes(search.toLowerCase())
  ) || [];

  const tagColor: Record<string, string> = {
    "🔥超活跃": "bg-red-500",
    "🟢活跃": "bg-green-500",
    "🟡偶尔": "bg-yellow-500",
    "🟠低频": "bg-orange-500",
    "🔴沉水": "bg-zinc-600",
    "💀死号": "bg-zinc-800",
  };

  return (
    <div className="min-h-screen p-4 md:p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">🏠 Dashboard</h1>
        <div className="flex items-center gap-3">
          <span className="text-zinc-400 text-sm">{user.username}</span>
          <Button variant="outline" size="sm" onClick={() => router.push("/dashboard/me")}>
            个人中心
          </Button>
          <Button variant="outline" size="sm" onClick={() => router.push("/admin")}>
            管理
          </Button>
        </div>
      </div>

      {/* Group selector */}
      {groups.length > 0 && (
        <div className="flex gap-2 mb-4">
          {groups.map((g) => (
            <Button
              key={g.id}
              variant={g.id === groupId ? "default" : "outline"}
              size="sm"
              onClick={() => setGroupId(g.id)}
            >
              {g.name}
            </Button>
          ))}
        </div>
      )}

      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <Card>
            <CardHeader className="py-3"><CardTitle className="text-sm text-zinc-400">总消息</CardTitle></CardHeader>
            <CardContent className="py-0"><p className="text-2xl font-bold">{stats.total_messages.toLocaleString()}</p></CardContent>
          </Card>
          <Card>
            <CardHeader className="py-3"><CardTitle className="text-sm text-zinc-400">发言人数</CardTitle></CardHeader>
            <CardContent className="py-0"><p className="text-2xl font-bold">{stats.total_speakers}</p></CardContent>
          </Card>
          <Card>
            <CardHeader className="py-3"><CardTitle className="text-sm text-zinc-400">从未发言</CardTitle></CardHeader>
            <CardContent className="py-0"><p className="text-2xl font-bold text-zinc-500">{stats.never_spoken}</p></CardContent>
          </Card>
          <Card>
            <CardHeader className="py-3"><CardTitle className="text-sm text-zinc-400">活跃率</CardTitle></CardHeader>
            <CardContent className="py-0">
              <p className="text-2xl font-bold">
                {stats.total_speakers > 0
                  ? Math.round((stats.total_speakers / (stats.total_speakers + stats.never_spoken)) * 100)
                  : 0}%
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Search + Leaderboard */}
      <div className="mb-3">
        <Input
          placeholder="搜索成员..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
      </div>

      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-base">成员排行榜</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="h-[600px]">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-zinc-900">
                <tr className="text-zinc-400">
                  <th className="text-left py-2 px-4 w-12">#</th>
                  <th className="text-left py-2 px-4">成员</th>
                  <th className="text-right py-2 px-4">总消息</th>
                  <th className="text-right py-2 px-4 hidden md:table-cell">30天</th>
                  <th className="text-right py-2 px-4">标签</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((m, i) => (
                  <tr
                    key={m.name}
                    className={`border-t border-zinc-800 hover:bg-zinc-800/50 ${
                      m.name === stats?.myWxid ? "bg-blue-900/20" : ""
                    }`}
                  >
                    <td className="py-2 px-4 text-zinc-500">{i + 1}</td>
                    <td className="py-2 px-4 font-medium">
                      {m.name}
                      {m.name === stats?.myWxid && (
                        <span className="ml-1 text-blue-400 text-xs">(我)</span>
                      )}
                    </td>
                    <td className="py-2 px-4 text-right tabular-nums">{m.total.toLocaleString()}</td>
                    <td className="py-2 px-4 text-right tabular-nums hidden md:table-cell">{m.last_1month}</td>
                    <td className="py-2 px-4 text-right">
                      <Badge className={`${tagColor[m.tag] || "bg-zinc-700"} text-xs`}>
                        {m.tag}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}
