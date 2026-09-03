"""md2pdf.py — Markdown → PDF（Chrome 无头打印，中文可靠）

用法: .runtime/python312/python.exe md2pdf.py <输入.md> <输出.pdf> [标题]
流程: markdown 库转 HTML → playwright-core + 系统 Chrome 无头打印（page.pdf）
依赖: markdown、pymupdf（校验用）、Node.js、系统 Chrome/Edge
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

_CSS = """
body { font-family: "Microsoft YaHei","SimHei",sans-serif; font-size: 11pt; line-height: 1.6; color: #222; }
h1 { font-size: 19pt; color: #0b57d0; border-bottom: 2px solid #0b57d0; padding-bottom: 4px; }
h2 { font-size: 14pt; color: #0b57d0; border-left: 5px solid #0b57d0; padding-left: 8px; margin-top: 14px; }
h3 { font-size: 12pt; color: #333; margin-top: 8px; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 9.5pt; }
th { background: #0b57d0; color: #fff; padding: 5px 7px; }
td { border: 1px solid #bbb; padding: 5px 7px; }
tr:nth-child(even) td { background: #f2f6fd; }
pre { background: #f6f8fa; border: 1px solid #ddd; padding: 8px; font-size: 9pt; white-space: pre-wrap; word-break: break-all; }
code { background: #f0f0f0; padding: 1px 4px; font-size: 9pt; }
blockquote { color: #555; border-left: 4px solid #ffb300; padding-left: 12px; margin-left: 0; }
strong { color: #111; }
footer { position: fixed; bottom: -14mm; width: 100%; text-align: center; font-size: 8pt; color: #999; }
"""

_HERE = Path(__file__).resolve().parent
_HTML2PDF = _HERE / "html2pdf.js"


def convert(md_path: str, pdf_path: str, title: str = "") -> int:
    text = Path(md_path).read_text(encoding="utf-8")
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8"><style>' + _CSS + "</style></head><body>"
        + (f"<footer>亚马逊运营硅基军团 v2.0 · {title}</footer>" if title else "")
        + body + "</body></html>"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".html", encoding="utf-8", delete=False, dir=str(_HERE / "docs")) as f:
        f.write(html)
        tmp_html = f.name
    try:
        r = subprocess.run(["node", str(_HTML2PDF), tmp_html, pdf_path], capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            print("PDF 生成失败:", (r.stderr or "")[-500:])
            return 1
        print((r.stdout or "").strip())
        return 0
    finally:
        Path(tmp_html).unlink(missing_ok=True)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(convert(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "使用指南"))
