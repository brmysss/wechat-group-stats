import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

// POST: 批量同步消息（API Key 认证）
export async function POST(request: NextRequest) {
  const apiKey = request.headers.get("x-api-key");

  if (!apiKey || apiKey !== process.env.SYNC_API_KEY) {
    return NextResponse.json({ error: "未授权" }, { status: 403 });
  }

  const { groupWxId, messages } = await request.json();

  if (!groupWxId || !messages || !Array.isArray(messages)) {
    return NextResponse.json({ error: "参数错误" }, { status: 400 });
  }

  // 确保群组存在
  const group = await prisma.group.upsert({
    where: { wxGroupId: groupWxId },
    update: {},
    create: {
      wxGroupId: groupWxId,
      name: groupWxId, // 默认用 wxid，后续可在后台改名
    },
  });

  let inserted = 0;
  let skipped = 0;

  // 批量插入，跳过重复
  for (const msg of messages) {
    try {
      await prisma.message.create({
        data: {
          groupId: group.id,
          senderWxid: msg.sender_wxid,
          content: msg.content || "",
          sentAt: new Date(msg.sent_at * 1000),
        },
      });
      inserted++;
    } catch (e: any) {
      // 唯一约束冲突 = 重复消息，跳过
      if (e?.code === "P2002") {
        skipped++;
      } else {
        throw e;
      }
    }
  }

  return NextResponse.json({
    ok: true,
    inserted,
    skipped,
    groupId: group.id,
  });
}
