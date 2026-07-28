"""CMP-PRES-OUTPUT-ADAPTER：快照 → 稳定 CT-009 响应 + 静态 HTML 导出。

PRES-IC-04 / LCD-PRES-004：只固定 `presentation_id + blocks[]` 的稳定
响应映射，与具体渲染解耦；LCD-008/DD-003 的展示导出格式为静态 HTML
（v1 不做 PDF），可在教师网页端打开（D-AC-REQ-010-01 oracle）。

导出的 HTML 为自包含静态文档：全部动态内容经 html.escape 转义，
缺失标记显式展示（不隐藏缺口），不引入外部脚本/样式资源。
"""
from __future__ import annotations

from html import escape

from .store import Snapshot

#: 导出格式标识（DD-003/LCD-008；v1 无 PDF）。
EXPORT_FORMAT_HTML = "static-html"


def to_response(snapshot: Snapshot) -> dict:
    """PRES-IC-04：快照 → contracts/ct-009.json response（稳定映射）。"""
    return {
        "presentation_id": snapshot.presentation_id,
        "blocks": [dict(block) for block in snapshot.blocks],
    }


def _esc(value: object) -> str:
    return escape("" if value is None else str(value))


def _render_block(block: dict) -> str:
    parts = [f"<section><h2>小组 {_esc(block.get('group_id'))}</h2>"]
    project = block.get("project_result")
    if project:
        parts.append(
            "<p>项目结果：提交 "
            f"<code>{_esc(project.get('submission_id'))}</code> / 材料引用 "
            f"<code>{_esc(project.get('result_ref'))}</code></p>"
        )
    else:
        parts.append("<p>项目结果：缺失</p>")
    parts.append(f"<p>过程摘要：{_esc(block.get('process_summary'))}</p>")

    parts.append("<h3>评分</h3><ul>")
    for grade in block.get("grades", []):
        parts.append(
            "<li>提交 "
            f"{_esc(grade.get('submission_id'))}：原始 "
            f"{_esc(grade.get('original_grade'))} / 最终 "
            f"{_esc(grade.get('final_grade'))}</li>"
        )
    parts.append("</ul>")

    parts.append("<h3>教师批注</h3><ul>")
    for annotation in block.get("annotations", []):
        parts.append(
            f"<li>{_esc(annotation.get('operator'))}："
            f"{_esc(annotation.get('excerpt'))}</li>"
        )
    parts.append("</ul>")

    missing = block.get("missing_marks", [])
    parts.append("<h3>缺失标记</h3>")
    if missing:
        items = "".join(f"<li>{_esc(mark)}</li>" for mark in missing)
        parts.append(f"<ul>{items}</ul>")
    else:
        parts.append("<p>无</p>")
    parts.append("</section>")
    return "".join(parts)


def render_html(snapshot: Snapshot) -> str:
    """LCD-008/DD-003：快照 → 自包含静态 HTML（v1 不做 PDF）。"""
    body = "".join(_render_block(block) for block in snapshot.blocks)
    return (
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        f"<title>展示视图 {_esc(snapshot.presentation_id)}</title></head>"
        "<body>"
        f"<h1>课堂展示视图 {_esc(snapshot.presentation_id)}</h1>"
        f"<p>生成时间：{_esc(snapshot.generated_at.isoformat())}；"
        "本视图为生成时点快照，不随源数据实时更新。</p>"
        f"{body}"
        "</body></html>"
    )
