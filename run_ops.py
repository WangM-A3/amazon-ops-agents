"""
run_ops.py — 亚马逊运营硅基军团统一 CLI 入口
==============================================
解决嵌入式 Python（._pth 忽略 CWD）下裸 `python -c` 无法导入引擎模块的问题：
本入口内置 sys.path 引导，所有子命令在仓库任意子目录下均可运行。

用法（仓库根 amazon-ops/ 下）：
    .runtime/python312/python.exe run_ops.py test          # pytest tests/ 全量回归
    .runtime/python312/python.exe run_ops.py selftest      # tests/test_demo.py 自测套件
    .runtime/python312/python.exe run_ops.py bench         # ProfitOptimizer 诚实基准
    .runtime/python312/python.exe run_ops.py po-test       # ProfitOptimizer 17 项测试
    .runtime/python312/python.exe run_ops.py ingest [目录] # 导入数据（默认 data/sample）
    .runtime/python312/python.exe run_ops.py workflow <id> # 跑预置工作流
    .runtime/python312/python.exe run_ops.py server [port] # 启动 FastAPI（默认 8080）
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.chdir(_ROOT)


def _cmd_test() -> int:
    import pytest
    return pytest.main(["tests/", "-q", "--no-header"])


def _cmd_selftest() -> int:
    import runpy
    sys.argv = ["tests/test_demo.py"]
    runpy.run_path("tests/test_demo.py", run_name="__main__")
    return 0


def _cmd_bench() -> int:
    import runpy
    runpy.run_path("benchmarks/bench_profit_optimizer.py", run_name="__main__")
    return 0


def _cmd_po_test() -> int:
    import runpy
    runpy.run_path("execution/tests/test_profit_optimizer.py", run_name="__main__")
    return 0


def _cmd_ingest(directory: str = "data/sample") -> int:
    from data.store import SellerDataStore
    from data.ingest import ingest_dir
    results = ingest_dir(SellerDataStore(), directory)
    for r in results:
        print(r)
    print(f"共导入 {sum(r.get('rows', 0) for r in results)} 行")
    return 0


def _cmd_workflow(workflow_id: str) -> int:
    import asyncio
    from workflows.presets import WORKFLOW_ENGINE

    async def _run() -> None:
        result = await WORKFLOW_ENGINE.launch(workflow_id, {})
        print(f"workflow={workflow_id} status={result.status.value} error={result.error} "
              f"steps={len(result.step_results)} 耗时={result.total_seconds:.1f}s")

    asyncio.run(_run())
    return 0


def _cmd_server(port: int = 8080) -> int:
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=port, workers=1, log_level="info")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "test":
        return _cmd_test()
    if cmd == "selftest":
        return _cmd_selftest()
    if cmd == "bench":
        return _cmd_bench()
    if cmd in ("po-test", "po"):
        return _cmd_po_test()
    if cmd == "ingest":
        return _cmd_ingest(sys.argv[2] if len(sys.argv) > 2 else "data/sample")
    if cmd == "workflow":
        if len(sys.argv) < 3:
            print("用法: run_ops.py workflow <new_product_launch|ad_optimization|inventory_alert|customer_service>")
            return 2
        return _cmd_workflow(sys.argv[2])
    if cmd == "server":
        return _cmd_server(int(sys.argv[2]) if len(sys.argv) > 2 else 8080)
    print(f"未知子命令: {cmd}")
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
