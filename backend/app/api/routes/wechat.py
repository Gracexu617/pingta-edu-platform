"""公众号文章转化 API 路由。

POST /api/v1/wechat/transform   — 提交文章 URL → 返回转化后的凭他教育风格文章
GET  /api/v1/wechat/search      — 按公众号名搜索其文章列表
"""

import re

from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from urllib.parse import quote

from app.services.wechat_transform_service import (
    TransformedArticle,
    WechatArticleRef,
    export_docx,
    export_wechat_html,
    get_cached_article,
    search_account_articles,
    transform_article,
)

router = APIRouter(prefix="/api/v1/wechat", tags=["wechat-transform"])


# ── Request / Response Schemas ──────────────────────────────────────────


class WechatSearchRequest(BaseModel):
    account_name: str = Field(..., description="要搜索的公众号名称", min_length=1)
    limit: int = Field(default=10, ge=1, le=50, description="返回数量上限")


class WechatSearchItem(BaseModel):
    title: str
    url: str
    summary: str = ""
    account_name: str = ""
    published_at: str = ""


class WechatSearchResponse(BaseModel):
    items: list[WechatSearchItem] = []
    total: int = 0


class TransformRequest(BaseModel):
    article_url: str = Field(..., description="微信文章链接", min_length=1)
    account_name: str = Field(default="", description="公众号名称（可选）")


class TransformedImage(BaseModel):
    url: str
    alt_text: str = ""
    has_processed_data: bool = False


class TransformResponse(BaseModel):
    title: str
    body_html: str
    body_text: str
    images: list[TransformedImage] = []
    source_account: str = ""
    source_title: str = ""
    source_url: str = ""
    word_count: int = 0
    transformed_at: str = ""


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/search", response_model=WechatSearchResponse)
async def search_wechat_articles(
    account_name: str,
    limit: int = 10,
) -> WechatSearchResponse:
    """按公众号名搜索其近期文章列表。"""
    if not account_name or not account_name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="account_name 不能为空",
        )

    results = await search_account_articles(account_name.strip(), limit=limit)

    return WechatSearchResponse(
        items=[
            WechatSearchItem(
                title=r.title,
                url=r.url,
                summary=r.summary,
                account_name=r.account_name,
                published_at=r.published_at,
            )
            for r in results
        ],
        total=len(results),
    )


@router.post("/transform", response_model=TransformResponse, status_code=status.HTTP_200_OK)
async def transform_wechat_article(
    payload: TransformRequest,
) -> TransformResponse:
    """提交一篇微信公众号文章 URL，返回转化后的凭他教育风格原创文章。

    流程：抓取全文 → 提炼核心（不抄袭）→ 重写 → 图片/表格加水印 → 输出。
    """
    url = payload.article_url.strip()
    if not url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="article_url 不能为空",
        )

    try:
        article: TransformedArticle = await transform_article(
            article_url=url,
            account_name=payload.account_name.strip(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文章转化失败: {str(e)}",
        ) from e

    if not article.body_text or not article.title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="未能从该文章中提取到有效内容，可能文章需要登录才能查看或已被删除",
        )

    return TransformResponse(
        title=article.title,
        body_html=article.body_html,
        body_text=article.body_text,
        images=[
            TransformedImage(
                url=img.url,
                alt_text=img.alt_text,
                has_processed_data=bool(img.processed_data),
            )
            for img in article.images
        ],
        source_account=article.source_account,
        source_title=article.source_title,
        source_url=article.source_url,
        word_count=article.word_count,
        transformed_at=article.transformed_at.isoformat(),
    )


def _attachment_headers(filename: str, media_type: str) -> dict:
    """构造带中文文件名的 Content-Disposition（RFC 5987）。"""
    ascii_name = re.sub(r"[^\x00-\x7f]", "", filename) or "article"
    return {
        "Content-Type": media_type,
        "Content-Disposition": (
            f"attachment; filename=\"{ascii_name}\"; "
            f"filename*=UTF-8''{quote(filename)}"
        ),
    }


@router.get("/export/docx")
async def export_wechat_docx(
    article_url: str,
    account_name: str = "",
) -> Response:
    """把一篇公众号文章转化后导出为 Word(.docx)。"""
    url = (article_url or "").strip()
    if not url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="article_url 不能为空",
        )
    # 优先用转化时缓存的结果（秒级），避免重复抓取导致下载慢
    article = get_cached_article(url)
    if article is None:
        try:
            article = await transform_article(
                article_url=url, account_name=account_name.strip()
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
            ) from e

    data = export_docx(article)
    headers = _attachment_headers(f"{article.title}.docx",
                                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    return Response(content=data, headers=headers, media_type=headers["Content-Type"])


@router.get("/export/wechat-html")
async def export_wechat_html_endpoint(
    article_url: str,
    account_name: str = "",
) -> Response:
    """把一篇公众号文章转化后导出为「微信公众号格式」HTML 文档。"""
    url = (article_url or "").strip()
    if not url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="article_url 不能为空",
        )
    # 优先用转化时缓存的结果（秒级）
    article = get_cached_article(url)
    if article is None:
        try:
            article = await transform_article(
                article_url=url, account_name=account_name.strip()
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
            ) from e

    html = export_wechat_html(article)
    headers = _attachment_headers(f"{article.title}.html", "text/html; charset=utf-8")
    return Response(content=html.encode("utf-8"), headers=headers, media_type="text/html")
