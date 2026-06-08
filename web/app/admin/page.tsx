"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

export default function AdminPage() {
  const router = useRouter();
  const [secret, setSecret] = useState("");
  const [authed, setAuthed] = useState(false);
  const [count, setCount] = useState(5);
  const [codes, setCodes] = useState<{ code: string; id: string }[]>([]);
  const [allCodes, setAllCodes] = useState<any[]>([]);

  const checkAuth = () => {
    setAuthed(true);
  };

  const generateCodes = async () => {
    try {
      const res = await fetch("/api/admin/invite-codes", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-admin-secret": secret,
        },
        body: JSON.stringify({ count }),
      });
      const data = await res.json();
      if (data.codes) {
        setCodes(data.codes);
        toast.success(`生成了 ${data.codes.length} 个邀请码`);
      } else {
        toast.error(data.error || "生成失败");
      }
    } catch {
      toast.error("网络错误");
    }
  };

  const loadCodes = async () => {
    try {
      const res = await fetch("/api/admin/invite-codes", {
        headers: { "x-admin-secret": secret },
      });
      const data = await res.json();
      if (data.codes) {
        setAllCodes(data.codes);
      }
    } catch {
      toast.error("加载失败");
    }
  };

  const copyAll = () => {
    const text = codes.map((c) => c.code).join("\n");
    navigator.clipboard.writeText(text);
    toast.success("已复制到剪贴板");
  };

  if (!authed) {
    return (
      <div className="flex items-center justify-center min-h-screen p-4">
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>管理员登录</CardTitle>
            <CardDescription>输入管理密钥</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              type="password"
              placeholder="ADMIN_SECRET"
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
            />
            <Button className="w-full" onClick={checkAuth}>
              验证
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-4 md:p-6 max-w-2xl mx-auto">
      <Button variant="ghost" className="mb-4" onClick={() => router.push("/dashboard")}>
        ← 返回 Dashboard
      </Button>

      <h1 className="text-2xl font-bold mb-6">⚙️ 管理后台</h1>

      {/* 生成邀请码 */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>生成邀请码</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-3">
            <Input
              type="number"
              value={count}
              onChange={(e) => setCount(parseInt(e.target.value) || 5)}
              min={1}
              max={100}
              className="w-24"
            />
            <Button onClick={generateCodes}>生成</Button>
          </div>

          {codes.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-sm text-zinc-400">新生成的邀请码（一次性，发给成员）：</p>
                <Button variant="outline" size="sm" onClick={copyAll}>
                  一键复制
                </Button>
              </div>
              <div className="bg-zinc-900 rounded-lg p-3 font-mono text-sm space-y-1">
                {codes.map((c) => (
                  <div key={c.id} className="text-green-400">{c.code}</div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 邀请码列表 */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>邀请码使用记录</CardTitle>
          <Button variant="outline" size="sm" onClick={loadCodes}>
            刷新
          </Button>
        </CardHeader>
        <CardContent>
          {allCodes.length === 0 ? (
            <p className="text-zinc-500 text-sm">点击「刷新」查看</p>
          ) : (
            <div className="space-y-2">
              {allCodes.map((c) => (
                <div
                  key={c.id}
                  className="flex items-center justify-between py-2 border-b border-zinc-800 last:border-0"
                >
                  <span className="font-mono">{c.code}</span>
                  <Badge variant={c.isUsed ? "default" : "secondary"}>
                    {c.isUsed ? "已使用" : "未使用"}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
