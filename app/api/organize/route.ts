import { NextResponse } from "next/server";

import { generateAiText } from "@/app/lib/ai-client";

type OrganizeRequest = {
  material?: {
    title?: string;
    source?: string;
    tags?: string[];
    summary?: string;
    content?: string;
  };
};

function localOrganize(input: OrganizeRequest) {
  const material = input.material;
  const content = material?.content?.trim() || material?.summary || "";
  const summary = content.length > 80 ? `${content.slice(0, 80)}...` : content || "待补充资料摘要。";
  const tags = new Set((material?.tags ?? []).filter((tag) => tag && tag !== "待标注"));

  if (/常州|本地|中考|升学|招生|录取/.test(content)) tags.add("常州教育");
  if (/高校|大学|专业|就业|录取/.test(content)) tags.add("高校资料");
  if (/视频|口播|脚本|分镜/.test(content)) tags.add("视频号");
  if (/风格|观点|大V|表达/.test(content)) tags.add("风格蒸馏");

  return {
    summary,
    tags: Array.from(tags).slice(0, 5).length ? Array.from(tags).slice(0, 5) : ["资料卡"],
  };
}

function parseJsonText(text: string) {
  const match = text.match(/\{[\s\S]*\}/);
  if (!match) return null;
  try {
    return JSON.parse(match[0]) as { summary?: string; tags?: string[] };
  } catch {
    return null;
  }
}

export async function POST(request: Request) {
  const input = (await request.json()) as OrganizeRequest;
  const fallback = localOrganize(input);

  const aiResult = await generateAiText(
    `你是教育内容中台的资料整理助理。请把资料整理成 JSON。

标题：${input.material?.title ?? "无"}
来源：${input.material?.source ?? "无"}
原标签：${input.material?.tags?.join("，") ?? "无"}
正文：${input.material?.content ?? "无"}

只输出 JSON：
{
  "summary": "80字以内的具体摘要",
  "tags": ["标签1", "标签2", "标签3"]
}

规则：
- 不编造资料中没有的事实。
- 标签最多 5 个。
- 优先使用稳定标签：常州教育、中考、高校资料、视频号、风格蒸馏、政策、招生、资料卡。`,
  ).catch(() => null);

  if (!aiResult) {
    return NextResponse.json({
      ...fallback,
      mode: "本地整理模式：配置 DOUBAO_API_KEY 和 DOUBAO_MODEL 后启用豆包整理",
    });
  }

  const parsed = parseJsonText(aiResult.text);

  if (!parsed?.summary || !parsed.tags?.length) {
    return NextResponse.json({ ...fallback, error: "AI 整理结果不可用，已使用本地规则" });
  }

  return NextResponse.json({
    summary: parsed.summary,
    tags: parsed.tags.slice(0, 5),
    mode: `${aiResult.providerName} 整理模式：${aiResult.model}`,
  });
}
