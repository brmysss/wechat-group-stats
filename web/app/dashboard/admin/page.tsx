"use client";

import { useState, useEffect, useCallback } from "react";
import { PageHeader } from "@/app/dashboard/shared";
import { Shield, Copy, Check, Users, Search, X, UserCheck, Send } from "lucide-react";

interface Member {
  wxid: string;
  tag: string | null;
  total: number;
  lastMonth: number;
  boundUser: { username: string; id: string; avatarUrl: string | null } | null;
  pendingCode: string | null;
  avatarUrl: string | null;
}

export default function AdminPage() {
  const [secret, setSecret] = useState<string>("");
  const [authed, setAuthed] = useState(false);
  const [members, setMembers] = useState<Member[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState<string | null>(null);
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [newCodes, setNewCodes] = useState<Map<string, string>>(new Map());
  const [error, setError] = useState("");

  // sessionStorage 缓存密码
  useEffect(() => {
    const saved = sessionStorage.getItem("admin_secret");
    if (saved) {
      setSecret(saved);
      setAuthed(true);
    }
  }, []);

  const headers = useCallback(() => ({ "x-admin-secret": secret, "Content-Type": "application/json" }), [secret]);

  // 验证密码 & 拉取成员
  const doLogin = async () => {
    setError("");
    setLoading(true);
    try {
      const res = await fetch("/api/admin/members", { headers: { "x-admin-secret": secret } });
      if (res.status === 403) {
        setError("密码错误");
        setLoading(false);
        return;
      }
      const data = await res.json();
      sessionStorage.setItem("admin_secret", secret);
      setAuthed(true);
      setMembers(data.members);
    } catch {
      setError("网络错误");
    }
    setLoading(false);
  };

  const loadMembers = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/admin/members", { headers: headers() });
      const data = await res.json();
      setMembers(data.members);
      setNewCodes(new Map());
    } catch {}
    setLoading(false);
  };

  useEffect(() => {
    if (authed) loadMembers();
  }, [authed]);

  // 为指定成员生成邀请码
  const generateCode = async (wxid: string) => {
    setGenerating(wxid);
    try {
      const res = await fetch("/api/admin/invite-codes", {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ count: 1, boundWxid: wxid }),
      });
      const data = await res.json();
      if (data.codes?.[0]) {
        setNewCodes((prev) => new Map(prev).set(wxid, data.codes[0].code));
        // 同步更新 members 中的 pendingCode
        setMembers((prev) =>
          prev.map((m) => (m.wxid === wxid ? { ...m, pendingCode: data.codes[0].code } : m))
        );
      }
    } catch {}
    setGenerating(null);
  };

  const copyToClipboard = async (code: string) => {
    await navigator.clipboard.writeText(code);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  // 登录界面
  if (!authed) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="w-full max-w-sm">
          <div className="cosmic-card rounded-2xl border border-[rgba(167,139,250,0.08)] bg-[#0b0810] p-8">
            <div className="flex items-center justify-center gap-2 mb-6">
              <Shield className="w-5 h-5 text-[#a78bfa]" />
              <h1 className="text-lg font-semibold text-[#eae4f0]">管理后台</h1>
            </div>
            <input
              type="password"
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && doLogin()}
              placeholder="输入管理员密码"
              className="w-full px-3 py-2 rounded-lg bg-[rgba(167,139,250,0.04)] border border-[rgba(167,139,250,0.1)] text-sm text-[#eae4f0] placeholder-[#5c5470] focus:outline-none focus:border-[rgba(167,139,250,0.3)] mb-3"
            />
            {error && <p className="text-xs text-red-400 mb-3">{error}</p>}
            <button
              onClick={doLogin}
              disabled={!secret || loading}
              className="w-full py-2 rounded-lg bg-gradient-to-r from-violet-500 to-purple-600 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40 transition-opacity"
            >
              {loading ? "验证中..." : "进入"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 过滤
  const filtered = members.filter((m) => {
    const q = search.toLowerCase();
    return m.tag?.toLowerCase().includes(q) || m.wxid.toLowerCase().includes(q);
  });

  const uniqueTag = (wxid: string, tag: string | null) => {
    if (!tag) return wxid.slice(-6);
    // 检查这个 tag 是否唯一
    const sameTag = members.filter((m) => m.tag === tag);
    if (sameTag.length > 1) return `${tag}(${wxid.slice(-4)})`;
    return tag;
  };

  return (
    <div className="max-w-4xl mx-auto px-5 md:px-8 pb-12">
      <PageHeader
        title="发邀请码"
        subtitle={`${members.length} 位群成员 · 点击生成绑定邀请码`}
        right={
          <button
            onClick={loadMembers}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[rgba(167,139,250,0.1)] text-xs text-[#7e7594] hover:text-[#c4bdd4] hover:border-[rgba(167,139,250,0.2)] transition-colors"
          >
            <Users className="w-3 h-3" /> 刷新
          </button>
        }
      />

      {/* 搜索 */}
      <div className="px-5 md:px-8 pb-3">
        <div className="relative max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#5c5470]" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索成员..."
            className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-[rgba(167,139,250,0.04)] border border-[rgba(167,139,250,0.06)] text-sm text-[#eae4f0] placeholder-[#5c5470] focus:outline-none focus:border-[rgba(167,139,250,0.2)]"
          />
          {search && (
            <button onClick={() => setSearch("")} className="absolute right-2 top-1/2 -translate-y-1/2 text-[#5c5470] hover:text-[#7e7594]">
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      {/* 成员列表 */}
      <div className="px-5 md:px-8 space-y-1">
        {loading ? (
          <div className="text-center py-20 text-sm text-[#5c5470]">加载中...</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-20 text-sm text-[#5c5470]">没有匹配的成员</div>
        ) : (
          filtered.map((m) => {
            const code = newCodes.get(m.wxid) || m.pendingCode;
            return (
              <div
                key={m.wxid}
                className="cosmic-card rounded-lg border border-[rgba(167,139,250,0.05)] bg-[rgba(167,139,250,0.01)] px-4 py-2.5 flex items-center gap-3 hover:border-[rgba(167,139,250,0.1)] transition-colors"
              >
                {/* 头像 */}
                <div className="w-8 h-8 rounded-full shrink-0 overflow-hidden">
                  {m.boundUser?.avatarUrl ? (
                    <img src={m.boundUser.avatarUrl} alt="" className="w-8 h-8 rounded-full object-cover" />
                  ) : (
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-400 via-purple-500 to-fuchsia-600 flex items-center justify-center text-xs font-bold text-white">
                      {(m.tag || m.wxid.slice(-2)).slice(0, 2)}
                    </div>
                  )}
                </div>

                {/* 信息 */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-[#eae4f0] truncate">
                      {uniqueTag(m.wxid, m.tag)}
                    </span>
                    {m.boundUser && (
                      <span className="text-xs text-[#34d399] bg-[rgba(52,211,153,0.08)] px-1.5 py-0.5 rounded flex items-center gap-1 shrink-0">
                        <UserCheck className="w-2.5 h-2.5" /> 已绑定
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-[#5c5470] mt-0.5">
                    <span>{m.total} 条消息</span>
                    <span>近月 {m.lastMonth}</span>
                    <span className="font-mono text-[#3d3754]">{m.wxid.slice(-8)}</span>
                  </div>
                </div>

                {/* 操作区 */}
                <div className="shrink-0">
                  {code ? (
                    <div className="flex items-center gap-1.5">
                      <code className="text-xs font-mono bg-[rgba(167,139,250,0.08)] text-[#a78bfa] px-2 py-1 rounded border border-[rgba(167,139,250,0.12)] select-all">
                        {code}
                      </code>
                      <button
                        onClick={() => copyToClipboard(code)}
                        className="p-1 rounded hover:bg-[rgba(167,139,250,0.06)] transition-colors"
                        title="复制"
                      >
                        {copiedCode === code ? (
                          <Check className="w-3.5 h-3.5 text-[#34d399]" />
                        ) : (
                          <Copy className="w-3.5 h-3.5 text-[#5c5470]" />
                        )}
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => generateCode(m.wxid)}
                      disabled={generating === m.wxid}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-gradient-to-r from-violet-500/80 to-purple-600/80 text-xs font-medium text-white hover:from-violet-500 hover:to-purple-600 disabled:opacity-40 transition-all"
                    >
                      <Send className="w-3 h-3" />
                      {generating === m.wxid ? "生成中..." : "发码"}
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
