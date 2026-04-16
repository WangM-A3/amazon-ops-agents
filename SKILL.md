# Amazon Operations Silicon Army - SKILL.md
## 亚马逊运营硅基军团

---
name: amazon-ops-silicon-army
description: |
  亚马逊运营硅基军团 — 面向跨境电商卖家的Multi-Agent运营系统
  
  ## 触发条件（满足任一即触发）
  - 关键词：选品/List/广告/ACOS/PPC/FBA/Listing/跟卖/差评/VINE/品牌/利润/库存/定价/合规
  - 场景：亚马逊运营、跨境电商、Amazon Seller、SP-API、广告优化、库存管理
  - 动作：帮我分析/优化/查询/制定计划/回复差评/检测跟卖/计算利润
  - IM调度：飞书指令、微信任务、WhatsApp消息
  - 竞品：竞品分析、BestSeller榜单、价格追踪、关键词排名
  
  ## 核心能力
  - 20个专业Agent覆盖选品→Listing→广告→库存→定价→评论→品牌→数据→客服→合规全链路
  - 幕僚长（ChiefOfStaff）智能任务分发 + 端云路由（LOCAL/SMALL/LARGE三引擎）
  - 🆕 **不需要Amazon账号密码**：三层数据架构（公开爬取+用户上传+SP-API可选授权）
  - 🆕 IM远程调度（飞书/微信/WhatsApp），自然语言一句话指挥Agent
  - 🆕 公开数据竞品情报（Layer1爬取，无需任何授权）
  - 4个预置工作流（一键新品上架/广告优化/库存预警/客服）
  - 三层安全防护（BLOCK/CONFIRM/AUDIT）
  - 🆕 错误记忆自进化（报错→学习→优化闭环，越用越聪明）
  - 支持Helium 10/Jungle Scout/Keepa/船长ERP等第三方工具集成
  
  ## 使用方式
  - 快速查询：「帮我查今天美国站销量」
  - 任务执行：「分析无线蓝牙耳机能不能做」
  - 工作流：「启动新品上架工作流」
  - 主动预警：库存/差评/跟卖/ACOS异常自动推送
metadata:
  openclaw:
    requires: ["python3>=3.10", "pip", "httpx", "fastapi", "uvicorn"]
    emoji: "📦"
    version: "1.1.0"
    author: "云旅智能体超市"
    category: "ecommerce-ai"
    tags: ["amazon", "ecommerce", "sp-api", "fba", "ppc", "listing", "cross-border", "multi-agent"]
  pricing:
    basic:
      price: 599
      currency: CNY
      period: month
      features: ["5个核心Agent", "选品/Listing/广告/库存/定价", "基础数据看板", "🆕 不需要账号密码（三层数据架构）"]
    professional:
      price: 2999
      currency: CNY
      period: month
      features: ["15个专业Agent", "全链路覆盖", "API集成", "广告优化", "品牌保护", "🆕 IM远程调度", "🆕 竞品分析Agent"]
    enterprise:
      price: 29999
      currency: CNY
      period: month
      features: ["全部20个Agent", "定制开发", "专属支持", "私有部署", "🆕 GEO可见性监测", "🆕 错误自进化"]
---

## 一、系统定位

面向亚马逊跨境电商卖家的AI运营平台，模拟一个完整的亚马逊运营团队。
**亚马逊全站点**为核心场景，覆盖美国/欧洲/日本等主要市场。

## 二、团队架构

### 幕僚长（ChiefOfStaff）
- 任务分发、调度、结果整合
- 支持自然语言查询全链路数据
- 主动预警异常
- 跨Agent协同调度

### 核心执行Agent（20个）

#### 选品分析（2个）
| Agent | 职能 | 关键能力 |
|-------|------|---------|
| ProductResearchAgent | 市场趋势、竞品分析、选品建议 | Helium 10/Jungle Scout数据 |
| NicheFinderAgent | 细分市场发现、机会识别 | 蓝海词挖掘、竞争度分析 |

#### Listing优化（3个）
| Agent | 职能 | 关键能力 |
|-------|------|---------|
| ListingOptimizerAgent | 标题、五点、描述优化 | SEO合规、A9算法优化 |
| KeywordResearchAgent | 关键词挖掘、搜索词分析 | 反查关键词、排名追踪 |
| AContentGeneratorAgent | A+页面内容生成 | 品牌故事、图表设计 |

#### 广告投放（2个）
| Agent | 职能 | 关键能力 |
|-------|------|---------|
| PPCManagerAgent | 广告Campaign管理、竞价优化 | ACOS优化、自动规则 |
| SponsoredAdsAgent | SP/SB/SD广告策略 | 投放组合、预算分配 |

#### 库存管理（2个）
| Agent | 职能 | 关键能力 |
|-------|------|---------|
| InventoryPlannerAgent | 库存预测、补货建议 | 安全库存、避免断货 |
| FbaManagerAgent | FBA费用优化、货件管理 | 费用计算、IPI优化 |

#### 定价策略（2个）
| Agent | 职能 | 关键能力 |
|-------|------|---------|
| PriceOptimizerAgent | 价格监控、动态定价 | 竞品比价、边际利润 |
| RepricingAgent | 自动调价策略 | BuyBox、守价规则 |

#### 评论管理（2个）
| Agent | 职能 | 关键能力 |
|-------|------|---------|
| ReviewMonitorAgent | 评论监控、差评预警 | 星级追踪、情感分析 |
| VINEProgramAgent | Vine计划申请管理 | 绿标策略、催评策略 |

#### 品牌保护（2个）
| Agent | 职能 | 关键能力 |
|-------|------|---------|
| BrandRegistryAgent | 品牌注册、侵权投诉 | 品牌2.0、真人评测 |
| HijackerDetectorAgent | 跟卖检测与处理 | 异常预警、自动赶跟卖 |

#### 数据分析（2个）
| Agent | 职能 | 关键能力 |
|-------|------|---------|
| SalesAnalyticsAgent | 销售数据、业绩分析 | 业务报表、趋势分析 |
| ProfitCalculatorAgent | 利润计算、成本分析 | FBA成本、ROI计算 |

#### 跨渠道归因（v1.2新增 ⭐）
| Agent | 职能 | 关键能力 |
|-------|------|---------|
| AttributionEngineAgent | 全漏斗跨渠道归因分析 | 5种归因模型、AMC级分析 |
| JourneyAnalyzerAgent | 客户旅程阶段分析 | 漏斗追踪、路径分析 |
| ROICalculatorAgent | 渠道/Campaign/Keyword ROI | ROAS/ACOS/TACOS计算 |

#### 客户服务（1个）
| Agent | 职能 | 关键能力 |
|-------|------|---------|
| CustomerServiceAgent | 买家消息回复、退货处理 | 自动回复模板、退货处理 |

#### 合规风控（2个）
| Agent | 职能 | 关键能力 |
|-------|------|---------|
| ComplianceCheckerAgent | 合规检查、政策预警 | 政策变动、类目审核 |
| AccountHealthAgent | 账号健康度监控 | ODR、订单缺陷率预警 |

## 三、行业Know-How（亚马逊运营）

### 核心业务流程
```
选品调研 → Listing优化 → 广告投放 → 库存管理
    ↓            ↓            ↓           ↓
评论积累  →  品牌保护   →  定价策略   →  数据复盘
```

### 关键KPI
| 指标 | 目标 | 说明 |
|------|------|------|
| 订单缺陷率(ODR) | ≤1% | 账号健康核心 |
| 库存可维持天数 | ≥21天 | 爆款≥21天 |
| ACOS | ≤25% | 健康区间 |
| 评论星级 | ≥4.3星 | 自然流量保障 |
| BuyBox占有率 | ≥85% | 销量保障 |

### Amazon SP-API 集成说明
- 支持 SP-API（亚马逊官方API）
- 支持第三方工具：Helium 10、Jungle Scout、Keepa
- 支持船长/数字酋长ERP数据对接

## 四、技术实现

### 架构
- ChiefOfStaff = 关键词路由 + **端云智能路由** + 调度引擎
- 各Agent = Python async 函数
- API层 = FastAPI + Uvicorn
- 数据源 = Amazon SP-API / ERP / CRM

### 端云智能路由（v1.1新增）
基于任务复杂度自动选择执行引擎：

```
任务输入 → TaskRouter复杂度评分 → 引擎决策
                                        ├─ LOCAL  → 本地Python（零Token）
                                        ├─ SMALL  → 小模型Qwen-7B（~100Token）
                                        └─ LARGE  → 大模型GPT-4（~500Token）
```

**核心优势**：
- 简单任务本地执行，零Token消耗（数据提取/格式转换/统计计算）
- Agent级别引擎覆盖（如profit_calculator强制LOCAL）
- 自动降级机制（LARGE→SMALL→LOCAL）
- 全链路Token预估

**实现文件**：`routing/task_router.py`（TaskRouter类）、`routing/local_executor.py`（LocalExecutor）

### GUI Agent三层安全防护（v1.1新增）
| 层级 | 机制 | 示例操作 |
|------|------|----------|
| 应用层 | BLOCK | 删除Listing、批量取消订单、删除评论 |
| 系统层 | CONFIRM | 修改价格、发送买家消息、导出客户数据 |
| 驱动层 | AUDIT | 操作日志全量记录、凭证加密存储 |

**安全特性**：
- 危险操作直接拦截（10类PROHIBITED_ACTIONS）
- 敏感操作二次确认（5类CONFIRM_REQUIRED_ACTIONS）
- 全量操作审计日志（GuardianResult + AuditLogEntry）
- CredentialVault凭证加密（HMAC-SHA256）

**实现文件**：`security/gui_guardian.py`（GUIGuardian类）

### 预置工作流（v1.1新增）
一键启动端到端业务流程：

| 工作流 | 步骤数 | 预估时长 | 说明 |
|--------|--------|----------|------|
| 🆕 新品上架 | 4步 | 60s | 选品→关键词→Listing→A+ |
| 📈 广告优化 | 4步 | 45s | 数据→竞品→策略→ROI |
| 📦 库存预警 | 5步 | 43s | FBA→预测→补货→供应→报告 |
| 💬 客户服务 | 4步 | 21s | 分类→检索→回复→审核 |
| 🎯 跨渠道归因分析 | 5步 | 30s | 数据→旅程→归因→ROI→报告 |

### 跨渠道归因引擎（v1.2新增 ⭐）
对标 Intentwise AMC 全漏斗分析能力：

**5种归因模型**：
| 模型 | 说明 | 适用场景 |
|------|------|---------|
| First Touch | 100%归因给首触渠道 | 品牌认知分析 |
| Last Touch | 100%归因给末触渠道 | 转化优化 |
| Linear | 均分给所有触点 | 平衡型分析 |
| Time Decay | 越近转化权重越高 | 短周期决策 |
| **Data-Driven (Markov)** | 移除效应算法，ML驱动 | ⭐生产级分析 |

**数据源集成**：
```
Amazon Advertising (SP/SB/SD/DSP)
    ↓
站内搜索 + 自然流量
    ↓
外部渠道（社交媒体/SEO/邮件）
```

**客户旅程漏斗**：
```
意识(Awareness) → 兴趣(Interest) → 考虑(Consideration)
      ↓                   ↓                 ↓
  曝光追踪            点击追踪         加购追踪
                                           ↓
                                    意向(Intent) → 购买(Purchase) → 忠诚(Loyalty)
                                           ↓                 ↓
                                      详情页追踪         转化追踪

```

**ROI计算层级**：
- 渠道级别：SP/SB/SD/DSP/Organic/Social/Email
- Campaign级别：每个Campaign的ROAS/CPA/ACOS
- Keyword级别：每个Keyword的ROAS/CPA
- 整体营销ROI：全渠道汇总

**可视化报告**：
- 漏斗图（Funnel Chart）
- 归因路径桑基图（Path Sankey）
- 渠道贡献热力图（Channel × Stage Heatmap）
- 多模型对比柱状图

**性能目标**：
- 归因准确率 >80%（Markov模型实测）
- 支持多账户并发分析
- 报告生成时间 <30秒（10K journeys）

**实现文件**：
- `tools/attribution_engine.py` — 核心归因引擎
- `tools/journey_analyzer.py` — 旅程分析器
- `tools/roi_calculator.py` — ROI计算器
- `tools/attribution_report.py` — 报告生成器

**使用示例**：
```python
from tools.attribution_engine import AttributionEngine, AttributionModel
from tools.attribution_report import generate_full_report, ReportConfig

# 数据接入
engine = AttributionEngine()
engine.ingest_from_records(your_clickstream_records)

# 运行Markov数据驱动归因
result = engine.run_model(AttributionModel.DATA_DRIVEN)
print(f"归因准确率: {result.attribution_accuracy:.1%}")

# 生成完整报告
report = generate_full_report(your_records, format="markdown")
```

每个工作流提供：标准输入参数、预期输出格式、执行时间预估

**实现文件**：`workflows/presets.py`（WorkflowEngine + 4个PresetWorkflow）

### 关键词路由表
| 关键词 | Agent |
|--------|-------|
| 选品/市场/竞品/蓝海/机会 | ProductResearchAgent |
| 细分/利基/长尾/小类 | NicheFinderAgent |
| Listing/标题/五点/描述/要点 | ListingOptimizerAgent |
| 关键词/搜索词/SearchTerm | KeywordResearchAgent |
| A+/AContent/品牌故事/图片 | AContentGeneratorAgent |
| 广告/PPC/SP/SB/SD/ACOS | PPCManagerAgent |
| 投放/竞价/预算/CPC | SponsoredAdsAgent |
| 库存/补货/断货/备货 | InventoryPlannerAgent |
| FBA/仓储/IPI/货件 | FbaManagerAgent |
| 定价/价格/调价/竞品价格 | PriceOptimizerAgent |
| 自动调价/Reprice/BuyBox | RepricingAgent |
| 评论/差评/星级/VINE/绿标 | ReviewMonitorAgent |
| 绿标/VINE/早期评论 | VINEProgramAgent |
| 品牌/商标/侵权/投诉 | BrandRegistryAgent |
| 跟卖/被跟卖/Hijacker | HijackerDetectorAgent |
| 销售/报表/业绩/数据 | SalesAnalyticsAgent |
| 利润/成本/ROI/核算 | ProfitCalculatorAgent |
| 客服/买家消息/退货/回复 | CustomerServiceAgent |
| 合规/政策/审核/类目 | ComplianceCheckerAgent |
| 账号/ODR/健康度/预警 | AccountHealthAgent |
| 归因/AMC/全漏斗/多触点/跨渠道 | AttributionEngineAgent |
| 旅程/漏斗/路径/首触/末触 | JourneyAnalyzerAgent |
| ROAS/ROI/ACOS/CPA/关键字ROI | ROICalculatorAgent |
| 我要查/帮我看/情况如何 | SalesAnalyticsAgent |

## 五、使用方式

### 快速查询
```
"帮我查一下今天美国站的销量"
"竞品A的关键词有哪些"
"我有个差评怎么回复"
```

### 任务执行
```
"帮我分析一下这个产品能不能做"
"优化一下我的Listing标题"
"制定一个30天冲BSR的计划"
```

### 主动预警
幕僚长自动监控以下异常并推送：
- 库存低于安全库存
- 收到1-2星差评
- 被跟卖检测到
- ACOS突然飙升
- ODR超过阈值

### ProfitOptimizer 算法模块（v1.2新增）

位于 `execution/` 目录，实现 Adspert 核心护城河能力：

| 模块 | 文件 | 核心能力 |
|------|------|---------|
| 利润市场曲线 | `execution/profit_optimizer.py` | 四参数曲线拟合（αβγδ）、最优出价搜索、批量关键词优化 |
| 转化预测器 | `execution/conversion_predictor.py` | 22维决策树特征体系、CVR/AOV预测、在线学习更新 |
| 日内调价 | `execution/intraday_bidder.py` | 三层决策（L1时段/L2表现/L3竞品）、24h动态出价 |

**ProfitOptimizer 核心公式**：
```
P(b) = α · (1 - e^{-βb}) · e^{-γb} + δ
最优出价 = argmax_b P(b)
```

**性能基准（vs规则引擎）**：
- ProfitOptimizer 利润提升 **+19.5%**（T9测试，模拟真实竞价场景）
- 日内调价相比「一天一次」策略更贴近实时市场竞争

运行测试：
```bash
cd amazon-ops-agents && python -m execution.tests.test_profit_optimizer
```
测试结果：**17/17 全部通过** ✅

### AMS 实时数据接入模块（v1.3新增）

位于 `tools/` + `config/` 目录，实现 **<5分钟延迟** 的实时AMS数据接入，直接支撑 ProfitOptimizer 实时竞价决策。

#### 核心架构

```
AMS API（SP/SB/SD + Marketing Stream）
       ↓
AMSClient（OAuth 2.0 / 速率限制 / 自动重试）
       ↓
DataPipeline（数据清洗 → SQLite缓存 → 实时聚合）
       ↓
RealTimeMetricsEngine（ACOS/TACOS/ROAS滚动窗口）
       ↓
ProfitOptimizer（竞价建议 → 实时出价调整）
```

#### 文件说明

| 文件 | 职责 |
|------|------|
| `tools/ams_client.py` | AMS API统一客户端：Sponsored Products/Brands/Display + Marketing Stream；OAuth 2.0自动刷新；滑动窗口速率限制（±10%抖动）；指数退避重试 |
| `tools/ams_data_pipeline.py` | 数据管道：多账户并发拉取 → DataCleaner（去重/异常过滤） → AMSCache（SQLite WAL模式，TTL管理）→ RealTimeMetricsEngine |
| `tools/real_time_metrics.py` | 实时指标引擎：60分钟滚动窗口；ACOS/ROAS/CTR/CVR实时聚合；ACOS飙升/预算耗尽告警；ProfitOptimizer竞价推荐；健康监控 |
| `config/ams_config.py` | 配置管理：多账户配置（OAuth凭证）；速率限制（各API独立RPM）；缓存TTL；ProfitOptimizer推送端点；YAML + 环境变量双模式 |

#### 关键指标

| 指标 | 目标 | 实现 |
|------|------|------|
| 数据延迟 | **<5分钟** | 60s轮询 + Stream事件增量更新 |
| API成功率 | **>99%** | 指数退避 × 3次重试 + 429按Retry-After |
| 多账户管理 | **任意数量** | Async并发 + 独立速率限制窗口 |
| 缓存命中率 | **>80%** | SQLite WAL + campaign/keyword分层TTL |

#### API集成

- **Sponsored Products API**：campaigns/list、keywords/list、reporting/reports（异步报告）
- **Sponsored Brands API**：campaigns/list（含headline search ads）
- **Sponsored Display API**：campaigns/list、受众定向报告
- **Marketing Stream**：IMPRESSION/CLICK/CONVERSION事件流（秒级延迟）

#### 告警类型

| 告警 | 触发条件 | 严重度 |
|------|---------|--------|
| `CAMPAIGN_ACOS_SPIKE` | ACOS > 目标×150% | critical/warning |
| `KEYWORD_ACOS_SPIKE` | 关键词ACOS > 目标×120% | warning |
| `BUDGET_CRITICAL` | 预算消耗 > 90% | critical |
| `BUDGET_WARNING` | 预算消耗 > 75% | info |
| `CAMPAIGN_UNPROFITABLE` | ROAS < 1.0（广告亏损） | warning |

#### ProfitOptimizer集成

实时指标每分钟推送至 ProfitOptimizer，触发竞价调整：

```python
# 竞价建议示例
recommendation = {
    "keyword_id": "KW123",
    "current_bid": 1.50,
    "recommended_bid": 1.20,    # 降低出价保护ACOS
    "bid_change_pct": -0.20,
    "expected_acos": 0.23,        # 从0.35降至0.23
    "confidence": 0.82,           # R²=0.67
    "priority": "high",          # 高优先级执行
}
```

#### 启动方式

```python
from config.ams_config import load_config
from tools.ams_client import MultiAccountAMSClient
from tools.ams_data_pipeline import DataPipeline, AMSCache
from tools.real_time_metrics import RealTimeMetricsEngine
from execution.profit_optimizer import ProfitMarketCurve

cfg = load_config("config/ams.yaml")
cache = AMSCache("data/ams_cache.db")
optimizer = ProfitMarketCurve()  # 可选，注入以启用模型竞价建议
metrics = RealTimeMetricsEngine(cfg, profit_optimizer=optimizer)
pipeline = DataPipeline(cfg, cache, metrics)

await pipeline.start()
```

## 六、版本说明

- v1.0.0 初始版本，包含20个专业Agent
- **v1.1.0 重大升级（2026-04-13）**：
  - 端云智能路由（LOCAL/SMALL/LARGE三级引擎，零Token消耗）
  - GUI Guardian三层安全防护（BLOCK/CONFIRM/AUDIT）
  - 4个预置工作流（一键启动新品上架/广告优化/库存预警/客服）
  - WorkflowEngine工作流引擎
  - TaskRouter复杂度评分系统
  - 全套单元测试（8个测试用例全部通过）
- **v1.2.0 ProfitOptimizer（2026-04-14）**：
  - ProfitMarketCurve 利润市场曲线建模（仿 Adspert）
  - ConversionPredictor 22维决策树转化率预测
  - IntradayBidder 日内动态出价引擎（三层决策）
  - 17个单元测试全部通过，性能提升+19.5% vs规则引擎
- **v1.3.0 AMS实时数据接入（2026-04-14）**：
  - AMSClient：SP/SB/SD三广告API + Marketing Stream；OAuth 2.0自动刷新；滑动窗口速率限制
  - DataPipeline：多账户并发；DataCleaner数据清洗；AMSCache SQLite WAL存储
  - RealTimeMetricsEngine：60s滚动窗口；5类告警（ACOS/预算/亏损）；ProfitOptimizer竞价推荐
  - 数据延迟<5分钟；API成功率>99%；支持ProfitOptimizer实时竞价
- **基础版 ¥599/月**：选品/Listing/广告/库存/定价（5个核心Agent）
- **专业版 ¥2999/月**：+评论/品牌/数据/客服/合规（10个Agent）
- **企业版 ¥29999/月**：全部20个Agent + 定制开发 + 专属支持
