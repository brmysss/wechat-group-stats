"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { toast } from "sonner";

export default function LoginPage() {
  const { login, loginPassword, user, loading } = useAuth();
  const [mode, setMode] = useState<"invite" | "password">("invite");
  const [code, setCode] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-zinc-400">加载中...</p>
      </div>
    );
  }

  if (user) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>已登录</CardTitle>
            <CardDescription>你好，{user.username}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button className="w-full" onClick={() => (window.location.href = "/dashboard")}>
              进入 Dashboard
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim() || !username.trim()) {
      toast.error("请填写邀请码和用户名");
      return;
    }
    setSubmitting(true);
    try {
      const res = await login(code.trim(), username.trim());
      if (!res.ok) toast.error(res.error || "邀请码无效");
    } catch {
      toast.error("网络错误");
    } finally {
      setSubmitting(false);
    }
  };

  const handlePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      toast.error("请填写用户名和密码");
      return;
    }
    setSubmitting(true);
    try {
      const res = await loginPassword(username.trim(), password.trim());
      if (!res.ok) toast.error(res.error || "用户名或密码错误");
    } catch {
      toast.error("网络错误");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">🚀 前进四社群</CardTitle>
          <CardDescription>
            {mode === "invite" ? "输入邀请码加入" : "管理员登录"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {mode === "invite" ? (
            <form onSubmit={handleInvite} className="space-y-4">
              <div>
                <Input
                  placeholder="邀请码"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  className="text-center text-lg tracking-widest"
                  maxLength={20}
                />
              </div>
              <div>
                <Input
                  placeholder="设置用户名"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  maxLength={20}
                />
              </div>
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? "验证中..." : "加入社群"}
              </Button>
              <p className="text-center">
                <button
                  type="button"
                  onClick={() => setMode("password")}
                  className="text-xs text-[#5c5470] hover:text-[#a78bfa] transition-colors"
                >
                  管理员登录
                </button>
              </p>
            </form>
          ) : (
            <form onSubmit={handlePassword} className="space-y-4">
              <div>
                <Input
                  placeholder="用户名"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>
              <div>
                <Input
                  placeholder="密码"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? "验证中..." : "登录"}
              </Button>
              <p className="text-center">
                <button
                  type="button"
                  onClick={() => setMode("invite")}
                  className="text-xs text-[#5c5470] hover:text-[#a78bfa] transition-colors"
                >
                  邀请码加入
                </button>
              </p>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
