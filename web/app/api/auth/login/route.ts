import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { cookies } from "next/headers";
import { createHash } from "crypto";

function hashPassword(password: string): string {
  return createHash("sha256").update(password).digest("hex");
}

export async function POST(req: NextRequest) {
  const { username, password } = await req.json();

  if (!username || !password) {
    return NextResponse.json({ ok: false, error: "请填写用户名和密码" }, { status: 400 });
  }

  const hash = hashPassword(password);

  const user = await prisma.user.findFirst({
    where: { username, passwordHash: hash },
    select: { id: true, username: true, wxid: true, avatarUrl: true, createdAt: true },
  });

  if (!user) {
    return NextResponse.json({ ok: false, error: "用户名或密码错误" }, { status: 401 });
  }

  const cookieStore = await cookies();
  cookieStore.set("user_id", user.id, {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });

  return NextResponse.json({ ok: true, user });
}
