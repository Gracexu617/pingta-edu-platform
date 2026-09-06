from app.services.content_fetcher import parse_feed, parse_html


def test_parse_html_extracts_title_and_text() -> None:
    result = parse_html(
        "<html><head><title>测试标题</title><script>x</script></head>"
        "<body><h1>正文标题</h1><p>第一段内容</p></body></html>",
        "fallback",
    )

    assert result.title == "测试标题"
    assert "正文标题" in result.content
    assert "第一段内容" in result.content
    assert "x" not in result.content
    assert result.tags == ["网页采集"]


def test_parse_feed_extracts_items() -> None:
    result = parse_feed(
        """
        <rss><channel>
          <item><title>第一条</title><description>第一条摘要</description></item>
          <item><title>第二条</title><description>第二条摘要</description></item>
        </channel></rss>
        """,
        "fallback",
    )

    assert result.title == "RSS更新：第一条"
    assert "第一条摘要" in result.content
    assert "第二条" in result.content
    assert result.tags == ["RSS", "自动采集"]
