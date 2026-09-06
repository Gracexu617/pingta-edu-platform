import { NextResponse } from "next/server";

import { getAiConfigStatus } from "@/app/lib/ai-client";

export async function GET() {
  const ai = getAiConfigStatus();

  return NextResponse.json({
    aiConfigured: ai.configured,
    model: ai.configured ? `${ai.providerName} / ${ai.model}` : ai.model,
  });
}
