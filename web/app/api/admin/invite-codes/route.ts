import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { randomBytes } from "crypto";

function isAdmin(request: NextRequest) {
  const header = request.headers.get("x-admin-secret");
  return header === process.env.ADMIN_SECRET;
}

// GET: 查看所有邀请码
export async function GET(request: NextRequest) {
  if (!isAdmin(request)) return NextResponse.json({ error: "未授权" }, { status: 403 });
  const codes = await prisma.inviteCode.findMany({ orderBy: { createdAt: "desc" } });
  return NextResponse.json({ codes });
}

// POST: 批量生成邀请码（可选绑定群成员）
export async function POST(request: NextRequest) {
  if (!isAdmin(request)) return NextResponse.json({ error: "未授权" }, { status: 403 });

  const { count = 5, boundWxid } = await request.json();
  const n = Math.min(Math.max(1, count), 100);

  const codes = [];
  for (let i = 0; i < n; i++) {
    codes.push({
      code: randomBytes(4).toString("hex"),
      createdBy: "admin",
      boundWxid: boundWxid || null,
    });
  }

  await prisma.inviteCode.createMany({ data: codes });
  const allCodes = await prisma.inviteCode.findMany({
    where: { code: { in: codes.map((c) => c.code) } },
    select: { code: true, id: true, boundWxid: true },
  });

  return NextResponse.json({ codes: allCodes });
}
