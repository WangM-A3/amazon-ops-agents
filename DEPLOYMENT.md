# 亚马逊运营硅基军团 — 部署文档

> **Amazon Operations Silicon Army** v1.0.0
> 1个幕僚长 + 22个专业Agent | 企业级亚马逊运营AI平台

---

## 目录

1. [环境要求](#1-环境要求)
2. [快速启动](#2-快速启动)
3. [部署方案选择](#3-部署方案选择)
4. [Docker容器部署（推荐）](#4-docker容器部署推荐)
4B. [Railway 云端部署（公网访问）](#4b-railway-云端部署公网访问推荐免费方案)
5. [云服务器直接部署](#5-云服务器直接部署)
6. [环境配置](#6-环境配置)
7. [API密钥配置](#7-api密钥配置)
8. [前端界面集成](#8-前端界面集成)
9. [测试验证](#9-测试验证)
10. [逆向测试报告](#10-逆向测试报告)
11. [运维监控](#11-运维监控)
12. [安全配置](#12-安全配置)
13. [故障排查](#13-故障排查)

---

## 1. 环境要求

### 硬件配置

| 部署规模 | CPU | 内存 | 磁盘 | 说明 |
|---------|-----|------|------|------|
| **开发/测试** | 2核 | 4GB | 20GB | 单机 |
| **生产（小型）** | 4核 | 8GB | 50GB | 支持50并发 |
| **生产（中型）** | 8核 | 16GB | 100GB | 支持200并发 |
| **生产（大型）** | 16核 | 32GB | 200GB | 支持500+并发 |

### 软件依赖

```bash
Python >= 3.11
Docker >= 24.0
Docker Compose >= 2.20
Redis >= 7.0  # 推荐，内存会话缓存
```

---

## 2. 快速启动

### 方式A：Docker Compose（推荐，3分钟启动）

```bash
# 1. 克隆代码
git clone https://github.com/yunlü-agent/amazon-ops-agents.git
cd amazon-ops-agents

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填写实际密钥

# 3. 启动服务
docker compose up -d

# 4. 验证服务
curl http://localhost:8080/health
```

### 方式B：本地开发

```bash
# 1. 安装依赖
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. 配置环境变量
export AMAZON_OPS_API_KEY=your_key
export AMAZON_OPS_API_SECRET=your_secret
export DEEPSEEK_API_KEY=sk-...  # 至少配置一个LLM

# 3. 启动服务
python api_server.py
# → http://localhost:8080
```

---

## 3. 部署方案选择

| 方案 | 适用场景 | 优点 | 缺点 |
|-----|---------|------|------|
| **A. Docker Compose** | 中小企业、创业公司 | 快速、一致环境、易回滚 | 需要服务器 |
| **B. Railway（推荐）** | 需要公网访问、无服务器 | $5/月免费额度、自动HTTPS、零运维 | 需GitHub账号 |
| **C. 云服务器直接部署** | 大型企业、定制需求 | 完全控制、性能最优 | 运维成本高 |
| **D. Serverless** | 流量波动大、预算有限 | 自动扩缩、免运维 | 冷启动延迟、功能限制 |

**推荐：方案B（Railway）** 用于公网访问，**方案A（Docker Compose）** 用于本地开发。

---

## 4. Docker容器部署（推荐）

### 4.1 构建镜像

```bash
# 方式1：直接构建
docker build -t amazon-ops-api:latest .

# 方式2：使用 Docker Compose（推荐）
docker compose build
```

### 4.2 启动服务

```bash
# 启动所有服务（API + Redis）
docker compose up -d

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f api
docker compose logs -f redis
```

### 4.3 服务健康检查

```bash
# 健康检查
curl http://localhost:8080/health

# 预期响应：
{
  "status": "healthy",
  "version": "1.0.0",
  "agents_registered": 22,
  "uptime_seconds": 1.8,
  "timestamp": "2026-04-16T..."
}
```

### 4.4 访问API文档

- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

---

## 4B. Railway 云端部署（公网访问，推荐免费方案）

> **Railway** 是目前最适合本项目的云部署平台：
> - $5/月免费额度（500小时，足够个人/小团队使用）
> - 无需信用卡（GitHub OAuth 注册）
> - 原生支持 Dockerfile + 自动 HTTPS
> - 亚太地区访问速度可接受

### 详细部署指南

详见 [deployment/RAILWAY_DEPLOY.md](./deployment/RAILWAY_DEPLOY.md)

### 快速部署（5分钟）

```bash
# 1. 安装 Railway CLI
npm install -g @railway/cli

# 2. 登录（浏览器自动打开）
railway login

# 3. 克隆并进入项目
git clone https://github.com/WangM-A3/amazon-ops-agents.git
cd amazon-ops-agents

# 4. 初始化 Railway 项目
railway init

# 5. 配置必需环境变量
railway variables set AMAZON_OPS_API_KEY your_key
railway variables set AMAZON_OPS_API_SECRET your_secret
railway variables set DEEPSEEK_API_KEY your_deepseek_key

# 6. 部署！
railway up

# 7. 获取公网地址
railway domain
# → https://xxx.railway.app
```

### Railway 项目配置

项目根目录已包含：
- `railway.toml` — 部署配置（Dockerfile 构建）
- `.github/workflows/deploy.yml` — GitHub Actions 自动部署

---

## 5. 云服务器直接部署

### 5.1 Ubuntu 22.04 部署脚本

```bash
#!/bin/bash
# deploy.sh — Ubuntu 22.04 一键部署脚本

set -e

# ── 系统依赖 ──────────────────────────────────────────────────────────────────
apt update && apt install -y python3.11 python3.11-venv python3-pip docker.io docker-compose

# ── 应用部署 ──────────────────────────────────────────────────────────────────
mkdir -p /opt/amazon-ops
cd /opt/amazon-ops
git clone https://github.com/yunlü-agent/amazon-ops-agents.git .
cp .env.example .env

# ── Python环境 ───────────────────────────────────────────────────────────────
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# ── 环境变量（生产环境建议使用 secrets manager）────────────────────────────────
# 编辑 .env 填写实际密钥

# ── Systemd 服务 ──────────────────────────────────────────────────────────────
cat > /etc/systemd/system/amazon-ops-api.service << 'EOF'
[Unit]
Description=Amazon Ops Silicon Army API
After=network.target redis.service
Requires=redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/amazon-ops
Environment="PATH=/opt/amazon-ops/venv/bin"
EnvironmentFile=/opt/amazon-ops/.env
ExecStart=/opt/amazon-ops/venv/bin/python api_server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable amazon-ops-api
systemctl start amazon-ops-api
systemctl status amazon-ops-api
```

### 5.2 Nginx 反向代理配置

```nginx
# /etc/nginx/sites-available/amazon-ops

server {
    listen 80;
    server_name api.your-domain.com;

    # HTTPS 重定向（需要先配置证书）
    # return 301 https://$server_name$request_uri;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时配置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

### 5.3 HTTPS 配置（Let's Encrypt）

```bash
# 安装 Certbot
apt install -y certbot python3-certbot-nginx

# 获取证书
certbot --nginx -d api.your-domain.com

# 自动续期测试
certbot renew --dry-run
```

---

## 6. 环境配置

### 6.1 .env 必填项

```bash
# 至少配置以下两项才能启动：

# ① API 认证（必需）
AMAZON_OPS_API_KEY=your_api_key_here
AMAZON_OPS_API_SECRET=your_api_secret_here

# ② LLM Provider（至少一个，DEEPSEEK 性价比最高）
DEEPSEEK_API_KEY=sk-...   # 推荐：deepseek-chat 模型
# OPENAI_API_KEY=sk-...  # 可选：GPT-4o / GPT-4o-mini
```

### 6.2 AMS广告API配置（可选）

如需接入真实的亚马逊广告数据：

```bash
AMS_CLIENT_ID=amzn1.application-oa2-client.xxx
AMS_CLIENT_SECRET=your_client_secret
AMS_REFRESH_TOKEN=Atzr|xxx   # OAuth refresh token
AMS_PROFILE_ID=123456789      # Amazon Ads Profile ID
```

### 6.3 Redis配置

```bash
# 生产环境建议开启认证
REDIS_PASSWORD=your_redis_password

# docker compose 模式下，REDIS_HOST 自动为 "redis"
```

---

## 7. API密钥配置

### 7.1 获取API密钥

首次使用需要配置LLM API密钥（至少一个）：

| 服务商 | 获取地址 | 推荐模型 |
|-------|---------|---------|
| **DeepSeek** | https://platform.deepseek.com | deepseek-chat（性价比最高） |
| **OpenAI** | https://platform.openai.com | GPT-4o-mini（通用） |
| **Anthropic** | https://console.anthropic.com | Claude 3.5 Sonnet（长上下文） |

### 7.2 API认证使用

```bash
# 获取Agent列表
curl -X GET http://localhost:8080/api/v1/agents \
  -H "X-API-Key: your_api_key_here"

# 执行任务
curl -X POST http://localhost:8080/api/v1/execute \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"task": "分析蓝牙耳机选品机会", "context": {"marketplace": "US"}}'

# 批量执行
curl -X POST http://localhost:8080/api/v1/batch \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"tasks": ["分析选品", "查看广告数据"], "parallel": true}'
```

---

## 8. 前端界面集成

### 8.1 API基础信息

| 项目 | 值 |
|-----|---|
| Base URL | `http://localhost:8080`（开发）或 `https://api.your-domain.com`（生产） |
| API文档 | `http://localhost:8080/docs`（Swagger UI） |
| 认证方式 | `X-API-Key` Header |

### 8.2 前端集成示例

```javascript
// 前端调用示例（fetch API）
const API_BASE = 'https://api.your-domain.com';

async function executeTask(task) {
  const response = await fetch(`${API_BASE}/api/v1/execute`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': 'your_api_key',
    },
    body: JSON.stringify({
      task: task,
      context: { marketplace: 'US' },
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail?.message || 'API请求失败');
  }

  return response.json();
}

// 使用示例
const result = await executeTask('分析蓝牙耳机选品机会');
console.log('路由Agent:', result.routed_agents);
console.log('策略:', result.strategy);
```

### 8.3 Webhook回调配置

```javascript
// 注册异步回调
const result = await executeTask('生成选品分析报告');
// result.callback_url 包含回调地址（可选）

// Webhook端点示例（Node.js/Express）
app.post('/webhook/amazon-ops', (req, res) => {
  const { event, task_id, result } = req.body;
  if (event === 'task_completed') {
    console.log(`任务 ${task_id} 完成:`, result);
    res.json({ status: 'received' });
  }
});
```

---

## 9. 测试验证

### 9.1 基础测试

```bash
# 运行所有测试（76个）
cd amazon-ops-agents
python -m pytest tests/ execution/tests/ tests/reverse/ -v

# 仅运行基础测试
python -m pytest tests/ -v

# 仅运行逆向测试
python -m pytest tests/reverse/ -v

# 带覆盖率报告
python -m pytest tests/ --cov=. --cov-report=html --cov-report=term
```

### 9.2 API端点测试

```bash
# 1. 健康检查
curl http://localhost:8080/health

# 2. 获取Agent列表
curl -X GET http://localhost:8080/api/v1/agents \
  -H "X-API-Key: $AMAZON_OPS_API_KEY"

# 3. 获取路由表
curl -X GET http://localhost:8080/api/v1/routing \
  -H "X-API-Key: $AMAZON_OPS_API_KEY"

# 4. 执行单个任务
curl -X POST http://localhost:8080/api/v1/execute \
  -H "X-API-Key: $AMAZON_OPS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"task": "分析蓝牙耳机的选品机会", "context": {"marketplace": "US"}}'

# 5. 批量执行
curl -X POST http://localhost:8080/api/v1/batch \
  -H "X-API-Key: $AMAZON_OPS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tasks": ["分析选品", "查看广告数据", "监控差评"], "parallel": true}'

# 6. 系统统计
curl -X GET http://localhost:8080/api/v1/stats \
  -H "X-API-Key: $AMAZON_OPS_API_KEY"

# 7. 提交反馈
curl -X POST http://localhost:8080/api/v1/feedback \
  -H "X-API-Key: $AMAZON_OPS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"trace_id": "abc123", "description": "测试反馈", "tags": ["test"]}'
```

### 9.3 性能基准测试

```bash
# 响应时间基准（10次执行）
for i in {1..10}; do
  START=$(date +%s.%N)
  curl -s -X POST http://localhost:8080/api/v1/execute \
    -H "X-API-Key: $AMAZON_OPS_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"task": "分析选品", "context": {}}' > /dev/null
  END=$(date +%s.%N)
  echo "执行${i}: $(echo "$END - $START" | bc)s"
done
```

---

## 10. 逆向测试报告

> 所有逆向测试均通过，详见 `tests/reverse/` 目录。

### 10.1 功能逆向测试（8个测试，全部通过 ✅）

| 测试用例 | 描述 | 通过标准 | 状态 |
|---------|------|---------|------|
| `test_reverse_inquiry_trace` | 询盘追溯：从结果反推完整流程 | trace_id存在，routed_agents非空 | ✅ |
| `test_error_invalid_product_id` | 无效ASIN容错 | 不崩溃，返回合法JSON | ✅ |
| `test_error_empty_product_name` | 空输入边界 | 返回完整结果结构 | ✅ |
| `test_error_malformed_json_context` | 畸形context处理 | 不崩溃 | ✅ |
| `test_extreme_task_length` | 超长文本（3500字符） | 处理正常 | ✅ |
| `test_extreme_batch_size` | 批量50任务 | 全部完成 | ✅ |
| `test_unicode_extreme_input` | Emoji+多语言 | 处理正常 | ✅ |
| `test_negative_numeric_input` | 非法数值 | 不崩溃 | ✅ |

### 10.2 安全逆向测试（9个测试，全部通过 ✅）

| 测试用例 | 攻击向量 | 通过标准 | 状态 |
|---------|---------|---------|------|
| `test_sqli_injection_agent_context` | SQL注入载荷 | 无系统级SQL错误泄漏 | ✅ |
| `test_xss_injection_inquiry` | XSS跨站脚本 | 无恶意JS执行特征 | ✅ |
| `test_api_unauthorized_access` | 无Key/伪造Key | 返回401，错误不含密钥 | ✅ |
| `test_api_key_rate_limit_leak` | 速率限制 | 配置不泄漏 | ✅ |
| `test_hmac_signature_forgery` | HMAC签名伪造 | 伪造/篡改签名被拒绝 | ✅ |
| `test_no_credential_leak_in_results` | 凭证泄漏 | 审计日志正确脱敏 | ✅ |
| `test_no_internal_path_leak` | 内部路径泄漏 | 路径不出现在响应中 | ✅ |
| `test_pii_in_context_not_leaked` | PII数据泄漏 | 信用卡号不明文出现 | ✅ |
| `test_webhook_signature_validation` | Webhook伪造 | 伪造签名被拒绝 | ✅ |

### 10.3 数据逆向测试（7个测试，全部通过 ✅）

| 测试用例 | 场景 | 通过标准 | 状态 |
|---------|------|---------|------|
| `test_data_deletion_recovery` | 数据删除后恢复 | 幂等性正常 | ✅ |
| `test_context_after_data_loss` | 上下文丢失 | 使用默认值正常 | ✅ |
| `test_context_manager_rollback` | 事务回滚 | working/memory状态正确 | ✅ |
| `test_audit_log_immutability` | 审计日志不可篡改 | 只追加，Key脱敏 | ✅ |
| `test_data_consistency_across_parallel` | 并行数据一致性 | 无交叉污染 | ✅ |
| `test_timestamp_consistency` | 时间戳一致性 | ISO格式正确 | ✅ |
| `test_agent_registry_consistency` | Agent注册表 | REGISTRY=AGENTS数量一致 | ✅ |

### 10.4 Agent逆向测试（8个测试，全部通过 ✅）

| 测试用例 | 场景 | 通过标准 | 状态 |
|---------|------|---------|------|
| `test_agent_failure_graceful_degradation` | Agent执行失败 | 整体流程降级正常 | ✅ |
| `test_missing_agent_fallback` | 缺失Agent | 有fallback | ✅ |
| `test_multi_agent_routing_conflict` | 多Agent冲突 | 策略合理，≤10个Agent | ✅ |
| `test_agent_execution_order` | 执行顺序 | 结果数量匹配路由 | ✅ |
| `test_api_retry_with_timeout` | API超时重试 | <30秒完成 | ✅ |
| `test_agent_result_integrity` | 结果完整性 | 必需字段存在 | ✅ |
| `test_router_fallback_local` | Router降级 | reasoning存在 | ✅ |
| `test_router_complexity_score` | 复杂度评分 | 评分逻辑正确 | ✅ |

### 10.5 用户行为逆向测试（9个测试，全部通过 ✅）

| 测试用例 | 场景 | 通过标准 | 状态 |
|---------|------|---------|------|
| `test_abnormal_repeated_same_task` | 连续重复10次 | 无资源泄漏，时间稳定 | ✅ |
| `test_abnormal_rapid_fire` | 1秒内10个不同任务 | 全部完成，无竞争错误 | ✅ |
| `test_abnormal_empty_then_normal` | 异常→正常混合 | 恢复正常 | ✅ |
| `test_concurrent_different_users` | 5用户并发 | 结果独立，无污染 | ✅ |
| `test_concurrent_same_user_same_task` | 同一用户幂等 | 5次结果结构一致 | ✅ |
| `test_network_interruption_recovery` | 网络中断恢复 | 系统继续可用 | ✅ |
| `test_rapid_cancel_resubmit` | 快速重试 | 两次任务独立 | ✅ |
| `test_idle_timeout_recovery` | 空闲超时 | <5秒响应 | ✅ |
| `test_api_response_format_stability` | 响应格式稳定性 | 基础字段一致 | ✅ |

---

## 11. 运维监控

### 11.1 日志配置

```bash
# 设置日志级别
export LOG_LEVEL=DEBUG  # DEBUG | INFO | WARNING | ERROR

# 查看日志
docker compose logs -f api
docker compose logs -f redis --tail=100
```

### 11.2 健康监控

```bash
# 基础健康检查
curl -s http://localhost:8080/health | jq .

# 带告警的健康检查脚本
#!/bin/bash
HEALTH=$(curl -sf http://localhost:8080/health)
if [ $? -ne 0 ]; then
  echo "服务不健康！"
  # 发送告警（钉钉/飞书/企业微信）
  curl -X POST "https://oapi.dingtalk.com/robot/send?access_token=xxx" \
    -H "Content-Type: application/json" \
    -d '{"msgtype": "text", "text": {"content": "Amazon Ops API 不健康！"}}'
fi
```

### 11.3 性能监控指标

| 指标 | 正常范围 | 告警阈值 |
|-----|---------|---------|
| 响应时间P50 | <500ms | >2s |
| 响应时间P95 | <2s | >10s |
| 错误率 | <0.1% | >1% |
| Agent并发数 | <20 | >50 |
| Token消耗/小时 | 动态 | >设定阈值 |

---

## 12. 安全配置

### 12.1 生产环境必做项

```bash
# 1. API Key安全
# - 使用强随机字符串作为 API_KEY
# - 生产环境不要使用默认值或测试Key

# 2. HTTPS
# - 必须使用HTTPS（Let's Encrypt免费证书）
# - 配置 HSTS

# 3. CORS限制
# 编辑 .env:
CORS_ORIGINS=https://your-frontend-domain.com

# 4. Redis密码
REDIS_PASSWORD=your_strong_redis_password

# 5. 速率限制
# 当前默认100请求/分钟，生产环境按需调整
# 在 api_server.py 的 RateLimiter 中配置

# 6. 日志脱敏
# 审计日志已自动对API Key脱敏（显示前8位+***）
```

### 12.2 安全加固命令

```bash
# 防火墙配置（仅开放必要端口）
ufw allow 22/tcp    # SSH
ufw allow 80/tcp     # HTTP
ufw allow 443/tcp    # HTTPS
ufw enable

# Docker安全配置
# 以非root用户运行容器（已在Dockerfile中配置）
# 限制容器内存
docker run --memory=2g amazon-ops-api:latest
```

---

## 13. 故障排查

### 常见问题

#### Q1: 服务启动失败

```bash
# 检查端口占用
lsof -i :8080

# 检查依赖
pip install -r requirements.txt

# 查看详细错误
python api_server.py
```

#### Q2: API返回401未授权

```bash
# 确认环境变量已设置
echo $AMAZON_OPS_API_KEY

# 确认API Key正确
curl -v http://localhost:8080/api/v1/agents \
  -H "X-API-Key: $AMAZON_OPS_API_KEY"
```

#### Q3: Agent执行很慢

```bash
# 检查LLM配置
# 确保DEEPSEEK_API_KEY或OPENAI_API_KEY已配置

# 查看详细日志
export LOG_LEVEL=DEBUG
python api_server.py
```

#### Q4: Docker容器重启后数据丢失

```bash
# 使用持久化卷
docker compose down -v  # 危险：会删除卷
docker compose up -d     # 重新创建

# 建议：定期备份数据目录
tar -czf backup_$(date +%Y%m%d).tar.gz data/
```

#### Q5: Redis连接失败

```bash
# 检查Redis状态
docker compose ps redis
docker compose logs redis

# 测试连接
redis-cli -h redis -p 6379 ping
```

---

## 快速命令参考

```bash
# 启动
docker compose up -d

# 停止
docker compose down

# 重启
docker compose restart api

# 更新代码后重建
git pull
docker compose build --no-cache
docker compose up -d

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f api

# 运行测试
python -m pytest tests/ -v

# 进入容器
docker compose exec api bash
```

---

*最后更新：2026-04-16 | 版本：1.0.0*
