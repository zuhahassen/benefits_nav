import { NextResponse } from "next/server";
import benefitsData from "@/public/benefits.json";

export async function GET() {
  return NextResponse.json(benefitsData);
}
