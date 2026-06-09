import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

// 管理员同步群统计数据
export async function POST(request: NextRequest) {
  const secret = request.headers.get("x-admin-secret");
  if (secret !== process.env.ADMIN_SECRET) {
    return NextResponse.json({ error: "未授权" }, { status: 403 });
  }

  const body = await request.json();
  const { groupId, members } = body;

  if (!groupId || !Array.isArray(members)) {
    return NextResponse.json({ error: "缺少 groupId 或 members 数组" }, { status: 400 });
  }

  try {
    // 删除旧数据
    await prisma.$executeRawUnsafe(
      `DELETE FROM "GroupStat" WHERE "groupId" = $1`,
      groupId
    );

    // 批量插入
    let inserted = 0;
    for (const m of members) {
      await prisma.$executeRawUnsafe(
        `INSERT INTO "GroupStat" ("groupId", "senderWxid", "total", "last_1month", "last_3month", "last_6month", "tag", "lastSeen")
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
        groupId,
        m.name,
        m.total,
        m.last_1month || 0,
        m.last_3month || 0,
        m.last_6month || 0,
        m.tag,
        m.last_seen ? new Date(m.last_seen + "T00:00:00.000Z") : null
      );
      inserted++;
    }

    return NextResponse.json({ ok: true, inserted, groupId });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
