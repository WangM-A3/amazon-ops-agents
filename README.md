# 亚马逊运营硅基军团 (Amazon Operations Silicon Army)

> **Amazon Operations Silicon Army v2.2** — 面向跨境电商卖家的 Multi-Agent 运营系统。
> **1 个幕僚长 (ChiefOfStaff) + 24 个专业 Agent**，覆盖选品 / Listing / 广告 / 库存 / 定价 / 评论 / 品牌 / 数据 / 客服 / 合规 / 竞品情报 / 供应链 / 知识库全链路。

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-92%2F92-green.svg)](./tests)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)

---

## ✨ 核心特性（v2.2）

| 能力 | 说明 |
|---|---|
| 🧠 **经验记忆闭环**（v2.2 新增） | Agent 本地经验库（SQLite）：沉淀运营打法 → 同类任务自动注入 LLM prompt → 打分回写 → 低成功率经验自动停用。**越用越懂这家店** |
| 📊 **真实数据层**（v2.0） | 三级数据源自动降级：CSV/JSON 本地导入（SQLite）→ SP-API 在线 → 模板兜底（明确标注，不伪装） |
| 🤖 **真实 LLM 路由**（v2.0） | LOCAL（零 Token 确定性处理）/ SMALL / LARGE 端云路由；SMALL/LARGE 真实调用 OpenAI 兼容端点（默认 DeepSeek），失败自动回退模板 |
| 🔀 **4 预置工作流** | new_product_launch / ad_optimization / inventory_alert / customer_service |
| ⚖️ **AI 内容合规**（v2.1） | 亚马逊 AI 人物图元数据披露 + TikTok Shop AIGC 标注（双平台新规检查） |
| 📐 **诚实基准** | ProfitOptimizer 同空间/同真值/50 市场×2 场景：拟合友好市场 vs 规则引擎 **+38~55%**（胜率 100%）；明确废弃 v1.x 矮化基准 "+19.5%" 声明 |
| 🧪 **测试基建** | pytest **92/92 全绿** + 自测套件 + 17 项算法测试 |

## 🧑‍💼 团队架构

```
ChiefOfStaff（幕僚长：关键词路由 + 复杂度评分 + 端云路由 + 并行调度）
├── 选品 2   ProductResearch / NicheFinder
├── Listing 3 ListingOptimizer / KeywordResearch / A+Content
├── 广告 2   PPCManager / SponsoredAds
├── 库存 2   InventoryPlanner / FBA Manager
├── 定价 2   PriceOptimizer / Repricing
├── 评论 2   ReviewMonitor / VINE Program
├── 品牌 2   BrandRegistry / HijackerDetector
├── 数据 2   SalesAnalytics / ProfitCalculator
├── 客服 1   CustomerService
├── 合规 2   ComplianceChecker / AccountHealth
├── 情报 1   CompetitorAnalysis
├── GUI 1    GUIAgent（SIMULATE，需人工确认）
├── 供应链 1 SupplyChain
└── 知识库 1 QAAgent
```

## 🚀 快速启动

### 方式 1：一键包（推荐，免安装）
Windows 解压后双击 `start.bat` → 浏览器自动打开操作台 `http://127.0.0.1:8090/docs`。
自带便携 Python 运行时 + 示例数据（雨伞品类），无需安装任何环境。

### 方式 2：源码运行
```bash
# 需要 Python 3.12
pip install -r requirements.txt
python run_ops.py ingest      # 导入 data/sample 示例数据（可选）
python run_ops.py server 8090 # 启动 API Server
# 操作台: http://localhost:8090/docs
```

### 配置 LLM（可选但推荐）
复制 `.env.example` 为 `.env` 并填写：
```ini
DEEPSEEK_API_KEY=sk-xxx          # 或 OPENAI_API_KEY
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
```
不配置也能用：Agent 自动降级为本地模板结果并明确标注"演示数据"。

## 🔌 API 概览

```
GET  /health                      健康检查
GET  /api/v1/agents               24 个 Agent 列表
POST /api/v1/execute              单任务（自动路由 → 并行执行 → 聚合）
POST /api/v1/batch                批量任务
POST /api/v1/workflow             预置工作流（4 个）
GET  /api/v1/stats                系统统计
POST /api/v1/memory/experience    沉淀经验（v2.2）
GET  /api/v1/memory/experience    列出经验（v2.2）
POST /api/v1/memory/rating        打分回写 → 自动淘汰烂经验（v2.2）
GET  /api/v1/audit                审计查询
```
鉴权：`X-API-Key` header（HMAC 签名可选）；限流 100/min/Key。

## 📁 目录结构

```
amazon-ops/
├── agents/           # 24 个 Agent（base/chief/real_data/support）
├── routing/          # 端云路由（task_router / llm_executor / local_executor）
├── llm/              # OpenAI 兼容 LLM 客户端（真实调用）
├── memory/           # 经验记忆闭环（v2.2）
├── execution/        # 算法内核（ProfitOptimizer / IntradayBidder / ConversionPredictor）
├── compliance/       # AI 内容合规规则（v2.1）
├── workflows/        # 4 预置工作流
├── data/             # SQLite 真实数据层（sample 示例数据 / ingest / provider）
├── benchmarks/       # 诚实基准
├── tests/            # 92 项测试
├── api_server.py     # FastAPI 入口
└── run_ops.py        # 统一 CLI（test/selftest/bench/ingest/workflow/server）
```

## 🧪 测试与验证

```bash
python run_ops.py test        # 全量 92 项
python run_ops.py selftest    # 自测 9 项
python run_ops.py bench       # ProfitOptimizer 诚实基准
python run_ops.py po-test     # 算法 17 项
```

## 📋 版本历史

- **v2.2.0 (2026-09)**：经验记忆闭环（memory/ + /api/v1/memory/*）
- v2.1.0：AI 内容合规层（亚马逊/TikTok Shop 双平台 AIGC 标注新规）
- v2.0.0：真实数据层 + 真实 LLM 路由 + 4 工作流修复 + 测试基建 + 诚实基准
- v1.x：框架真实、业务层 Mock 演示壳（已废弃矮化基准声明）

## ⚠️ 诚实声明

- 经验记忆为**半自动闭环**：经验由卖家沉淀、打分淘汰；**自动「报错→学习」进化为零实现**
- IM 远程调度（飞书/微信/WhatsApp）、跨渠道归因引擎、公开爬取竞品情报：**规划中，零实现**
- 所有 Agent 输出携带数据来源标记（真实数据 / 演示数据），不伪装

## 📄 许可

[MIT License](./LICENSE) · 定价方案见 [PRICING.md](./PRICING.md)
