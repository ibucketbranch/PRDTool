import { NextResponse } from "next/server";
import { testConnection } from "@/lib/supabase";

export async function GET() {
  const result = await testConnection();

  if (!result.connected) {
    return NextResponse.json(
      {
        status: "error",
        database: "disconnected",
        error: result.error,
      },
      { status: 503 }
    );
  }

  return NextResponse.json({
    status: "ok",
    database: "connected",
    documentCount: result.documentCount,
  });
}
