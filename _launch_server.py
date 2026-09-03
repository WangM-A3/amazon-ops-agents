"""试跑 launcher：注入仓库根到 sys.path 后启动 api_server（规避嵌入式 Python ._pth 对非 ASCII 路径的忽略）"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("api_server:app", host=host, port=port, workers=1, log_level="info")
