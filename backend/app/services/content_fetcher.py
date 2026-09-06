from dataclasses import dataclass
from html.parser import HTMLParser
from xml.etree import ElementTree

import httpx


class ContentFetchError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FetchedContent:
    title: str
    content: str
    tags: list[str]


class _HtmlTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self.title = f"{self.title} {text}".strip()
        elif not self._skip_depth:
            self._parts.append(text)

    def content(self) -> str:
        return "\n".join(self._parts)


def parse_html(text: str, fallback_title: str) -> FetchedContent:
    parser = _HtmlTextParser()
    parser.feed(text)
    content = parser.content()
    if not content:
        raise ContentFetchError("No readable page text found")
    return FetchedContent(
        title=parser.title or fallback_title,
        content=content[:12000],
        tags=["网页采集"],
    )


def parse_feed(text: str, fallback_title: str) -> FetchedContent:
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise ContentFetchError("Invalid feed XML") from exc

    def local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    items = [node for node in root.iter() if local_name(node.tag) in {"item", "entry"}]
    if not items:
        raise ContentFetchError("No feed items found")

    parts: list[str] = []
    title = fallback_title
    for item in items[:5]:
        fields: dict[str, str] = {}
        for child in item:
            if child.text:
                fields[local_name(child.tag)] = " ".join(child.text.split())
        item_title = fields.get("title", "未命名条目")
        title = title if title != fallback_title else item_title
        parts.append(f"{item_title}\n{fields.get('description') or fields.get('summary') or ''}")

    return FetchedContent(
        title=f"RSS更新：{title}",
        content="\n\n".join(parts)[:12000],
        tags=["RSS", "自动采集"],
    )


class HttpxContentFetcher:
    async def fetch(self, url: str, fallback_title: str) -> FetchedContent:
        try:
            async with httpx.AsyncClient(
                timeout=20,
                follow_redirects=True,
                headers={"User-Agent": "AI-Education-Intel/0.1"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ContentFetchError(f"Fetch failed: {exc}") from exc

        content_type = response.headers.get("content-type", "")
        body = response.text
        if "xml" in content_type or body.lstrip().startswith("<?xml"):
            return parse_feed(body, fallback_title)
        return parse_html(body, fallback_title)
