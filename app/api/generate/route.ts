import { NextResponse } from "next/server";

import { generateAiText } from "@/app/lib/ai-client";

type GenerateRequest = {
  type?: string;
  topic?: string;
  material?: {
    title?: string;
    summary?: string;
    content?: string;
    tags?: string[];
  };
};

function localDraft(input: GenerateRequest) {
  const type = input.type ?? "公众号文章";
  const topic = input.topic?.trim() || "基于资料库的新选题";
  const material = input.material;
  const reference = material?.summary || material?.content || "请先补充资料。";

  if (type === "视频号脚本") {
    return `选题：${topic}
开场：用一个家长最容易忽略的问题切入。
口播：
第一，先讲这个问题为什么重要。
第二，结合本地教育场景讲清判断方法。
第三，给出一个今天就能做的动作。
分镜：人物口播、资料截图、重点字幕、结尾引导。
参考资料：${reference}`;
  }

  return `选题：${topic}
标题建议：
1. ${topic}，家长真正要看懂的是这几点
2. 关于${topic}，别只看表面信息
3. ${topic}背后的选择逻辑

正文结构：
一、先说明问题为什么值得关注。
二、结合资料库事实拆解背景。
三、分析对家长、学生或学校选择的影响。
四、给出可执行建议。

参考资料：${reference}`;
}

export async function POST(request: Request) {
  const input = (await request.json()) as GenerateRequest;
  const aiResult = await generateAiText(
    `你是教育内容中台的写作助理。请基于资料生成${input.type ?? "公众号文章"}草稿。

选题：${input.topic ?? "基于资料库的新选题"}
参考资料标题：${input.material?.title ?? "无"}
参考资料摘要：${input.material?.summary ?? "无"}
参考资料正文：${input.material?.content ?? "无"}

要求：
- 不编造事实。
- 明确列出需要人工核实的信息。
- 输出中文。
- 结构清晰，适合进入人工审核。`,
  ).catch(() => null);

  if (!aiResult) {
    return NextResponse.json({
      body: localDraft(input),
      mode: "本地模板模式：配置 DOUBAO_API_KEY 和 DOUBAO_MODEL 后启用豆包生成",
    });
  }

  return NextResponse.json({
    body: aiResult.text || localDraft(input),
    mode: `${aiResult.providerName} 生成模式：${aiResult.model}`,
  });
}
