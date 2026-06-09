import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { cookies } from "next/headers";

// GET /api/redemptions — my redemption history
export async function GET() {
  const cookieStore = await cookies();
  const userId = cookieStore.get("user_id")?.value;
  if (!userId) return NextResponse.json({ error: "请先登录" }, { status: 401 });

  const redemptions = await prisma.redemption.findMany({
    where: { userId },
    include: { reward: { select: { name: true, type: true, imageUrl: true } } },
    orderBy: { createdAt: "desc" },
    take: 50,
  });

  return NextResponse.json({
    redemptions: redemptions.map(r => ({
      id: r.id,
      rewardName: r.reward.name,
      rewardType: r.reward.type,
      pointsSpent: r.pointsSpent,
      status: r.status,
      createdAt: r.createdAt,
    })),
  });
}
