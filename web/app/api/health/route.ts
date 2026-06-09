import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function GET() {
  try {
    await prisma.$queryRaw`SELECT 1`;
    return NextResponse.json({ db: "ok" });
  } catch (e: any) {
    return NextResponse.json({ db: "error", message: e.message?.substring(0, 200) });
  }
}
