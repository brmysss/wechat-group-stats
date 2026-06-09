import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { cookies } from "next/headers";

// 验证邀请码 + 注册
export async function POST(request: NextRequest) {
  const { code, username } = await request.json();

  if (!code || !username) {
    return NextResponse.json({ error: "邀请码和用户名不能为空" }, { status: 400 });
  }

  if (username.length < 2 || username.length > 20) {
    return NextResponse.json({ error: "用户名需要 2-20 个字符" }, { status: 400 });
  }

  // 查邀请码
  const invite = await prisma.inviteCode.findUnique({ where: { code } });

  if (!invite) {
    return NextResponse.json({ error: "邀请码无效" }, { status: 400 });
  }

  if (invite.isUsed) {
    return NextResponse.json({ error: "邀请码已被使用" }, { status: 400 });
  }

  // 检查用户名是否重复
  const existing = await prisma.user.findUnique({ where: { username } });
  if (existing) {
    return NextResponse.json({ error: "用户名已被占用" }, { status: 400 });
  }

  // 创建用户 + 标记邀请码已用（如果有 boundWxid，自动关联）
  const user = await prisma.user.create({
    data: {
      username,
      inviteCode: code,
      wxid: invite.boundWxid || undefined,
    },
  });

  await prisma.inviteCode.update({
    where: { code },
    data: { isUsed: true, usedBy: user.id },
  });

  // 设置 session cookie
  const cookieStore = await cookies();
  cookieStore.set("user_id", user.id, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 30, // 30 天
    path: "/",
  });

  return NextResponse.json({ ok: true, user: { id: user.id, username: user.username } });
}
