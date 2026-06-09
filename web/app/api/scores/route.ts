import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { cookies } from "next/headers";

export async function GET() {
  const cookieStore = await cookies();
  const userId = cookieStore.get("user_id")?.value;
  if (!userId) return NextResponse.json({ error: "请先登录" }, { status: 401 });

  const scoreRows = await prisma.score.findMany({
    include: { user: { select: { id: true, username: true, avatarUrl: true } } },
  });

  const scores = scoreRows.map((s) => ({
    userId: s.userId,
    username: s.user.username,
    avatarUrl: s.user.avatarUrl || null,
    activePoints: s.activePoints,
    sharerPoints: s.sharerPoints,
    researcherPoints: s.researcherPoints,
    collaboratorPoints: s.collaboratorPoints,
    dragonBalls: s.dragonBalls,
    dragonBallReason: s.dragonBallReason || "",
    totalPoints: s.activePoints + s.sharerPoints + s.researcherPoints + s.collaboratorPoints,
    totalEarned: s.totalEarned,
    totalSpent: s.totalSpent,
    availableBalance: s.totalEarned - s.totalSpent,
  }));

  scores.sort((a, b) => b.totalPoints - a.totalPoints);

  return NextResponse.json({
    scores,
    dragonBallCount: scores.filter((s) => s.dragonBalls > 0).length,
  });
}
