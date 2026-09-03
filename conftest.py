"""
conftest.py — 测试基建修复
============================
1. 把仓库根加入 sys.path：修复 tests/reverse/ 因 __init__.py 导致的
   `No module named 'agents'` 收集失败（pytest 默认只插入 basedir）。
2. 强制 UTF-8 输出：修复中文 Windows(GBK 控制台) 下 print(emoji)
   抛 UnicodeEncodeError 的崩溃。
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# 修复 GBK 控制台 print emoji 崩溃（pytest 收集阶段即生效）
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# 测试默认关闭真实 LLM 调用（保持确定性；LLM 路径由 test_llm_route.py 显式开启）
os.environ.setdefault("AMAZON_OPS_LLM", "off")


def pytest_configure(config) -> None:  # noqa: ARG001
    """所有测试执行前统一输出编码"""
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ARG001
    """会话结束清理：关闭数据/LLM 单例，避免跨测试文件串扰"""
    try:
        from data.provider import reset_provider
        reset_provider()
    except Exception:  # noqa: BLE001
        pass
    try:
        from llm.client import reset_llm_client
        reset_llm_client()
    except Exception:  # noqa: BLE001
        pass
