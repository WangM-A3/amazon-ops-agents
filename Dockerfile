FROM python:3.11-slim

WORKDIR /app

# 安装依赖（分层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码
COPY . .

# 环境变量（运行时注入）
ENV PYTHONPATH=/app
ENV HOST=0.0.0.0
ENV PORT=8080
ENV LOG_LEVEL=INFO

# 非root运行
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/health').raise_for_status()"

# 启动
CMD ["python", "api_server.py"]
