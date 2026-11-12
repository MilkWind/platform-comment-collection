"""UI strings. Default locale is zh-CN; English is the alternative.

Platform names and field labels come from each platform's metadata, so a new
skill adds a tab with no edits here.
"""

from __future__ import annotations

DEFAULT_LOCALE = "zh"

STRINGS: dict[str, dict[str, str]] = {
    "zh": {
        "app_title": "视频评论与弹幕采集",
        "app_subtitle": "选择平台，粘贴链接，勾选字段，一键采集。",
        "language": "语言",
        "output_root": "输出目录",
        "input_label": "视频链接或 BV 号",
        "input_placeholder": "https://www.bilibili.com/video/BV1GJ411x7h7 或 BV1GJ411x7h7",
        "input_invalid": "无法识别为有效的视频链接。",
        "load_video": "加载视频",
        "video_loaded": "已加载：",
        "parts": "分P",
        "scope": "采集范围",
        "collect_comments": "评论（一级）",
        "collect_sub": "楼中楼（二级回复）",
        "collect_danmaku": "弹幕",
        "sort": "评论排序",
        "sort_hot": "按热度",
        "sort_time": "按时间",
        "fields_comments": "评论字段",
        "fields_danmaku": "弹幕字段",
        "advanced": "高级选项",
        "preset": "速度预设",
        "preset_safe": "保守",
        "preset_balanced": "均衡",
        "preset_fast": "快速",
        "max_roots": "最多一级评论数（0 为不限）",
        "start": "开始采集",
        "cancel": "取消",
        "running": "采集中…",
        "how_to_get_cookie": "如何获取 Cookie（可选）",
        "anon_banner": "当前为匿名模式：IP 属地不可用，部分楼中楼可能不完整。",
        "logs": "运行日志",
        "results": "结果",
        "download": "下载结果压缩包",
        "open_dir": "输出目录",
        "phase_auth": "验证凭证",
        "phase_resolve": "解析视频",
        "phase_comments": "评论",
        "phase_danmaku": "弹幕",
        "phase_finalize": "写入文件",
        "done": "采集完成",
        "cancelled": "已取消",
        "error": "出错",
        "job_running_banner": "任务运行中",
        "required_login": "需要登录",
        "no_video_yet": "请先加载视频。",
    },
    "en": {
        "app_title": "Video Comment & Danmaku Collector",
        "app_subtitle": "Pick a platform, paste a link, choose fields, and collect.",
        "language": "Language",
        "output_root": "Output folder",
        "input_label": "Video URL or BV id",
        "input_placeholder": "https://www.bilibili.com/video/BV1GJ411x7h7 or BV1GJ411x7h7",
        "input_invalid": "Not a recognizable video link.",
        "load_video": "Load video",
        "video_loaded": "Loaded: ",
        "parts": "Parts",
        "scope": "Scope",
        "collect_comments": "Comments (roots)",
        "collect_sub": "Sub-replies",
        "collect_danmaku": "Danmaku",
        "sort": "Comment sort",
        "sort_hot": "By popularity",
        "sort_time": "By time",
        "fields_comments": "Comment fields",
        "fields_danmaku": "Danmaku fields",
        "advanced": "Advanced",
        "preset": "Speed preset",
        "preset_safe": "Safe",
        "preset_balanced": "Balanced",
        "preset_fast": "Fast",
        "max_roots": "Max root comments (0 = unlimited)",
        "start": "Start collection",
        "cancel": "Cancel",
        "running": "Running…",
        "how_to_get_cookie": "How to get a cookie (optional)",
        "anon_banner": "Anonymous mode: IP location is unavailable and some sub-replies may be truncated.",
        "logs": "Logs",
        "results": "Results",
        "download": "Download results (.zip)",
        "open_dir": "Output folder",
        "phase_auth": "Verifying credentials",
        "phase_resolve": "Resolving video",
        "phase_comments": "Comments",
        "phase_danmaku": "Danmaku",
        "phase_finalize": "Writing files",
        "done": "Collection complete",
        "cancelled": "Cancelled",
        "error": "Error",
        "job_running_banner": "Job running",
        "required_login": "Login required",
        "no_video_yet": "Load a video first.",
    },
}


def t(locale: str, key: str) -> str:
    return STRINGS.get(locale, STRINGS[DEFAULT_LOCALE]).get(key, key)


def label(locale: str, en: str, zh: str) -> str:
    return zh if locale.startswith("zh") else en
