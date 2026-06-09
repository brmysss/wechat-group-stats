import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

function isAdmin(request: NextRequest) {
  const header = request.headers.get("x-admin-secret");
  return header === process.env.ADMIN_SECRET;
}

// GET: 获取所有群成员（用于邀请码绑定）
export async function GET(request: NextRequest) {
  if (!isAdmin(request)) return NextResponse.json({ error: "未授权" }, { status: 403 });

  const members = await prisma.groupStat.findMany({
    select: {
      senderWxid: true,
      tag: true,
      total: true,
      last_1month: true,
    },
    orderBy: { total: "desc" },
  });

  // 查哪些 wxid 已经绑定了用户
  const wxids = members.map((m) => m.senderWxid);
  const users = await prisma.user.findMany({
    where: { wxid: { in: wxids } },
    select: { wxid: true, username: true, id: true, avatarUrl: true },
  });
  const userByWxid = new Map(users.map((u) => [u.wxid!, u]));

  // 查哪些 wxid 已经有未使用的邀请码
  const pendingCodes = await prisma.inviteCode.findMany({
    where: { isUsed: false, boundWxid: { in: wxids } },
    select: { boundWxid: true, code: true },
  });
  const codeByWxid = new Map(pendingCodes.map((c) => [c.boundWxid!, c]));

  const result = members.map((m) => ({
    wxid: m.senderWxid,
    tag: m.tag || null,
    total: m.total,
    lastMonth: m.last_1month,
    // 已绑定用户
    boundUser: userByWxid.get(m.senderWxid)
      ? { username: userByWxid.get(m.senderWxid)!.username, id: userByWxid.get(m.senderWxid)!.id, avatarUrl: userByWxid.get(m.senderWxid)!.avatarUrl }
      : null,
    // 已有待用邀请码
    pendingCode: codeByWxid.get(m.senderWxid)?.code || null,
  }));

  return NextResponse.json({ members: result });
}
