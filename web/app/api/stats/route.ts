import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { cookies } from "next/headers";

export async function GET(request: NextRequest) {
  const cookieStore = await cookies();
  const userId = cookieStore.get("user_id")?.value;
  if (!userId) {
    return NextResponse.json({ error: "请先登录" }, { status: 401 });
  }

  const { searchParams } = new URL(request.url);
  const groupId = searchParams.get("groupId");

  if (!groupId) {
    const groups = await prisma.group.findMany({
      select: { id: true, wxGroupId: true, name: true },
    });
    return NextResponse.json({ groups });
  }

  // 从 group_stats 读预聚合数据
  const rows = await prisma.groupStat.findMany({
    where: { groupId },
    orderBy: { total: "desc" },
  });

  const members = rows.map((r) => ({
    name: r.senderWxid,
    total: r.total,
    last_1month: r.last_1month,
    last_3month: r.last_3month,
    last_6month: r.last_6month,
    last_seen: r.lastSeen?.toISOString() || null,
    tag: r.tag,
  }));

  const totalSpeakers = members.filter((m) => m.total > 0).length;
  const neverSpoken = members.filter((m) => m.total === 0).length;
  const totalMessages = members.reduce((s, m) => s + m.total, 0);
  const totalMembers = members.length;

  // 近1月活跃：last_1month > 0
  const active1month = members.filter((m) => m.last_1month > 0).length;

  // 标签分布
  const tagDistribution = members.reduce<Record<string, number>>((acc, m) => {
    acc[m.tag] = (acc[m.tag] || 0) + 1;
    return acc;
  }, {});

  const user = await prisma.user.findUnique({ where: { id: userId } });

  return NextResponse.json({
    total_messages: totalMessages,
    total_speakers: totalSpeakers,
    total_members: totalMembers,
    never_spoken: neverSpoken,
    active_1month: active1month,
    tag_distribution: tagDistribution,
    members,
    myWxid: user?.wxid || null,
  });
}
