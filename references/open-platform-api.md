# Amazon SP-API & 开放平台集成指南

## 概述

亚马逊运营硅基军团的API基于FastAPI构建，支持与微盟、腾讯云等主流SaaS平台集成。

## 一、API端点总览

| 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/health` | GET | 健康检查 | 无 |
| `/api/v1/agents` | GET | Agent列表 | API Key |
| `/api/v1/routing` | GET | 路由表 | API Key |
| `/api/v1/execute` | POST | 单任务执行 | API Key+签名 |
| `/api/v1/batch` | POST | 批量执行 | API Key+签名 |
| `/api/v1/stats` | GET | 系统统计 | API Key |
| `/api/v1/audit` | GET | 审计日志 | API Key |
| `/api/v1/webhook` | POST | Webhook回调 | HMAC验证 |

## 二、认证方式

### 2.1 API Key 认证（基础）
```
X-API-Key: your_api_key_here
```

### 2.2 HMAC签名认证（推荐，企业级）
```
X-API-Key: your_api_key
X-Timestamp: 1713000000
X-Signature: hmac_sha256(timestamp + body)
```

签名算法（Python示例）：
```python
import hmac, hashlib, time
timestamp = str(int(time.time()))
payload = f"{timestamp}.{body}"
signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
```

## 三、请求示例

### curl 基础调用
```bash
curl -X POST http://localhost:8080/api/v1/execute \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{"task": "帮我分析这款无线蓝牙耳机的市场机会"}'
```

### curl 带签名调用
```bash
TIMESTAMP=$(date +%s)
BODY='{"task":"帮我分析选品"}'
SIGNATURE=$(echo -n "${TIMESTAMP}.${BODY}" | openssl dgst -sha256 -hmac "your_secret" | cut -d' ' -f2)

curl -X POST http://localhost:8080/api/v1/execute \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -H "X-Timestamp: ${TIMESTAMP}" \
  -H "X-Signature: ${SIGNATURE}" \
  -d "${BODY}"
```

### Python SDK调用
```python
from amazon_ops import AmazonOpsClient

client = AmazonOpsClient(
    api_key="your_api_key",
    secret="your_secret",
    base_url="https://your-domain.com",
)

# 单任务
result = client.execute("帮我分析这个产品的市场机会")

# 批量
result = client.batch_execute([
    "帮我分析选品",
    "优化我的listing标题",
    "我的广告acos太高了"
])
```

## 四、响应格式

### 成功响应（单任务）
```json
{
  "task_id": "a1b2c3d4",
  "chief": "🎩 ChiefOfStaff",
  "routed_agents": ["product_research"],
  "agent_count": 1,
  "strategy": "single",
  "results": {
    "product_research": {
      "agent": "🔍 选品分析Agent",
      "tokens": 150,
      "input": "帮我分析这款无线蓝牙耳机...",
      "result": { ... },
      "kpis": { ... }
    }
  },
  "total_tokens": 150,
  "timestamp": "2026-04-13T10:30:00"
}
```

### 成功响应（批量）
```json
{
  "total": 3,
  "task_id": "b2c3d4e5",
  "results": [
    { "input": "...", "routed_agents": [...], "results": {...}, "tokens": 150 },
    ...
  ]
}
```

### 错误响应
```json
{
  "code": "MISSING_API_KEY",
  "message": "请提供 X-API-Key header",
  "detail": null
}
```

## 五、Webhook 回调

### 请求格式
```json
{
  "event": "task_completed",
  "task_id": "a1b2c3d4",
  "timestamp": "2026-04-13T10:30:00Z",
  "result": { ... }
}
```

### 注册Webhook
```python
# 触发任务时指定callback_url
result = client.execute(
    "帮我分析选品",
    callback_url="https://your-server.com/api/amazon-ops-callback"
)
```

### 验证Webhook签名
```python
import hmac, hashlib

def verify_webhook(callback_url: str, signature: str, webhook_secret: str) -> bool:
    expected = hmac.new(
        webhook_secret.encode(),
        callback_url.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

## 六、错误码说明

| 错误码 | HTTP状态 | 说明 | 解决方案 |
|--------|----------|------|---------|
| `MISSING_API_KEY` | 401 | 缺少API Key | 添加X-API-Key header |
| `INVALID_API_KEY` | 401 | API Key无效 | 检查Key是否正确或已过期 |
| `INVALID_SIGNATURE` | 401 | 签名验证失败 | 检查Secret和签名算法 |
| `RATE_LIMITED` | 429 | 请求过于频繁 | 降低请求频率 |
| `INTERNAL_ERROR` | 500 | 服务器内部错误 | 联系技术支持 |

## 七、速率限制

| 套餐 | 限制 |
|------|------|
| 基础版 | 100次/分钟 |
| 专业版 | 100次/分钟 |
| 企业版 | 无限制 |

## 八、环境变量

```bash
# 认证
AMAZON_OPS_API_KEY=your_api_key
AMAZON_OPS_API_SECRET=your_secret
AMAZON_OPS_TIER=professional  # basic | professional | enterprise
AMAZON_OPS_CLIENT_NAME=your_client

# 服务
HOST=0.0.0.0
PORT=8080
LOG_LEVEL=INFO
DEBUG=false

# Amazon SP-API（可选）
SP_API_CLIENT_ID=your_spapi_client_id
SP_API_CLIENT_SECRET=your_spapi_client_secret
SP_API_REFRESH_TOKEN=your_refresh_token
```

## 九、SLA承诺

| 指标 | 承诺 |
|------|------|
| 可用性 | 99.9% |
| API响应时间 | P95 < 500ms |
| Webhook投递 | 99.5% |
| 支持响应 | 企业版7×24，旗舰版工作日8h |
