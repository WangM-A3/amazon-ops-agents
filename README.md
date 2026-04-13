# 企业级智能体集群系统

> 基于 **1+N** 架构的智能体协作系统，参考 OpenClaw Main Agent、腾讯ADP Router、智己汽车研发设计集群

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     用户请求 (自然语言)                       │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Orchestrator (指挥智能体)                        │
│  ┌─────────────┐ ┌─────────────┐ ┌──────────────────────┐  │
│  │ 意图识别    │→│ 任务拆解    │→│ 智能体调度 (串行/并行) │  │
│  └─────────────┘ └─────────────┘ └──────────────────────┘  │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┬───────────────┐
        ▼               ▼               ▼               ▼
┌───────────────┐ ┌─────────────┐ ┌───────────────┐ ┌───────────────┐
│Inventory Agent│ │Logistics    │ │Procurement    │ │Finance Agent  │
│(库存智能体)   │ │Agent        │ │Agent          │ │(财务智能体)   │
│               │ │(物流智能体) │ │(采购智能体)   │ │               │
└───────┬───────┘ └──────┬──────┘ └───────┬───────┘ └───────┬───────┘
        │                 │                 │                 │
        ▼                 ▼                 ▼                 ▼
┌───────────────┐ ┌─────────────┐ ┌───────────────┐ ┌───────────────┐
│  ERP Server   │ │ 物流三方API  │ │ SRM Server    │ │ 财务系统API   │
│  WMS Server   │ │ (顺丰/圆通) │ │  ERP Server   │ │               │
└───────────────┘ └─────────────┘ └───────────────┘ └───────────────┘
```

## 目录结构

```
agent-cluster/
├── orchestrator.py          # 指挥智能体（核心调度器）
├── README.md                # 本文件
│
├── specialists/              # 专业智能体
│   ├── inventory_agent.py   # 库存智能体
│   ├── logistics_agent.py   # 物流智能体
│   ├── procurement_agent.py # 采购智能体
│   ├── finance_agent.py     # 财务智能体
│   └── doc_agent.py         # 工艺文档智能体
│
├── mcp_servers/             # MCP协议封装
│   ├── erp_server.py        # ERP系统接口
│   ├── wms_server.py        # WMS仓库管理接口
│   └── srm_server.py        # SRM供应商管理接口
│
├── safety/                  # 安全围栏
│   ├── permission_manager.py # RBAC权限管理
│   ├── audit_logger.py       # 全链路审计日志
│   └── human_loop.py         # 人机回环审批
│
└── config/                  # 配置文件
    ├── agents.yaml          # 智能体定义
    ├── workflows.yaml       # 工作流配置
    └── permissions.yaml     # 权限矩阵
```

## 快速开始

### 环境要求

- Python 3.10+
- 依赖包（可选）：
  ```bash
  pip install pyyaml fastapi uvicorn httpx
  ```

### 运行演示

```bash
# 完整演示（指挥智能体）
cd agent-cluster
python orchestrator.py

# 单独测试各智能体
python -m specialists.inventory_agent
python -m specialists.procurement_agent
python -m specialists.finance_agent
```

## 核心模块详解

### 1. 指挥智能体 (orchestrator.py)

**职责**：不直接干活，只做调度

```
用户输入 → 意图识别 → 任务拆解 → 智能体分发 → 结果汇总 → 返回
```

**意图识别示例**：

| 用户输入 | 识别意图 | 调度智能体 |
|---------|---------|-----------|
| "查询SKU001库存" | stock_query | inventory_agent |
| "向SUP001采购轴承" | purchase | procurement_agent, finance_agent |
| "查下物流运费" | logistics | logistics_agent |
| "帮我查库存，缺货就补货" | mixed | inventory + procurement |

**支持协作模式**：

```python
# 串行：指挥 → 查库存 → 判断 → 触发采购
# 并行：同时呼叫物流 + 财务 → 综合决策
```

### 2. 专业智能体

#### 库存智能体 (inventory_agent.py)

```python
agent = InventoryAgent(user_role="warehouse_operator")
result = await agent.query_stock(sku="SKU001")
# → 返回: 库存量、状态、告警、补货建议
```

核心能力：
- 多维度库存查询（SKU/仓库/状态）
- 安全库存计算（统计学公式：SS = Z × σ × √LT）
- 补货建议自动生成
- 低库存告警

#### 物流智能体 (logistics_agent.py)

```python
agent = LogisticsAgent()
result = await agent.query_freight(
    origin="上海", destination="北京", weight=500
)
# → 返回: 多承运商报价、最优路线规划
```

核心能力：
- 运费多承运商比较
- 物流路线规划（碳排放、成本）
- 实时物流追踪

#### 采购智能体 (procurement_agent.py)

```python
agent = ProcurementAgent(user_role="procurement_manager")
result = await agent.place_order(
    supplier_id="SUP001",
    items=[{"sku": "SKU001", "quantity": 100, "unit_price": 50}],
)
# → 返回: 订单ID，触发人机审批（金额>5万）
```

核心能力：
- 供应商智能推荐（综合评分）
- 采购申请创建
- **高风险**：金额>5万自动触发人机回环审批

#### 财务智能体 (finance_agent.py)

```python
agent = FinanceAgent(user_role="finance_manager")
result = await agent.audit_payment(
    payment_id="PAY001", amount=8000,
    payee="华东轴承有限公司",
)
# → 返回: 自动审核结果（规则引擎）
```

核心能力：
- 预算查询与分析
- 付款自动审核（风险评分）
- 财务报表生成

#### 工艺文档智能体 (doc_agent.py)

```python
agent = DocumentAgent(user_role="procurement_manager")
result = await agent.generate_process_sheet(item_id="BOM-ASSY-001")
# → 返回: 工艺卡文档（含工序、物料、BOM）
```

核心能力：
- 截图填表（OCR字段提取）
- 工艺卡/BOM/采购申请单生成
- PLM系统集成

### 3. MCP协议封装

基于 Model Context Protocol 标准接口：

```python
# 工具注册
"erp.query_stock"          # 库存查询
"erp.calculate_safety_stock" # 安全库存
"srm.search_suppliers"     # 供应商搜索
"wms.transfer_stock"       # 库位调拨
```

每个MCP Server实现：
- 工具注册表
- 参数校验
- 异步执行
- 错误处理

### 4. 安全围栏

#### 权限管理 (permission_manager.py)

```python
# RBAC矩阵示例
admin          → 所有权限
procurement_manager → 采购+库存查询
warehouse_operator  → 库存操作
viewer             → 只读权限
```

#### 审计日志 (audit_logger.py)

```python
# 追踪能力
- trace_id/span_id 全链路追踪
- PII自动脱敏（邮箱/手机/身份证/银行卡）
- SOC 2 合规报告生成
- 慢操作告警 (>5s)
```

#### 人机回环 (human_loop.py)

```python
# 风险评估触发审批
RiskLevel.LOW     → 自动批准
RiskLevel.MEDIUM  → 记录日志
RiskLevel.HIGH    → 人工审批
RiskLevel.CRITICAL → 严谨审批

# 支持渠道：控制台/飞书/邮件/Webhook
```

## 配置说明

### agents.yaml - 智能体定义

```yaml
orchestrator:
  name: "企业智能调度中心"
  model: "混元-pro"
  capabilities:
    - intent_understanding
    - task_decomposition
```

### workflows.yaml - 工作流配置

```yaml
stock_replenishment:
  steps:
    - agent: inventory_agent
      action: query_stock
    - agent: procurement_agent
      action: place_order
      condition: "needs_replenishment"
      requires_approval: true
```

### permissions.yaml - 权限矩阵

```yaml
roles:
  procurement_manager:
    permissions:
      - procurement_agent.place_order  # 金额阈值触发审批
      - finance_agent.query_budget
```

## 生产部署建议

### 1. 模型层接入

```python
# 意图识别可替换为LLM调用
class IntentRecognizer:
    async def recognize(self, text: str) -> Intent:
        # 调用混元/文心/开源模型
        response = await llm.chat(
            model="混元-pro",
            messages=[{"role": "user", "content": f"识别意图: {text}"}]
        )
        return parse_intent(response)
```

### 2. MCP Server接入

```python
# 替换模拟数据为真实ERP/SRM API
class ERPService:
    async def query_stock(self, sku: str):
        # 真实ERP API调用
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://erp.company.com/api/stock/{sku}",
                headers={"Authorization": f"Bearer {api_token}"}
            )
            return resp.json()
```

### 3. 高可用部署

```bash
# Docker Compose 部署
services:
  orchestrator:
    image: agent-cluster:latest
    ports: ["8080:8080"]

  mcp-erp:
    image: erp-mcp-server:latest
    ports: ["8081:8081"]

  mcp-srm:
    image: srm-mcp-server:latest
    ports: ["8082:8082"]
```

### 4. 监控接入

```python
# Prometheus 指标
metrics = {
    "agent_requests_total": Counter,
    "agent_latency_seconds": Histogram,
    "approval_pending_gauge": Gauge,
    "active_sessions": Gauge,
}
```

## 安全设计

| 维度 | 措施 |
|------|------|
| 认证 | JWT Token + 角色绑定 |
| 授权 | RBAC 权限矩阵 |
| 审计 | 全链路JSONL日志 + SOC2报告 |
| 数据 | PII自动脱敏 |
| 审批 | 人机回环（高风险操作）|
| 网络 | MCP四层隔离 |

## License

MIT
