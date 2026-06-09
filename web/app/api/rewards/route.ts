import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { cookies } from "next/headers";

// GET /api/rewards — list rewards + user balance
export async function GET() {
  const cookieStore = await cookies();
  const userId = cookieStore.get("user_id")?.value;
  if (!userId) return NextResponse.json({ error: "请先登录" }, { status: 401 });

  const rewards = await prisma.reward.findMany({
    where: { isActive: true },
    orderBy: { costPoints: "asc" },
  });

  const score = await prisma.score.findUnique({ where: { userId } });
  const balance = score ? score.totalEarned - score.totalSpent : 0;

  return NextResponse.json({ rewards, myPoints: balance });
}
