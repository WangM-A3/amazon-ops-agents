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
  
  ## 核心能力
  - 20个专业Agent覆盖选品→Listing→广告→库存→定价→评论→品牌→数据→客服→合规全链路
  - 幕僚长（ChiefOfStaff）智能任务分发 + 端云路由（LOCAL/SMALL/LARGE三引擎）
  - 4个预置工作流（一键新品上架/广告优化/库存预警/客服）
  - 三层安全防护（BLOCK/CONFIRM/AUDIT）
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
      features: ["5个核心Agent", "选品/Listing/广告/库存/定价", "基础数据看板"]
    professional:
      price: 2999
      currency: CNY
      period: month
      features: ["15个专业Agent", "全链路覆盖", "API集成", "广告优化", "品牌保护"]
    enterprise:
      price: 29999
      currency: CNY
      period: month
      features: ["全部20个Agent", "定制开发", "专属支持", "私有部署"]
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

## 六、版本说明

- v1.0.0 初始版本，包含20个专业Agent
- **v1.1.0 重大升级（2026-04-13）**：
  - 端云智能路由（LOCAL/SMALL/LARGE三级引擎，零Token消耗）
  - GUI Guardian三层安全防护（BLOCK/CONFIRM/AUDIT）
  - 4个预置工作流（一键启动新品上架/广告优化/库存预警/客服）
  - WorkflowEngine工作流引擎
  - TaskRouter复杂度评分系统
  - 全套单元测试（8个测试用例全部通过）
- **基础版 ¥599/月**：选品/Listing/广告/库存/定价（5个核心Agent）
- **专业版 ¥2999/月**：+评论/品牌/数据/客服/合规（10个Agent）
- **企业版 ¥29999/月**：全部20个Agent + 定制开发 + 专属支持
