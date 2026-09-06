"""热点视频「点赞/收藏」推送门槛的持久化存储。

默认门槛与历史上硬编码在 social_video_service.threshold_for 中的值保持一致，
改为可运行时编辑：保存在 backend/data/hot_thresholds.json，
前端「推送门槛设置」卡片可随时修改并即时生效。
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

# (platform, scope) 组合 -> 默认门槛。platform/scope 使用与前端、domain 一致的中文枚举值。
_PLATFORM_SCOPE_KEYS: list[tuple[str, str]] = [
    ("抖音", "全国大博主"),
    ("微信视频号", "全国大博主"),
    ("抖音", "常州本地"),
    ("微信视频号", "常州本地"),
]

DEFAULTS: dict[str, dict[str, int]] = {
    "抖音|全国大博主": {"likes": 1250, "saves": 500},
    "微信视频号|全国大博主": {"likes": 250, "saves": 50},
    "抖音|常州本地": {"likes": 125, "saves": 50},
    "微信视频号|常州本地": {"likes": 50, "saves": 18},
}

# backend/data/hot_thresholds.json（app/services/ -> backend/data）
_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "hot_thresholds.json"
_lock = threading.Lock()


def _default_payload() -> dict[str, Any]:
    return {"version": 1, "thresholds": _build_defaults()}


def _build_defaults() -> dict[str, dict[str, int]]:
    return {f"{p}|{s}": dict(DEFAULTS[f"{p}|{s}"]) for p, s in _PLATFORM_SCOPE_KEYS}


def load() -> dict[str, Any]:
    """读取门槛配置；文件缺失/损坏时回退默认并落地默认文件。"""
    with _lock:
        if not _PATH.exists():
            payload = {"version": 1, "thresholds": _build_defaults()}
            _write(payload)
            return payload
        try:
            data = json.loads(_PATH.read_text(encoding="utf-8"))
        except Exception:
            payload = {"version": 1, "thresholds": _build_defaults()}
            _write(payload)
            return payload
        raw = data.get("thresholds", {}) if isinstance(data, dict) else {}
        merged: dict[str, dict[str, int]] = {}
        for p, s in _PLATFORM_SCOPE_KEYS:
            key = f"{p}|{s}"
            d = raw.get(key, {}) if isinstance(raw, dict) else {}
            default = DEFAULTS[key]
            merged[key] = {
                "likes": _to_int(d.get("likes"), default["likes"]),
                "saves": _to_int(d.get("saves"), default["saves"]),
            }
        return {"version": 1, "thresholds": merged}


def save(incoming: dict[str, dict[str, int]]) -> dict[str, Any]:
    """持久化门槛；未提供的组合回退默认，数值钳制为非负整数。"""
    merged: dict[str, dict[str, int]] = {}
    for p, s in _PLATFORM_SCOPE_KEYS:
        key = f"{p}|{s}"
        d = incoming.get(key, DEFAULTS[key]) if isinstance(incoming, dict) else DEFAULTS[key]
        merged[key] = {
            "likes": max(0, _to_int(d.get("likes"), DEFAULTS[key]["likes"])),
            "saves": max(0, _to_int(d.get("saves"), DEFAULTS[key]["saves"])),
        }
    payload = {"version": 1, "thresholds": merged}
    _write(payload)
    return payload


def get_threshold(platform: str, scope: str) -> tuple[int, int]:
    data = load()
    d = data["thresholds"].get(f"{platform}|{scope}", DEFAULTS.get(f"{platform}|{scope}", {"likes": 0, "saves": 0}))
    return d["likes"], d["saves"]


def _to_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _write(payload: dict[str, Any]) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_PATH)
