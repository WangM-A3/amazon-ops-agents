# 亚马逊运营硅基军团 — Railway 云端部署指南

> 适用于亚马逊运营硅基军团系统的公网部署
> 推荐平台：Railway（免费额度 $5/月，无需信用卡）

---

## 目录

1. [为什么选择 Railway](#1-为什么选择-railway)
2. [快速部署（推荐）](#2-快速部署推荐)
3. [详细部署步骤](#3-详细部署步骤)
4. [环境变量配置](#4-环境变量配置)
5. [自定义域名配置](#5-自定义域名配置)
6. [GitHub Actions 自动部署](#6-github-actions-自动部署)
7. [监控与日志](#7-监控与日志)
8. [故障排查](#8-故障排查)

---

## 1. 为什么选择 Railway

| 特性 | Railway | 阿里云ECS | 腾讯云CVM | Fly.io |
|------|---------|----------|----------|--------|
| 免费额度 | $5/月 | 无（需付费） | 无（需付费） | $5/月 |
| 免费数据库 | 500小时/月 | 无 | 无 | 无 |
| SSL自动证书 | ✅ | 需配置 | 需配置 | ✅ |
| 自定义域名 | ✅ 免费 | 需额外购买 | 需额外购买 | ✅ |
| 国内访问速度 | 一般 | 极快 | 极快 | 一般 |
| 无需信用卡 | ✅ | ❌ | ❌ | ❌ |
| Docker支持 | ✅ 原生 | ✅ | ✅ | ✅ |
| 亚太节点 | 可选香港 | ✅ | ✅ | ❌ |

**推荐理由**：
- 🚀 开箱即用，5分钟完成部署
- 💰 免费额度充足（500小时 = 约20天24小时运行）
- 🔒 自动HTTPS，零配置
- 🐳 完美支持现有 Dockerfile
- 🔄 支持 GitHub Actions 自动化部署

---

## 2. 快速部署（推荐）

### 前置条件
- GitHub 账号
- Railway 账号（https://railway.app，使用 GitHub OAuth 注册）

### 一键部署命令

```bash
# 1. 克隆仓库
git clone https://github.com/WangM-A3/amazon-ops-agents.git
cd amazon-ops-agents

# 2. 安装 Railway CLI
npm install -g @railway/cli

# 3. 浏览器登录（自动弹出）
railway login

# 4. 初始化项目
railway init

# 5. 配置环境变量（至少配置以下）
railway variables set AMAZON_OPS_API_KEY your_api_key
railway variables set AMAZON_OPS_API_SECRET your_api_secret
railway variables set DEEPSEEK_API_KEY your_deepseek_key

# 6. 部署！
railway up

# 7. 获取访问地址
railway domain
```

部署完成后，访问 `https://your-project.railway.app/health` 验证服务状态。

---

## 3. 详细部署步骤

### 步骤 1：注册 Railway 账号

1. 访问 https://railway.app
2. 点击 "Login" → "Continue with GitHub"（无需信用卡）
3. 授权 GitHub 访问

### 步骤 2：安装 Railway CLI

```bash
# npm 安装（推荐）
npm install -g @railway/cli

# 验证安装
railway --version
```

### 步骤 3：本地登录

```bash
railway login
# 会自动打开浏览器进行 GitHub OAuth 授权
```

### 步骤 4：创建/链接项目

**方式 A：从现有 GitHub 仓库部署（推荐）**
```bash
# 在 Railway Dashboard 中：
# 1. 点击 "New Project" → "Deploy from GitHub repo"
# 2. 选择 WangM-A3/amazon-ops-agents 仓库
# 3. Railway 自动检测 Dockerfile 并构建
```

**方式 B：使用 CLI 部署本地代码**
```bash
cd amazon-ops-agents
railway init
railway up
```

### 步骤 5：配置环境变量

Railway Dashboard → 选择项目 → "Variables" 标签页

**必需变量**：
```
AMAZON_OPS_API_KEY=your_api_key
AMAZON_OPS_API_SECRET=your_api_secret
```

**至少一个 LLM Provider**：
```
# DeepSeek（推荐，便宜 + 长上下文）
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx

# 或 OpenAI
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx

# 或 Anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
```

**可选变量**：
```
LOG_LEVEL=INFO
DEBUG=false
CORS_ORIGINS=https://your-domain.com
```

### 步骤 6：配置 Redis（可选，但推荐）

Railway 提供免费 Redis 实例：
```bash
# 在 Railway Dashboard 中：
# 1. 点击项目 → "Add Plugin" → "Redis"
# 2. Railway 自动注入 REDIS_URL 环境变量
```

### 步骤 7：验证部署

```bash
# 获取部署 URL
railway domain

# 健康检查
curl https://your-project.railway.app/health

# 查看日志
railway logs
```

---

## 4. 环境变量配置

### 完整环境变量列表

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `AMAZON_OPS_API_KEY` | ✅ | - | API 认证密钥 |
| `AMAZON_OPS_API_SECRET` | ✅ | - | API 认证密钥 |
| `DEEPSEEK_API_KEY` | 推荐 | - | DeepSeek LLM 密钥 |
| `OPENAI_API_KEY` | 可选 | - | OpenAI LLM 密钥 |
| `ANTHROPIC_API_KEY` | 可选 | - | Anthropic LLM 密钥 |
| `LOG_LEVEL` | 否 | INFO | 日志级别 |
| `DEBUG` | 否 | false | 调试模式 |
| `CORS_ORIGINS` | 否 | * | 允许的跨域来源 |
| `REDIS_URL` | 否 | 内置 | Redis 连接地址 |

### 批量导入环境变量

```bash
# 从 .env 文件导入
railway variables -f .env

# 或逐个设置
railway variables set AMAZON_OPS_API_KEY your_key
railway variables set AMAZON_OPS_API_SECRET your_secret
```

---

## 5. 自定义域名配置

### Railway 绑定自定义域名（免费SSL）

1. **Railway Dashboard** → 项目 → **Settings** → **Networking**
2. 点击 **"Generate Domain"** 或 **"Add Custom Domain"**
3. 输入你的域名（如 `api.yourdomain.com`）
4. 在你的 DNS 服务商处添加 CNAME 记录：
   ```
   类型: CNAME
   名称: api（或 @）
   目标: your-project.railway.app
   ```
5. 等待 DNS 传播（通常 5-30 分钟）
6. Railway 自动配置 HTTPS 证书

### 推荐域名方案

| 用途 | 域名示例 |
|------|---------|
| API 访问 | `api.amazon-agent.yourdomain.com` |
| 管理后台 | `admin.amazon-agent.yourdomain.com` |
| Webhook | `webhook.amazon-agent.yourdomain.com` |

---

## 6. GitHub Actions 自动部署

### 配置步骤

1. **在 Railway 中创建服务令牌**：
   - 访问 https://railway.app/project/-/settings/tokens
   - 点击 "New Token" → 命名（如 "github-actions"）→ 创建
   - 复制令牌（格式：`RWxxxxxxxx`）

2. **在 GitHub 仓库中添加 Secrets**：
   - 访问 https://github.com/WangM-A3/amazon-ops-agents/settings/secrets/actions
   - 点击 "New repository secret"，添加：
     - `RAILWAY_TOKEN`: 粘贴 Railway 服务令牌
     - `AMAZON_OPS_API_KEY`: 你的 API 密钥
     - `AMAZON_OPS_API_SECRET`: 你的 API 密钥
     - `DEEPSEEK_API_KEY`: 你的 DeepSeek 密钥

3. **推送代码自动部署**：
   ```bash
   git add .
   git commit -m "feat: 配置 Railway 部署"
   git push origin main
   # GitHub Actions 自动触发部署
   ```

### 查看部署状态

- GitHub Actions：https://github.com/WangM-A3/amazon-ops-agents/actions
- Railway Dashboard：https://railway.app/project/-/deployments

---

## 7. 监控与日志

### 实时日志
```bash
railway logs -f
```

### 部署历史
```bash
railway status
railway deployments
```

### 性能监控
Railway Dashboard 提供：
- CPU/内存使用率
- 请求量和响应时间
- 错误率
- 部署历史

### 告警配置（可选）
```bash
# 设置告警（当错误率 > 5% 时通知）
railway alerts create --metric error_rate --threshold 5 --notify email
```

---

## 8. 故障排查

### 常见问题

**Q1: 部署失败，显示 "Build failed"**
```
可能原因：requirements.txt 中有不可安装的包
解决：检查 requirements.txt，确保所有包有兼容版本
```

**Q2: 启动失败，显示 "Module not found"**
```
可能原因：Python 路径问题
解决：Dockerfile 中已设置 PYTHONPATH=/app，确保 WORKDIR 正确
```

**Q3: 健康检查失败**
```
可能原因：服务启动时间超过健康检查超时（30秒）
解决：Railway.toml 中设置更长的 healthcheckTimeout
```

**Q4: LLM API 调用失败**
```
可能原因：API 密钥未配置或过期
解决：在 Railway Variables 中配置 DEEPSEEK_API_KEY 或其他 LLM 密钥
```

**Q5: 国内访问速度慢**
```
原因：Railway 服务器在欧美
解决：
1. 使用香港/新加坡区域（如有）
2. 考虑使用阿里云/腾讯云（需付费但速度快）
3. 配置 CDN 加速（如 Cloudflare）
```

### 调试命令

```bash
# 进入 Railway Shell
railway shell

# 查看环境变量
railway run printenv | grep AMAZON

# 本地运行
railway run python api_server.py

# 重启服务
railway redeploy
```

### Rollback（回滚到上一版本）

```bash
# 查看部署历史
railway deployments

# 回滚到指定版本
railway rollback <deployment_id>
```

---

## 快速参考卡

```bash
# ── 常用命令速查 ─────────────────────────────────────────────────────────────
railway login              # 登录
railway init               # 初始化项目
railway up                 # 部署
railway up --production    # 生产环境部署
railway domain             # 查看访问域名
railway logs -f           # 实时日志
railway status             # 状态
railway redeploy           # 重新部署
railway rollback           # 回滚
railway variables          # 环境变量
railway variables set KEY=VALUE  # 设置变量
railway shell              # 进入容器 Shell
railway run CMD            # 运行命令
railway link PROJECT_ID    # 链接已有项目
```

---

## 费用说明

Railway Starter Plan（免费）：
- **$5/月** 额度（500小时/月的服务时间）
- 支持 1 个 Web Service + 1 个 Database
- 超出按量付费

**估算**：
- 1 个 API 服务（0.5 CPU，512MB 内存）≈ $1-2/月
- + Redis（可选）≈ $1-2/月
- **总费用**：$0-3/月（免费额度内基本免费）

---
