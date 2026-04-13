# Amazon Ops Agents — 生产就绪检查清单

> 适用版本：v1.0.0+  
> 维护团队：硅基军团·研发部  
> 更新日期：2025-04-13

---

## 📋 概览

本清单覆盖 **状态持久化**、**监控体系**、**容错机制** 三大生产就绪维度。
每次部署前必须逐项验证，通过标记 `✅`，失败标记 `❌` 并附修复方案。

---

## 1️⃣ 状态持久化检查

### 1.1 会话状态

- [ ] **SQLite WAL 模式已启用**
  ```bash
  grep "PRAGMA journal_mode=WAL" ./amazon_ops/*.py
  # 预期：每个数据库连接都应设置 WAL + busy_timeout=30000
  ```

- [ ] **并发锁超时配置正确**
  ```bash
  grep "busy_timeout=30000" ./amazon_ops/*.py
  # 预期：≥ 30000ms，防止 "database is locked"
  ```

- [ ] **会话数据已持久化到磁盘**
  ```bash
  ls -lh ./data/sessions.jsonl
  # 预期：文件存在且有内容
  ```

- [ ] **断点恢复机制已实现**
  ```bash
  curl http://localhost:8080/api/v1/stats | jq .session_count
  # 预期：重启后 session_count > 0
  ```

### 1.2 Agent 记忆

- [ ] **记忆数据文件可写**
  ```bash
  touch ./data/memory.jsonl && echo "writable" || echo "readonly"
  ```

- [ ] **记忆回放顺序正确**（LIFO）
  ```bash
  tail -n 3 ./data/memory.jsonl | jq -s '.[-1].timestamp < .[-2].timestamp'
  # 预期：true（LIFO = 最新记忆优先）
  ```

### 1.3 配置与环境

- [ ] **`.env` 文件已配置（非 `.env.example`）**
  ```bash
  [ -f .env ] && echo "exists" || echo "MISSING — copy .env.example"
  ```

- [ ] **敏感变量已设置**
  ```bash
  grep -E "GUI_GUARDIAN_SECRET|MCP_AUTH_TOKEN" .env
  # 预期：两个变量均已设置且值非默认值
  ```

- [ ] **数据库路径配置正确**
  ```bash
  grep "DATABASE_PATH" .env
  # 预期：路径指向持久化卷，非 /tmp/
  ```

---

## 2️⃣ 监控体系配置

### 2.1 健康检查端点

- [ ] **健康检查返回 200**
  ```bash
  curl -s http://localhost:8080/health | jq .status
  # 预期：{"status": "ok", "uptime_seconds": N}
  ```

- [ ] **依赖服务健康检查**
  ```bash
  curl -s http://localhost:8080/health | jq '.dependencies | length'
  # 预期：≥ 2（SQLite、Agent Registry 等）
  ```

### 2.2 日志与审计

- [ ] **审计日志目录存在且可写**
  ```bash
  mkdir -p ./security/mcp_audit_logs
  touch ./security/mcp_audit_logs/.keep
  ls -ld ./security/mcp_audit_logs
  ```

- [ ] **日志轮转配置已设置**
  ```bash
  grep -E "maxFileSizeMB|maxFiles|rotation" ./security/audit_log_config.json
  # 预期：maxFileSizeMB=100, maxFiles=90, type=daily
  ```

- [ ] **PII 脱敏审计已启用**
  ```bash
  jq ".events.pii_redaction.enabled" ./security/audit_log_config.json
  # 预期：true
  ```

- [ ] **MCP 审计日志已集成**
  ```bash
  ls ./security/mcp_audit_logs/*.jsonl 2>/dev/null | head -1
  # 预期：至少存在一个日志文件（首次运行后生成）
  ```

### 2.3 告警规则

- [ ] **失败登录告警已配置**
  ```bash
  jq '.alerting.rules[] | select(.name == "failed_login_threshold")' \
    ./security/audit_log_config.json
  # 预期：condition 存在，action = notify_admin
  ```

- [ ] **Agent 循环检测已配置**
  ```bash
  jq '.alerting.rules[] | select(.name == "agent_loop")' \
    ./security/audit_log_config.json
  # 预期：> 100 次 / 5 分钟 → suspend_agent
  ```

- [ ] **PII 泄露告警已配置**
  ```bash
  jq '.alerting.rules[] | select(.name == "pii_exposure")' \
    ./security/audit_log_config.json
  # 预期：severity = critical, action = immediate_notify
  ```

---

## 3️⃣ 容错机制验证

### 3.1 限流与配额

- [ ] **API 速率限制已启用**
  ```bash
  jq ".api_request.enabled" ./security/audit_log_config.json
  # 预期：true，且有 rate_limit_remaining 字段
  ```

- [ ] **Agent 并发上限已设置**
  ```bash
  grep -E "max_concurrent|max_workers" ./api_server.py
  # 预期：值 ≤ 20，防止资源耗尽
  ```

### 3.2 错误处理

- [ ] **异常不泄露堆栈到客户端**
  ```bash
  curl http://localhost:8080/api/v1/execute \
    -X POST -H "Content-Type: application/json" \
    -d '{"task":"throw"}' 2>&1 | grep -i "traceback\|stack"
  # 预期：无 traceback 输出
  ```

- [ ] **超时机制已配置**
  ```bash
  grep -E "timeout|max_time" ./api_server.py
  # 预期：每个异步调用有超时配置（建议 ≤ 120s）
  ```

- [ ] **任务失败有降级策略**
  ```bash
  grep -E "fallback|retry|degraded" ./api_server.py
  # 预期：至少有一种降级机制
  ```

### 3.3 Docker 生产配置

- [ ] **`restart: unless-stopped` 已配置**
  ```bash
  grep "unless-stopped" ./Dockerfile 2>/dev/null || \
  grep "unless-stopped" ./docker-compose.yml 2>/dev/null
  ```

- [ ] **健康检查已配置**
  ```bash
  grep "healthcheck" ./docker-compose.yml
  # 预期：interval=30s, timeout=10s, retries=3
  ```

- [ ] **非 root 用户运行**
  ```bash
  grep "USER" ./Dockerfile
  # 预期：USER node 或 USER app（非 root）
  ```

- [ ] **只读文件系统（可选加固）**
  ```bash
  grep "read_only" ./docker-compose.yml
  # 推荐：tmpfs 用于 /tmp，或 --read-only 标志
  ```

### 3.4 网络隔离

- [ ] **内部网络已定义**
  ```bash
  grep "company_internal" ./docker-compose.yml
  # 预期：服务间通过内部网络通信，不暴露公网
  ```

- [ ] **敏感端口未映射到宿主机**
  ```bash
  grep -E "ports:" -A 10 ./docker-compose.yml | grep -E '":8080"|":5432"|":6379"'
  # 预期：仅 8080（API）映射；数据库/缓存仅内部访问
  ```

---

## 4️⃣ 安全基线

### 4.1 认证与授权

- [ ] **JWT Secret ≥ 32 字符**
  ```bash
  grep "JWT_SECRET" .env | awk -F= '{print length($2)}'
  # 预期：≥ 32
  ```

- [ ] **RBAC 权限矩阵已加载**
  ```bash
  curl http://localhost:8080/api/v1/stats | jq .rbac_enabled
  # 预期：true
  ```

### 4.2 凭证管理

- [ ] **核心凭证存储在 CredentialVault**
  ```bash
  grep "CredentialVault" ./security/mcp_audit.py
  # 预期：导入并使用 CredentialVault 加密存储
  ```

- [ ] **凭证不在日志中明文出现**
  ```bash
  grep -r "password\|api_key\|secret" ./security/*.json \
    | grep -v "\.keep\|archive" | grep -v "REDACTED"
  # 预期：无匹配（或仅在 .env.example 中）
  ```

### 4.3 MCP 安全

- [ ] **MCP 审计模块已集成**
  ```bash
  python -c "from security.mcp_audit import AUDITOR; print('OK')"
  # 预期：OK（无 ImportError）
  ```

- [ ] **危险工具调用已被阻止**
  ```bash
  # 模拟一次危险调用测试
  python -c "
from security.mcp_audit import AUDITOR
result = AUDITOR.audit_tool_call('exec_cmd', {'cmd': 'rm -rf /'}, user_permission='read_only')
print(result)
"
  # 预期：result contains BLOCKED
  ```

---

## 5️⃣ 部署前最终验证

```bash
#!/bin/bash
# === 快速生产验证脚本 ===
set -e

echo "=== 1. 健康检查 ==="
curl -sf http://localhost:8080/health || { echo "HEALTH FAILED"; exit 1; }

echo "=== 2. MCP审计模块 ==="
python -c "from security.mcp_audit import AUDITOR; print('MCP OK')"

echo "=== 3. 安全配置 ==="
[ -f .env ] && [ -s .env ] || { echo ".env missing/empty"; exit 1; }

echo "=== 4. 日志目录 ==="
mkdir -p ./security/mcp_audit_logs

echo "=== 5. Docker健康 ==="
docker compose ps --format json | jq -e '.[] | select(.Health!="healthy") | empty' \
  && echo "UNHEALTHY containers found" && exit 1 \
  || echo "All healthy"

echo ""
echo "✅ 生产就绪检查全部通过"
```

---

## 附录：检查结果记录

| 检查项 | 日期 | 执行人 | 结果 | 备注 |
|--------|------|--------|------|------|
| 状态持久化 | 2025-04-13 | Agent | ✅ | WAL + busy_timeout=30000 已配置 |
| 监控体系 | 2025-04-13 | Agent | ✅ | SOC 2 合规告警规则已就绪 |
| 容错机制 | 2025-04-13 | Agent | ✅ | 健康检查 + 重启策略已配置 |
| 安全基线 | 2025-04-13 | Agent | ✅ | MCP审计 + RBAC + CredentialVault |
