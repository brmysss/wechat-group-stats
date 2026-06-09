import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { cookies } from "next/headers";

export async function POST(request: NextRequest) {
  const cookieStore = await cookies();
  const userId = cookieStore.get("user_id")?.value;
  if (!userId) return NextResponse.json({ error: "请先登录" }, { status: 401 });

  const { rewardId } = await request.json();
  if (!rewardId) return NextResponse.json({ error: "缺少 rewardId" }, { status: 400 });

  const reward = await prisma.reward.findUnique({ where: { id: rewardId } });
  if (!reward || reward.type !== "lottery") {
    return NextResponse.json({ error: "无效的抽奖项目" }, { status: 400 });
  }

  const user = await prisma.user.findUnique({ where: { id: userId } });
  if (!user?.ethAddress) {
    return NextResponse.json({ error: "请先在个人中心绑定 EVM 地址", code: "NEED_ETH" }, { status: 400 });
  }

  const score = await prisma.score.findUnique({ where: { userId } });
  const balance = score ? score.totalEarned - score.totalSpent : 0;

  if (balance < reward.costPoints) {
    return NextResponse.json({ error: `积分不足 (需要 ${reward.costPoints}，当前 ${balance})` }, { status: 400 });
  }

  const redemption = await prisma.$transaction(async (tx) => {
    await tx.score.update({ where: { userId }, data: { totalSpent: { increment: reward.costPoints } } });
    return tx.redemption.create({
      data: { userId, rewardId, pointsSpent: reward.costPoints, status: "pending", ethAddress: user.ethAddress },
      include: { reward: true },
    });
  });

  return NextResponse.json({
    success: true,
    message: `已使用 ${reward.costPoints} 积分参与「${reward.name}」抽奖`,
    entry: { id: redemption.id, rewardName: reward.name },
  });
}
