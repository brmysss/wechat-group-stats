import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { cookies } from "next/headers";

// PUT /api/me/address — update shipping / EVM address
export async function PUT(request: NextRequest) {
  const cookieStore = await cookies();
  const userId = cookieStore.get("user_id")?.value;
  if (!userId) return NextResponse.json({ error: "请先登录" }, { status: 401 });

  const body = await request.json();
  const updates: Record<string, string> = {};

  if (body.shippingAddress !== undefined) {
    updates.shippingAddress = typeof body.shippingAddress === "string"
      ? body.shippingAddress
      : JSON.stringify(body.shippingAddress);
  }
  if (body.ethAddress !== undefined) {
    // Basic EVM address validation
    const addr = body.ethAddress.trim();
    if (addr && !/^0x[a-fA-F0-9]{40}$/.test(addr)) {
      return NextResponse.json({ error: "无效的 EVM 地址格式" }, { status: 400 });
    }
    updates.ethAddress = addr || null;
  }

  if (Object.keys(updates).length === 0) {
    return NextResponse.json({ error: "无更新内容" }, { status: 400 });
  }

  await prisma.user.update({ where: { id: userId }, data: updates });

  return NextResponse.json({ success: true });
}

// GET /api/me/address
export async function GET() {
  const cookieStore = await cookies();
  const userId = cookieStore.get("user_id")?.value;
  if (!userId) return NextResponse.json({ error: "请先登录" }, { status: 401 });

  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { shippingAddress: true, ethAddress: true },
  });

  return NextResponse.json({
    shippingAddress: user?.shippingAddress ? safeParseJSON(user.shippingAddress) : null,
    ethAddress: user?.ethAddress || null,
  });
}

function safeParseJSON(s: string) {
  try { return JSON.parse(s); } catch { return s; }
}
