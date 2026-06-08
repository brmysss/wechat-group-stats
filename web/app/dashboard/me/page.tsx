"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

interface MemberStats {
  name: string;
  total: number;
  last_1month: number;
  last_3month: number;
  last_6month: number;
  last_seen: string | null;
  tag: string;
}

export default function MePage() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const [myStats, setMyStats] = useState<MemberStats | null>(null);
  const [notBound, setNotBound] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.push("/");
  }, [loading, user, router]);

  useEffect(() => {
    if (!user) return;
    // 先获取群，再查统计
    fetch("/api/stats")
      .then((r) => r.json())
      .then(async (data) => {
        if (data.groups?.length > 0) {
          const res = await fetch(`/api/stats?groupId=${data.groups[0].id}`);
          const stats = await res.json();
          if (stats.myWxid) {
            const me = stats.members.find((m: MemberStats) => m.name === stats.myWxid);
            setMyStats(me || null);
          } else {
            setNotBound(true);
          }
        }
      });
  }, [user]);

  if (loading || !user) return null;

  const tagColor: Record<string, string> = {
    "🔥超活跃": "bg-red-500",
    "🟢活跃": "bg-green-500",
    "🟡偶尔": "bg-yellow-500",
    "🟠低频": "bg-orange-500",
    "🔴沉水": "bg-zinc-600",
    "💀死号": "bg-zinc-800",
  };

  return (
    <div className="min-h-screen p-4 md:p-6 max-w-lg mx-auto">
      <Button variant="ghost" className="mb-4" onClick={() => router.push("/dashboard")}>
        ← 返回 Dashboard
      </Button>

      <h1 className="text-2xl font-bold mb-6">👤 个人中心</h1>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="text-lg">账号信息</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex justify-between">
            <span className="text-zinc-400">用户名</span>
            <span>{user.username}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-zinc-400">绑定微信号</span>
            <span>{user.wxid || (notBound ? "未绑定" : "...")}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-zinc-400">加入时间</span>
            <span>{new Date(user.createdAt).toLocaleDateString("zh-CN")}</span>
          </div>
        </CardContent>
      </Card>

      {myStats ? (
        <Card className="mb-4">
          <CardHeader>
            <CardTitle className="text-lg">我的发言统计</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <p className="text-zinc-400 text-sm">总消息</p>
                <p className="text-2xl font-bold">{myStats.total.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-zinc-400 text-sm">近30天</p>
                <p className="text-2xl font-bold">{myStats.last_1month}</p>
              </div>
              <div>
                <p className="text-zinc-400 text-sm">近90天</p>
                <p className="text-2xl font-bold">{myStats.last_3month}</p>
              </div>
              <div>
                <p className="text-zinc-400 text-sm">近180天</p>
                <p className="text-2xl font-bold">{myStats.last_6month}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge className={`${tagColor[myStats.tag] || "bg-zinc-700"}`}>
                {myStats.tag}
              </Badge>
              <span className="text-zinc-400 text-sm">
                最后发言: {myStats.last_seen
                  ? new Date(myStats.last_seen).toLocaleDateString("zh-CN")
                  : "从未"}
              </span>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card className="mb-4">
          <CardContent className="py-8 text-center text-zinc-400">
            {notBound
              ? "你的微信账号尚未在后台绑定，请联系管理员"
              : "加载中..."}
          </CardContent>
        </Card>
      )}

      <Card className="mb-4 border-blue-900/50 bg-blue-950/20">
        <CardHeader>
          <CardTitle className="text-lg">我的积分</CardTitle>
        </CardHeader>
        <CardContent className="py-4 text-center">
          <p className="text-zinc-500 text-sm">Phase 2 即将上线</p>
          <p className="text-zinc-600 text-xs mt-1">
            AI 消息评分 · 双周结算 · 龙珠奖励
          </p>
        </CardContent>
      </Card>

      <Separator className="my-4" />

      <Button variant="outline" className="w-full" onClick={logout}>
        退出登录
      </Button>
    </div>
  );
}
