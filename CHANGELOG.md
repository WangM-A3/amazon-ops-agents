# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-03

### Added

- **AI 内容合规层**（应对亚马逊 + TikTok Shop 双平台 AI 内容标注新规）
  - `compliance/ai_content_rules.py`：双平台规则库 + 检查函数
    - 亚马逊：AI 生成逼真人物图元数据披露（contains-synthetic-performer / synthetic-media）
    - TikTok Shop：AI 内容显著标注 + 禁用 AI 篡改商品外观/捏造不实效果
  - `ComplianceCheckerAgent`：AI 内容合规检查（素材属性从 context/任务文本自动推断）
  - `ListingOptimizerAgent` / `AContentGeneratorAgent`：AI 合规 checklist 输出
  - LLM 模式 prompt 注入合规规则（compliance_checker / listing_optimizer / acontent）
  - 新增 16 项 AI 内容合规单元测试

## [1.1.0] - 2026-04-13

### Added

- **端云智能路由引擎**（TaskRouter + LocalExecutor）
  - 三级引擎架构：LOCAL（零Token消耗）/ SMALL（Qwen-7B）/ LARGE（GPT-4）
  - 基于任务复杂度的自动引擎选择
  - Agent级别引擎覆盖（如 profit_calculator 强制 LOCAL）
  - 全链路 Token 预估和成本分析
  - 自动降级机制（LARGE → SMALL → LOCAL）

- **GUI Guardian 三层安全防护**
  - 应用层：10类危险操作直接拦截（BLOCK）
  - 系统层：5类敏感操作二次确认（CONFIRM）
  - 驱动层：全量操作审计日志（GuardianResult + AuditLogEntry）
  - CredentialVault 凭证加密存储（HMAC-SHA256）

- **4个预置工作流**（WorkflowEngine）
  - 🆕 `new_product_launch`：新品上架（4步，60s）
  - 📈 `ad_optimization`：广告优化（4步，45s）
  - 📦 `inventory_alert`：库存预警（5步，43s）
  - 💬 `customer_service`：客户服务（4步，21s）

- **WorkflowEngine 工作流引擎**
  - 步骤级执行与状态追踪
  - Context 上下文管理
  - 步骤输出自动传递

- **完整单元测试套件**
  - 8个测试用例，覆盖 ChiefOfStaff / TaskRouter / Agent
  - 全部测试通过（8/8）
  - pytest-asyncio 异步测试支持

- **Agent 覆盖扩展**
  - 新增 GuiAgent（GUI 操作代理，含 Guardian 安全守护）
  - chief.py 支持动态 Agent 加载

- **技术文档**
  - IMPROVEMENT_REPORT.md（详细改进报告）
  - 全链路文档注释

### Changed

- `routing/task_router.py`：重构复杂度评分算法，新增 token 预估
- `security/gui_guardian.py`：三层安全架构，替代原有简单权限检查
- `agents/chief.py`：支持动态 agent 注册，新增 run_agent 方法
- `agents/base.py`：统一 Agent 基类，新增 engine 属性

## [1.0.0] - 2026-04-13

### Added

- 初始版本发布
- **1个幕僚长（ChiefOfStaff）** - 智能任务调度中心
- **20个专业Agent**，覆盖亚马逊运营全链路：

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

- FastAPI 服务（端口 8080）
- Amazon SP-API 集成支持
- 关键词路由调度引擎
- 完整定价方案（基础版/专业版/企业版）
- 测试用例（tests/test_demo.py）
- Dockerfile 生产部署支持
