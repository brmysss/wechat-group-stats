import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { cookies } from "next/headers";

export async function GET(request: NextRequest) {
  // 需要登录
  const cookieStore = await cookies();
  const userId = cookieStore.get("user_id")?.value;
  if (!userId) {
    return NextResponse.json({ error: "请先登录" }, { status: 401 });
  }

  const { searchParams } = new URL(request.url);
  const groupId = searchParams.get("groupId");

  if (!groupId) {
    // 返回所有群
    const groups = await prisma.group.findMany({
      select: { id: true, wxGroupId: true, name: true },
    });
    return NextResponse.json({ groups });
  }

  // 按发送者统计
  const messages = await prisma.message.findMany({
    where: { groupId },
    select: { senderWxid: true, sentAt: true },
    orderBy: { sentAt: "desc" },
  });

  const now = new Date();
  const oneMonthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
  const threeMonthsAgo = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000);
  const sixMonthsAgo = new Date(now.getTime() - 180 * 24 * 60 * 60 * 1000);

  // 按发送者聚合
  const stats = new Map<string, {
    total: number;
    last_1month: number;
    last_3month: number;
    last_6month: number;
    last_seen: Date | null;
  }>();

  for (const m of messages) {
    const s = stats.get(m.senderWxid) || {
      total: 0,
      last_1month: 0,
      last_3month: 0,
      last_6month: 0,
      last_seen: null,
    };

    s.total++;
    if (m.sentAt >= oneMonthAgo) s.last_1month++;
    if (m.sentAt >= threeMonthsAgo) s.last_3month++;
    if (m.sentAt >= sixMonthsAgo) s.last_6month++;
    if (!s.last_seen || m.sentAt > s.last_seen) s.last_seen = m.sentAt;

    stats.set(m.senderWxid, s);
  }

  // 算标签
  const members = Array.from(stats.entries()).map(([wxid, s]) => {
    let tag = "💀死号";
    if (s.total > 0 && s.last_6month === 0) tag = "🔴沉水";
    else if (s.last_6month > 0 && s.last_3month === 0) tag = "🟠低频";
    else if (s.last_3month >= 5 && s.last_1month === 0) tag = "🟡偶尔";
    else if (s.last_1month >= 5 && s.last_1month < 20) tag = "🟢活跃";
    else if (s.last_1month >= 20) tag = "🔥超活跃";

    return {
      name: wxid,
      ...s,
      last_seen: s.last_seen?.toISOString() || null,
      tag,
    };
  });

  // 按总消息降序
  members.sort((a, b) => b.total - a.total);

  // 找当前用户是否已绑定 wxid
  const user = await prisma.user.findUnique({ where: { id: userId } });

  return NextResponse.json({
    total_messages: messages.length,
    total_speakers: members.filter((m) => m.total > 0).length,
    never_spoken: members.filter((m) => m.total === 0).length,
    members,
    myWxid: user?.wxid || null,
  });
}
