"""
凭他教育 · 知识数据卡片生成器

把结构化表格数据渲染为「凭他教育」品牌风格的竖版知识卡片（HTML）。
样式逆向自 2026-08 凭他生涯公众号真实发文（南京师范大学2026综评常州录取等）。

用法：
    from app.services.knowledge_card import KnowledgeCard, CardTable, CardStat

    card = KnowledgeCard(
        title="南京师范大学",
        subtitle="2026综评常州录取",
        stats=[
            CardStat(label="常州录取人数", value="12", unit="人"),
            CardStat(label="涉及高中", value="8", unit="所"),
            CardStat(label="涉及专业", value="8", unit="个"),
        ],
        table=CardTable(
            title="常州录取名单",
            headers=["序号", "姓名（脱敏）", "毕业高中", "录取专业"],
            rows=[...],
        ),
    )
    html = card.render_html()       # 完整独立 HTML
    frag = card.render_fragment()   # 可嵌入公众号的片段
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional


# ── 色值（从样例卡片提取）─────────────────────────────────────────────
C_CREAM_BG = "#FAF6ED"          # 卡片底色（米色/宣纸色）
C_NAVY = "#1B2A4A"              # 主色深蓝（标题、表头、页脚）
C_GOLD = "#C9A96E"              # 金色（副标题、数字、装饰）
C_GOLD_DARK = "#A68B4B"         # 深金（边框）
C_TABLE_HEADER_BG = "#1B2A4A"   # 表头背景（深蓝）
C_ROW_EVEN = "#FFFFFF"          # 偶数行白
C_ROW_ODD = "#F8F3E8"           # 奇数行浅米
C_TEXT_DARK = "#2C2C2C"         # 正文深色
C_TEXT_MUTED = "#666666"        # 辅助文字灰
C_WATERMARK = "rgba(26, 42, 74, 0.04)"  # 水印色

CARD_WIDTH = "560px"             # 公众号适配宽度
FONT_SERIF = '"Source Han Serif SC", "Noto Serif CJK SC", "STSong", "SimSun", serif'
FONT_SANS = '-apple-system, "PingFang SC", "Microsoft YaHei", "Hiragino Sans GB", sans-serif'


@dataclass
class CardStat:
    """顶部统计项。"""
    label: str
    value: str
    unit: str = ""
    icon: str = ""  # SVG icon name or emoji; empty = auto by index


@dataclass
class CardTableRow:
    """表格行，支持多行单元格（用 \\n 分隔）。"""
    cells: List[str]


@dataclass
class CardTable:
    """数据表格区域。"""
    title: str                          # 如 "常州录取名单"
    headers: List[str]                  # 列名
    rows: List[List[str]]               # 二维文本数组；含 \\n 的 cell 会拆成多行
    col_widths: Optional[List[str]] = None  # 如 ["50px","auto","180px","200px"]


@dataclass
class KnowledgeCard:
    """一张完整的凭他教育知识数据卡片。"""

    title: str = ""                     # 主标题（如校名/主题）
    subtitle: str = ""                  # 副标题（如年份+事件）
    stats: List[CardStat] = field(default_factory=list)
    table: Optional[CardTable] = None
    footer_text: str = "凭他教育升学规划整体解决方案"
    footer_sub: str = "常州家长荟"      # 右下角小字
    watermark_text: str = "凭他教育"

    # ── 图标 SVG（内联，不依赖外部资源）───────────────────────────────
    _ICON_PEOPLE = (
        '<svg viewBox="0 0 40 40" width="36" height="36"><circle cx="20" cy="13" r="7" fill="{navy}"/>'
        '<path d="M7 34c0-7.2 5.8-13 13-13s13 5.8 13 13" fill="{navy}"/></svg>'
    )
    _ICON_SCHOOL = (
        '<svg viewBox="0 0 40 40" width="36" height="36">'
        '<path d="M20 4L3 14v3h34v-3L20 4z" fill="{navy}"/>'
        '<path d="M6 19v14h6V19H6zm10 0v14h8V19h-6zm12 0v14h6V19h-6z" fill="{navy}"/></svg>'
    )
    _ICON_BOOK = (
        '<svg viewBox="0 0 40 40" width="36" height="36">'
        '<path d="M6 6c0-1.5 1-3 3-3h8c2 0 3 1.5 3 3v28H9c-2 0-3-1.5-3-3V6z" fill="{navy}" opacity=".7"/>'
        '<path d="M20 6c0-1.5 1-3 3-3h8c2 0 3 1.5 3 3v28H23c-2 0-3-1.5-3-3V6z" fill="{navy}" opacity=".9"/>'
        '<path d="M20 6v28" stroke="{navy}" stroke-width="1"/></svg>'
    )
    _ICON_TEMPLE = (
        '<svg viewBox="0 0 40 32" width="32" height="26">'
        '<path d="M20 2L2 12h36L20 2z" fill="{gold}"/>'
        '<rect x="5" y="13" width="4" height="15" fill="{gold}"/>'
        '<rect x="14" y="13" width="4" height="15" fill="{gold}"/>'
        '<rect x="22" y="13" width="4" height="15" fill="{gold}"/>'
        '<rect x="31" y="13" width="4" height="15" fill="{gold}"/>'
        '<rect x="1" y="28" width="38" height="3" fill="{gold}"/></svg>'
    )
    _ICON_GRAD_CAP = (
        '<svg viewBox="0 0 100 80" width="72" height="58">'
        '<polygon points="50,2 88,30 85,33 50,8 15,33 12,30" fill="{navy}"/>'
        '<polygon points="18,33 18,55 48,70 48,48" fill="{navy}"/>'
        '<polygon points="82,33 82,55 52,70 52,48" fill="{navy}" opacity=".85"/>'
        '<rect x="16" y="31" width="68" height="4" rx="1" fill="{navy}" opacity=".6"/>'
        '<circle cx="50" cy="44" r="4" fill="{gold}"/>'
        '<path d="M35 60 Q50 75 65 60" stroke="{gold}" stroke-width="2" fill="none"/>'
        '<path d="M30 56 Q25 48 30 42 M70 56 Q75 48 70 42" stroke="{gold}" stroke-width="1.5" fill="none" opacity=".7"/>'
        '</svg>'
    )

    # ── 主渲染入口 ────────────────────────────────────────────────────

    def render_html(self) -> str:
        """返回完整独立 HTML 文档（可用于浏览器预览 / 截图）。"""
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={CARD_WIDTH}">
<title>{self._esc(self.title)} {self._esc(self.subtitle)}</title>
{self._style_block()}
</head>
<body>
{self._card_outer()}
</body>
</html>"""

    def render_fragment(self) -> str:
        """返回可嵌入微信公众号/网站的 HTML 片段（含 <style>，不含 html/head/body）。

        使用作用域安全版本（无全局 * / body 规则），避免污染父页面样式。
        """
        return f'<style>{self._style_block_scoped()}</style>\n{self._card_outer()}'

    # ── CSS ───────────────────────────────────────────────────────────

    @staticmethod
    def _style_block() -> str:
        return f"""<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    background:#EDE8DC;
    display:flex; justify-content:center;
    padding:24px 12px; font-family:{FONT_SANS};
  }}
  .pc-card {{
    width:{CARD_WIDTH}; background:{C_CREAM_BG};
    border: 3px double {C_GOLD_DARK};
    border-radius:6px;
    position:relative; overflow:hidden;
    padding:22px 18px 16px;
    font-family:{FONT_SANS};
  }}
  /* 角花 */
  .pc-corner-tl,.pc-corner-tr,.pc-corner-bl,.pc-corner-br {{
    position:absolute; width:28px; height:28px;
    border-color:{C_GOLD_DARK}; border-style:solid;
  }}
  .pc-corner-tl {{ top:-1px; left:-1px; border-width:4px 0 0 4px; }}
  .pc-corner-tr {{ top:-1px; right:-1px; border-width:4px 4px 0 0; }}
  .pc-corner-bl {{ bottom:-1px; left:-1px; border-width:0 0 4px 4px; }}
  .pc-corner-br {{ bottom:-1px; right:-1px; border-width:0 4px 4px 0; }}

  /* 水印 */
  .pc-wm {{
    position:absolute; top:0; left:0; width:100%; height:100%;
    pointer-events:none; z-index:2;
    background-image: repeating-linear-gradient(
      -30deg,
      transparent, transparent 120px,
      {C_WATERMARK} 120px, {C_WATERMARK} 240px
    );
    -webkit-user-select:none; user-select:none;
  }}
  .pc-wm::after {{
    content:"{KnowledgeCard.watermark_text if isinstance(KnowledgeCard.watermark_text, str) else '凭他教育'}";
    position:absolute; top:50%; left:50%;
    transform:translate(-50%,-50%) rotate(-30deg);
    font-size:72px; color:rgba(26,42,74,0.05);
    white-space:nowrap; letter-spacing:24px;
    font-family:{FONT_SERIF}; font-weight:700;
  }}

  /* 头部 */
  .pc-header {{ display:flex; align-items:center; gap:14px; margin-bottom:14px; position:relative;z-index:3; }}
  .pc-header-text {{ flex:1; }}
  .pc-title {{
    font-family:{FONT_SERIF}; font-size:30px; font-weight:900;
    color:{C_NAVY}; letter-spacing:2px; line-height:1.2;
  }}
  .pc-subtitle {{
    font-family:{FONT_SERIF}; font-size:22px; font-weight:700;
    color:{C_GOLD}; letter-spacing:1px; margin-top:2px;
  }}

  /* 统计栏 */
  .pc-stats {{
    display:flex; gap:0; background:#F0EBE0;
    border:1.5px solid {C_GOLD_DARK}; border-radius:8px;
    padding:12px 8px; margin-bottom:14px; position:relative;z-index:3;
  }}
  .pc-stat {{ flex:1; text-align:center; display:flex; align-items:center; justify-content:center; gap:6px; }}
  .pc-stat-icon {{ flex-shrink:0; }}
  .pc-stat-label {{ font-size:11px; color:{C_TEXT_MUTED}; line-height:1.3; }}
  .pc-stat-value-wrap {{ text-align:left; }}
  .pc-stat-num {{ font-size:22px; font-weight:900; color:{C_GOLD_DARK}; line-height:1; font-family:{FONT_SANS}; }}
  .pc-stat-unit {{ font-size:12px; color:{C_TEXT_MUTED}; }}

  /* 表格 */
  .pc-table-wrap {{ position:relative; z-index:3; border-radius:6px; overflow:hidden; border:1px solid {C_GOLD_DARK}; }}
  .pc-table-head {{
    background:{C_TABLE_HEADER_BG}; color:#FFF;
    text-align:center; padding:10px 12px;
    font-family:{FONT_SERIF}; font-size:17px; font-weight:700;
    letter-spacing:3px; display:flex; align-items:center; justify-content:center; gap:6px;
  }}
  .pc-table-head .star {{ color:{C_GOLD}; }}
  table.pc-table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  table.pc-table th {{
    background:{C_NAVY}; color:#E8E4DB; font-weight:600;
    padding:9px 8px; text-align:center; font-size:12.5px;
    border:1px solid rgba(201,169,110,0.3);
  }}
  table.pc-table td {{
    padding:8px 8px; text-align:center; color:{C_TEXT_DARK};
    border:1px solid rgba(201,169,110,0.25); font-size:12.5px; vertical-align:middle; line-height:1.45;
  }}
  table.pc-table tr:nth-child(even) td {{ background:{C_ROW_EVEN}; }}
  table.pc-table tr:nth-child(odd) td {{ background:{C_ROW_ODD}; }}
  /* 多行单元格 */
  td .pc-sub {{ display:block; font-size:11px; color:{C_TEXT_MUTED}; margin-top:1px; line-height:1.3; }}

  /* 页脚 */
  .pc-footer {{
    margin-top:14px; background:{C_NAVY};
    border-radius:4px; padding:10px 16px;
    display:flex; align-items:center; justify-content:center; gap:10px;
    position:relative; z-index:3;
  }}
  .pc-footer-text {{
    color:{C_GOLD}; font-family:{FONT_SERIF};
    font-size:14px; font-weight:700; letter-spacing:2px;
    white-space:nowrap;
  }}
  .pc-footer-star {{ color:{C_GOLD}; font-size:12px; }}
  .pc-footer-sub {{
    color:rgba(255,255,255,0.45); font-size:11px;
    margin-left:auto; white-space:nowrap;
  }}
</style>"""

    @staticmethod
    def _style_block_scoped() -> str:
        """作用域安全版本：仅包含 .pc-card* 选择器，不含全局 * / body 规则。

        用于嵌入网站/公众号编辑器等已有样式的页面环境，
        避免全局重置破坏父容器布局。
        """
        # 提取完整样式块，去掉前两行全局规则（* 和 body）
        full = KnowledgeCard._style_block()
        # 去掉 <style> 标签
        inner = full.replace("<style>", "").replace("</style>", "")
        lines = inner.strip().split("\n")
        # 跳过以 `* {` 或 `body {` 开头的规则块
        skip = False
        scoped_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("* {") or stripped.startswith("body {"):
                skip = True
                continue
            if skip and stripped == "}":
                skip = False
                continue
            if not skip:
                scoped_lines.append(line)
        return "\n".join(scoped_lines)

    # ── DOM 构建 ──────────────────────────────────────────────────────

    def _card_outer(self) -> str:
        inner = self._card_inner()
        return (
            f'<div class="pc-card">\n'
            f'  <div class="pc-corner-tl"></div>\n'
            f'  <div class="pc-corner-tr"></div>\n'
            f'  <div class="pc-corner-bl"></div>\n'
            f'  <div class="pc-corner-br"></div>\n'
            f'  <div class="pc-wm"></div>\n'
            f'{inner}'
            f'</div>'
        )

    def _card_inner(self) -> str:
        parts: list[str] = []
        parts.append(self._build_header())
        if self.stats:
            parts.append(self._build_stats())
        if self.table:
            parts.append(self._build_table())
        parts.append(self._build_footer())
        return "\n".join(parts)

    def _build_header(self) -> str:
        cap_svg = self._ICON_GRAD_CAP.format(navy=C_NAVY, gold=C_GOLD)
        return (
            f'<div class="pc-header">\n'
            f'  <div class="pc-cap">{cap_svg}</div>\n'
            f'  <div class="pc-header-text">\n'
            f'    <div class="pc-title">{self._esc(self.title)}</div>\n'
            f'    <div class="pc-subtitle">{self._esc(self.subtitle)}</div>\n'
            f'  </div>\n'
            f'</div>'
        )

    def _build_stats(self) -> str:
        icons = [self._ICON_PEOPLE, self._ICON_SCHOOL, self._ICON_BOOK]
        items: list[str] = []
        for i, s in enumerate(self.stats):
            svg = (icons[i % len(icons)]).format(navy=C_NAVY)
            items.append(
                f'<div class="pc-stat">\n'
                f'  <div class="pc-stat-icon">{svg}</div>\n'
                f'  <div><div class="pc-stat-label">{self._esc(s.label)}</div>'
                f'<div class="pc-stat-value-wrap">'
                f'<span class="pc-stat-num">{self._esc(s.value)}</span>'
                f'<span class="pc-stat-unit">{self._esc(s.unit)}</span>'
                f'</div></div></div>'
            )
        return f'<div class="pc-stats">\n{"  ".join(items)}\n</div>'

    def _build_table(self) -> str:
        t = self.table
        head = (
            f'<div class="pc-table-head">'
            f'<span class="star">★</span> {self._esc(t.title)} <span class="star">★</span>'
            f'</div>'
        )
        ths = "".join(f"<th>{self._esc(h)}</th>" for h in t.headers)
        trs: list[str] = []
        for ri, row in enumerate(t.rows):
            tds: list[str] = []
            for cell in row:
                lines = cell.split("\n")
                main = self._esc(lines[0])
                subs = "".join(f'<span class="pc-sub">{self._esc(l)}</span>' for l in lines[1:])
                tds.append(f"<td>{main}{subs}</td>")
            trs.append(f"<tr>{''.join(tds)}</tr>")
        return (
            f'<div class="pc-table-wrap">\n'
            f'  {head}\n'
            f'  <table class="pc-table"><thead><tr>{ths}</tr></thead>'
            f'<tbody>{"\n".join(trs)}</tbody></table>\n'
            f'</div>'
        )

    def _build_footer(self) -> str:
        temple = self._ICON_TEMPLE.format(gold=C_GOLD)
        return (
            f'<div class="pc-footer">\n'
            f'  <div>{temple}</div>\n'
            f'  <span class="pc-footer-star">★</span>\n'
            f'  <span class="pc-footer-text">{self._esc(self.footer_text)}</span>\n'
            f'  <span class="pc-footer-star">★</span>\n'
            f'  <span class="pc-footer-sub">公众号 {self._esc(self.footer_sub)}</span>\n'
            f'</div>'
        )

    # ── 工具 ──────────────────────────────────────────────────────────

    @staticmethod
    def _esc(s: str) -> str:
        """最小 HTML 转义（仅防破坏结构）。"""
        return (s
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))


# ── 便捷工厂：从 wechat_transform_service 的 ExtractedCore 自动构建 ─────

def build_card_from_data(
    *,
    title: str,
    subtitle: str,
    stat_items: list[dict],
    table_title: str,
    table_headers: list[str],
    table_rows: list[list[str]],
    footer_sub: str = "常州家长荟",
) -> KnowledgeCard:
    """从原始字典列表快速构建卡片（给 pipeline 层调用）。"""
    stats = [CardStat(**it) for it in stat_items]
    tbl = CardTable(title=table_title, headers=table_headers, rows=table_rows)
    return KnowledgeCard(
        title=title, subtitle=subtitle, stats=stats, table=tbl, footer_sub=footer_sub,
    )
