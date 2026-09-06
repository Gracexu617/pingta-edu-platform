import { NextResponse } from "next/server";

type ImportRequest = {
  url?: string;
};

function decodeHtml(text: string) {
  return text
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

function stripHtml(html: string) {
  return decodeHtml(
    html
      .replace(/<script[\s\S]*?<\/script>/gi, " ")
      .replace(/<style[\s\S]*?<\/style>/gi, " ")
      .replace(/<noscript[\s\S]*?<\/noscript>/gi, " ")
      .replace(/<(br|p|div|section|article|h[1-6])\b[^>]*>/gi, "\n")
      .replace(/<[^>]+>/g, " ")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .replace(/[ \t]{2,}/g, " ")
      .trim(),
  );
}

function pickTitle(html: string, url: URL) {
  const ogTitle = html.match(/<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']+)["']/i)?.[1];
  const title = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1];
  return decodeHtml((ogTitle || title || url.hostname).replace(/\s+/g, " ").trim());
}

function pickArticleHtml(html: string) {
  const article = html.match(/<article[\s\S]*?<\/article>/i)?.[0];
  if (article) return article;

  const main = html.match(/<main[\s\S]*?<\/main>/i)?.[0];
  if (main) return main;

  const richText = html.match(/<div[^>]+id=["']js_content["'][\s\S]*?<\/div>/i)?.[0];
  if (richText) return richText;

  const body = html.match(/<body[\s\S]*?<\/body>/i)?.[0];
  return body || html;
}

function sourceFromUrl(url: URL) {
  const host = url.hostname;
  if (host.includes("weixin.qq.com") || host.includes("mp.weixin.qq.com")) return "公众号";
  if (/edu|school|university|college|招生|高校/i.test(host)) return "高校官网";
  return "教育资讯";
}

function tagsFromText(text: string, host: string) {
  const tags = new Set<string>();
  if (/常州|本地|中考|升学|招生|录取/.test(text)) tags.add("常州教育");
  if (/高校|大学|专业|就业|学院/.test(text)) tags.add("高校资料");
  if (/政策|通知|发布|改革/.test(text)) tags.add("政策");
  if (host.includes("weixin.qq.com")) tags.add("公众号");
  return Array.from(tags).slice(0, 5).length ? Array.from(tags).slice(0, 5) : ["待整理"];
}

export async function POST(request: Request) {
  const input = (await request.json()) as ImportRequest;
  if (!input.url) {
    return NextResponse.json({ error: "请先填写链接" }, { status: 400 });
  }

  let target: URL;
  try {
    target = new URL(input.url);
  } catch {
    return NextResponse.json({ error: "链接格式不正确" }, { status: 400 });
  }

  if (!["http:", "https:"].includes(target.protocol)) {
    return NextResponse.json({ error: "只支持 http 或 https 链接" }, { status: 400 });
  }

  try {
    const response = await fetch(target, {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
        Accept: "text/html,application/xhtml+xml",
      },
      redirect: "follow",
    });

    if (!response.ok) {
      return NextResponse.json({ error: `页面读取失败：${response.status}` }, { status: 400 });
    }

    const contentType = response.headers.get("content-type") ?? "";
    if (!contentType.includes("text/html")) {
      return NextResponse.json({ error: "该链接不是普通网页，暂时无法自动提取" }, { status: 400 });
    }

    const html = await response.text();
    const title = pickTitle(html, target);
    const text = stripHtml(pickArticleHtml(html));
    const content = text
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 1)
      .join("\n");

    if (content.length < 80) {
      return NextResponse.json({ error: "正文提取太短，请手动粘贴正文" }, { status: 400 });
    }

    return NextResponse.json({
      title,
      content,
      source: sourceFromUrl(target),
      tags: tagsFromText(content, target.hostname),
      summary: content.length > 80 ? `${content.slice(0, 80)}...` : content,
      mode: "已导入链接，请确认后入库",
    });
  } catch {
    return NextResponse.json({ error: "链接读取失败，请手动粘贴正文" }, { status: 400 });
  }
}
