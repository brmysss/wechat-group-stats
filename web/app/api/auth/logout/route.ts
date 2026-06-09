import { NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function POST() {
  const cookieStore = await cookies();
  cookieStore.set("user_id", "", { httpOnly: true, secure: true, sameSite: "lax", maxAge: 0, path: "/" });
  return NextResponse.json({ ok: true });
}
