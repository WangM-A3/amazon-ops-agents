# 亚马逊运营硅基军团

> **Amazon Operations Silicon Army** — 面向亚马逊跨境电商卖家的AI运营平台
>
> **1个幕僚长 + 20个专业Agent**，覆盖选品 / Listing优化 / 广告投放 / 库存管理 / 定价策略 / 评论管理 / 品牌保护 / 数据分析 / 客户服务 / 合规风控全链路。

[![GitHub stars](https://img.shields.io/github/stars/yunlü-agent/amazon-ops-agents)](https://github.com/yunlü-agent/amazon-ops-agents)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)

---

## 🎯 定价方案

| 版本 | 价格 | 周期 | 推荐场景 |
|------|------|------|----------|
| **基础版** | ¥599 | 月 | 新手卖家，选品/Listing/广告/库存/定价（5个核心Agent） |
| **专业版** ⭐ | ¥2,999 | 月 | 成长期卖家，+评论/品牌/数据/客服/合规（15个Agent） |
| **企业版** | ¥29,999 | 月 | 大卖家/品牌方，全部20个Agent + 定制开发 + 私有部署 |

详见 [PRICING.md](./PRICING.md)

---

## ⚡ 快速启动

```bash
# 克隆项目
git clone https://github.com/yunlü-agent/amazon-ops-agents.git
cd amazon-ops-agents

# 安装依赖
pip install -r requirements.txt

# 启动服务
python api_server.py
# → 服务地址：http://localhost:8080
```

**API文档**（Swagger UI）：http://localhost:8080/docs

---

## 🏗️ 团队架构

### 幕僚长（ChiefOfStaff）

智能任务调度中心，理解用户意图并分发到专业Agent，支持：
- 自然语言查询全链路数据
- 并行执行 + 结果聚合
- 主动预警异常（库存/差评/跟卖/ACOS/ODR）
- 端云智能路由（零Token消耗优化）

### 20个专业Agent

| 类别 | Agent | 核心能力 |
|------|-------|---------|
| **选品分析** | ProductResearchAgent | 市场趋势、竞品分析 |
| | NicheFinderAgent | 细分市场、机会识别 |
| **Listing优化** | ListingOptimizerAgent | 标题/五点/描述优化 |
| | KeywordResearchAgent | 关键词挖掘、排名追踪 |
| | AContentGeneratorAgent | A+页面内容生成 |
| **广告投放** | PPCManagerAgent | Campaign管理、ACOS优化 |
| | SponsoredAdsAgent | SP/SB/SD广告策略 |
| **库存管理** | InventoryPlannerAgent | 库存预测、安全库存 |
| | FbaManagerAgent | FBA费用优化、货件管理 |
| **定价策略** | PriceOptimizerAgent | 竞品比价、动态定价 |
| | RepricingAgent | BuyBox守价、自动调价 |
| **评论管理** | ReviewMonitorAgent | 评论监控、差评预警 |
| | VINEProgramAgent | Vine计划、催评策略 |
| **品牌保护** | BrandRegistryAgent | 品牌注册、侵权投诉 |
| | HijackerDetectorAgent | 跟卖检测与处理 |
| **数据分析** | SalesAnalyticsAgent | 销售报表、趋势分析 |
| | ProfitCalculatorAgent | 利润计算、ROI分析 |
| **客户服务** | CustomerServiceAgent | 买家消息、退货处理 |
| **合规风控** | ComplianceCheckerAgent | 合规检查、政策预警 |
| | AccountHealthAgent | 账号健康、ODR监控 |

---

## 📌 快速使用示例

### 快速查询（自然语言）

```bash
curl -X POST http://localhost:8080/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "帮我查一下今天美国站的销量", "marketplace": "US"}'
```

### 单Agent调用

```bash
# Listing优化
curl -X POST http://localhost:8080/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "优化蓝牙耳机标题", "sku": "ABC123"}'

# 广告优化
curl -X POST http://localhost:8080/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "我的广告ACOS太高了，怎么优化", "sku": "ABC123"}'

# 差评回复
curl -X POST http://localhost:8080/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "收到一个1星差评，说耳机续航不行，怎么回复", "asin": "B0XXXXXX"}'
```

### 工作流（一键端到端）

```bash
# 新品上架工作流
curl -X POST http://localhost:8080/api/v1/workflow \
  -H "Content-Type: application/json" \
  -d '{"workflow_id": "new_product_launch", "input": {"product_name": "3D打印灯", "marketplace": "US"}}'

# 广告优化工作流
curl -X POST http://localhost:8080/api/v1/workflow \
  -H "Content-Type: application/json" \
  -d '{"workflow_id": "ad_optimization", "input": {"sku": "ABC123", "current_acos": 0.42}}'
```

更多示例见 [examples/](./examples/) 目录。

---

## ✨ 核心功能特性

### 🧠 端云智能路由（v1.1+）
- **LOCAL引擎**：数据提取/格式转换/统计计算，零Token消耗
- **SMALL引擎**：轻量级推理，Qwen-7B级别
- **LARGE引擎**：复杂分析，GPT-4级别
- 自动降级保障，可用性>99%

### 🛡️ 三层安全防护（v1.1+）
- **应用层**：10类危险操作直接拦截（BLOCK）
- **系统层**：5类敏感操作二次确认（CONFIRM）
- **驱动层**：全量操作审计日志

### ⚡ 预置工作流（v1.1+）
| 工作流 | 步骤 | 用途 |
|--------|------|------|
| 🆕 新品上架 | 4步/60s | 选品→关键词→Listing→A+ |
| 📈 广告优化 | 4步/45s | 数据→竞品→策略→ROI |
| 📦 库存预警 | 5步/43s | FBA→预测→补货→供应→报告 |
| 💬 客户服务 | 4步/21s | 分类→检索→回复→审核 |

### 🔗 外部集成
- **Amazon SP-API**（官方API）
- **Helium 10 / Jungle Scout / Keepa**（选品分析）
- **船长ERP / 数字酋长**（数据同步）
- **Google Sheets**（数据导出）
- **钉钉 / 企业微信 / 邮件**（告警通知）

---

## 📁 项目结构

```
amazon-ops-agents/
├── SKILL.md                    # 技能定义（ClawHub发布用）
├── README.md                   # 项目说明
├── CHANGELOG.md                # 版本记录
├── PRICING.md                  # 定价方案
├── LICENSE                     # MIT协议
├── requirements.txt            # Python依赖
├── Dockerfile                  # 生产部署
├── api_server.py              # FastAPI服务（端口8080）
│
├── agents/                     # Agent实现
│   ├── base.py                # Agent基类
│   ├── chief.py               # 幕僚长（任务调度）
│   ├── gui_agent.py           # GUI操作代理（Guardian安全）
│   └── ...
│
├── routing/                   # 路由引擎
│   ├── task_router.py         # 复杂度评分+引擎选择
│   └── local_executor.py      # 本地执行器（零Token）
│
├── security/                  # 安全模块
│   ├── gui_guardian.py        # 三层安全防护
│   └── credential_vault.py    # 凭证加密存储
│
├── workflows/                 # 工作流引擎
│   ├── workflow_engine.py     # 步骤执行+状态追踪
│   └── presets.py             # 预置工作流
│
├── examples/                   # 使用示例
│   ├── README.md              # 示例说明
│   ├── basic/                 # 基础示例
│   │   ├── 01_quick_query.py
│   │   ├── 02_single_agent.py
│   │   └── 03_batch_tasks.py
│   ├── advanced/             # 高级示例
│   │   ├── 01_workflow_launch.py
│   │   ├── 02_multi_agent_chain.py
│   │   └── 03_api_integration.py
│   └── scripts/               # 运维脚本
│       ├── demo_local.sh
│       └── health_check.sh
│
├── tests/                     # 单元测试
│   ├── test_demo.py           # 基础测试
│   ├── test_agents.py         # Agent测试
│   ├── test_router.py         # 路由测试
│   └── test_workflow.py       # 工作流测试
│
└── data/                      # 本地数据存储
```

---

## 🔧 技术栈

| 层级 | 技术 |
|------|------|
| **语言** | Python 3.10+ |
| **框架** | FastAPI + Uvicorn |
| **协议** | Amazon SP-API（官方） |
| **路由** | 关键词匹配 + 复杂度评分 |
| **执行** | async 并发（asyncio） |
| **安全** | HMAC-SHA256 凭证加密 |
| **部署** | Docker + Docker Compose |

---

## 📖 文档

| 文档 | 说明 |
|------|------|
| [examples/README.md](./examples/) | 完整使用示例 |
| [CHANGELOG.md](./CHANGELOG.md) | 版本更新记录 |
| [PRICING.md](./PRICING.md) | 详细定价方案 |
| [IMPROVEMENT_REPORT.md](./IMPROVEMENT_REPORT.md) | v1.1技术改进报告 |

---

## 🐛 测试

```bash
# 运行所有测试
pytest tests/ -v

# 查看测试覆盖率
pytest tests/ --cov=agents --cov=routing --cov=workflows
```

---

## 🌐 ClawHub

本技能包发布于 [ClawHub](https://clawhub.com)，支持扣子平台一键安装。

> 扣子用户可直接在技能商店搜索「亚马逊运营硅基军团」安装使用。

---

## 📄 License

MIT License - 详见 [LICENSE](./LICENSE)
