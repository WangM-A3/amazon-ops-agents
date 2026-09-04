---
name: "amazon-ops-silicon-army"
description: "亚马逊运营硅基军团 v2.3 — 面向跨境电商卖家的 Multi-Agent 运营系统（幕僚长 + 24 专业 Agent）。真实数据层（CSV 导入/SP-API）+ 真实 LLM 路由 + 4 预置工作流（含复核沙箱：步骤校验+人工复核闸门）+ AI 内容合规检查 + 经验记忆闭环，已接入 DSH Harness。"
whenToUse: "用户需要选品分析、Listing 优化、广告 ACOS 优化、库存预警、利润核算、差评回复、跟卖检测、账号健康、AI 内容合规检查、沉淀/教 Agent 记住运营偏好（经验记忆）、工作流步骤复核（approve/reject 高风险产物）等亚马逊运营任务时使用。触发词：选品/List/广告/ACOS/PPC/FBA/Listing/跟卖/差评/VINE/利润/库存/定价/合规/AI合规/AI内容/AIGC/经验/记住/教他/工作流/复核/亚马逊运营/Amazon Seller/TikTok Shop。"
---

# Amazon Operations Silicon Army v2.3 — 亚马逊运营硅基军团

> 版本 v2.3.0（2026-09-04）：新增「工作流复核沙箱层」— 4 个预置工作流的每个步骤产物
> 独立校验（expected_keys），高风险对外步骤（Listing 文案/广告调价建议/补货计划/客服回复）
> 进入人工复核闸门（approve/reject + 审计）。映射 WeKnora v0.8「沙箱 + 工具级审批」到单机引擎的轻量实现。
> v2.2.0（2026-08-28）：新增「经验记忆闭环」— Agent 本地经验库（SQLite）。
> v2.1.0（2026-03）：新增 AI 内容合规层 — 亚马逊 AI 人物图元数据披露 + TikTok Shop AIGC 标注与禁用 AI 篡改商品外观（双平台新规）。
> v2.0.0（2026-08-26）：真实数据层 + 真实 LLM 路由 + 工作流修复 + 测试基建 + 诚实基准。
> 相比 v1.x（全 Mock 演示壳）：业务 Agent 不再返回硬编码模板，改为「真实数据优先 → LLM 分析 → 模板兜底」三级。
> 引擎仓库：`amazon-ops/`（工作区）；DSH preset：`amazon-ops`。

## 一、系统定位

面向亚马逊跨境电商卖家的 AI 运营平台，模拟完整亚马逊运营团队。
**1 个幕僚长 + 24 个专业 Agent**（含竞品情报、供应链、知识库检索），覆盖全站点。

## 二、团队架构

### 幕僚长（ChiefOfStaff）
- 关键词路由 + 复杂度评分 + 端云路由（LOCAL/SMALL/LARGE）+ 并行调度 + 结果聚合
- 每个任务自动生成 trace_id，全链路 span 落 SQLite 审计库

### 24 个专业 Agent

| 类别 | Agent | 核心能力 |
|---|---|---|
| 选品（2） | ProductResearchAgent / NicheFinderAgent | 市场趋势、竞品分析、蓝海机会 |
| Listing（3） | ListingOptimizerAgent / KeywordResearchAgent / AContentGeneratorAgent | 标题五点优化、关键词挖掘、A+内容 |
| 广告（2） | PPCManagerAgent / SponsoredAdsAgent | ACOS 优化、SP/SB/SD 策略 |
| 库存（2） | InventoryPlannerAgent / FbaManagerAgent | 补货预测、FBA 费用优化 |
| 定价（2） | PriceOptimizerAgent / RepricingAgent | 动态定价、BuyBox 守价 |
| 评论（2） | ReviewMonitorAgent / VINEProgramAgent | 差评预警、Vine 策略 |
| 品牌（2） | BrandRegistryAgent / HijackerDetectorAgent | 侵权投诉、跟卖检测 |
| 数据（2） | SalesAnalyticsAgent / ProfitCalculatorAgent | 销售报表、利润核算 |
| 客服（1） | CustomerServiceAgent | 买家消息、退货处理 |
| 合规（2） | ComplianceCheckerAgent / AccountHealthAgent | 政策合规、ODR 健康 |
| 竞品情报（1） | CompetitorAnalysisAgent | BestSeller 监控、价格追踪 |
| GUI（1） | GUIAgent（SIMULATE 模式，需人工确认） | 浏览器自动化规划 |
| 供应链（1）🚢 | SupplyChainAgent | 交期/物流时效评估 |
| 知识库（1）📚 | QAAgent | FAQ 检索、政策库 |

## 三、真实数据层（v2.0 核心）

**三级数据来源，按真实度自动降级**：

| 级别 | 来源 | 接入方式 | data_source 标记 |
|---|---|---|---|
| 1 | 本地导入 | 把运营报表存为 CSV/JSON，运行 `python -m data.ingest` 导入 SQLite（支持中英文列名自动识别） | `local_store` |
| 2 | SP-API 在线 | 配置 `SPAPI_CLIENT_ID/SECRET/REFRESH_TOKEN`，`data/sp_api_client.py` 自动 OAuth + 拉取 | `sp_api` |
| 3 | 模板兜底 | 无任何真实数据时 | `demo`（明确标注，不伪装） |

- 存储：SQLite（products / sales_daily / inventory / ads_daily 四表），数据目录 `data/seller.db`
- 已接入真实数据读取的 Agent：sales_analytics、inventory_planner、ppc_manager、profit_calculator
- 示例数据：`data/sample/`（雨伞品类，可直接导入体验）

## 四、端云智能路由（v2.0 真实化）

| 引擎 | 实现 | 说明 |
|---|---|---|
| LOCAL | `routing/local_executor.py` | 确定性处理（CSV/JSON 转换等），零 Token |
| SMALL | `routing/llm_executor.py` | **真实调用 LLM**（OpenAI 兼容，默认 DeepSeek），注入 DataProvider 真实数据到 prompt |
| LARGE | 同上 | 复杂分析走更大 max_tokens，按 Agent 角色建 prompt |

- LLM 开关：`AMAZON_OPS_LLM=auto|on|off`（auto=端点可用即启用）
- 环境变量：`DEEPSEEK_BASE_URL / DEEPSEEK_API_KEY / DEEPSEEK_MODEL`（或 OPENAI_*）
- 失败自动回退模板并标记 `llm_mode: template_fallback`；token 为真实 usage 计量
- 数据型 Agent 的 prompt 自动注入真实数据摘要（销售/库存/广告/利润），LLM 基于真实数字分析，不编造

## 五、预置工作流（v2.0 修复，4/4 可用）

| 工作流 | 步骤 | 说明 |
|---|---|---|
| new_product_launch | 4 | 选品→关键词→Listing→A+（含 AI 内容合规提示） |
| ad_optimization | 4 | 数据→竞品→策略→ROI |
| inventory_alert | 5 | FBA→预测→补货→供应链→预警报告 |
| customer_service | 4 | 分类→知识库→回复→合规审核 |

API：`POST /api/v1/workflow`（workflow_id + input）、`GET /api/v1/workflows`
（v2.3：workflow 响应含 `run_id` + `reviews`——每步产物校验 + 待复核清单）

## 五·二、工作流复核沙箱层（v2.3 新增）

> 映射 WeKnora v0.8「沙箱运行时 + 工具级人工审批 require_approval + pending」到单机引擎的轻量实现。
> 设计取舍：卖家一键包无 Docker → 不引入容器沙箱；"沙箱"语义 = **产物隔离校验 + 复核闸门 + 全链路审计**。

```
工作流启动(POST /api/v1/workflow) → run_id
   │
   ▼
每步执行 → 产物校验(expected_keys 缺失→记录 validated/missing，不中断)
   │
   ▼
review=True 的高风险步骤（对外产物）→ decision=pending，列入待复核
   │   （new_product_launch: Listing文案·high | ad_optimization: 调价建议·high
   │     inventory_alert: 补货计划·medium | customer_service: 客服回复·high）
   ▼
人工复核 POST /api/v1/workflow/review {run_id, step_key, decision: approve|reject, comment}
   │   → 审计落盘（谁在何时批准/否决了什么产物）；幂等（已决策不可改）
   ▼
GET /api/v1/workflow/review/{run_id} → 全部步骤决策状态
```

- 模块：`workflows/presets.py`（`WorkflowStep.review/risk/expected_keys` + `_sandbox_step` 校验）、`workflows/review_gate.py`（ReviewGate：登记/查询/决策 + 审计）
- 关键语义：**所有步骤产物默认只读建议**；approve = 该建议可采纳，reject = 不采纳（仅记录，不触发任何外部动作）——与"人工确认闸门"一致
- 产物预览：待复核项带 `preview`（截断 400 字符），复核人无需展开完整结果

## 五·五、AI 内容合规层（v2.1 新增）

> 应对 2025 亚马逊 + TikTok Shop 双平台 AI 内容标注新规。

**规则库**：`compliance/ai_content_rules.py`

| 平台 | 新规要求 | 违规后果 |
|---|---|---|
| **亚马逊** | AI 生成的逼真人物图（Listing/A+/旗舰店/广告）须在元数据添加 AI 披露标签（contains-synthetic-performer / synthetic-media） | 图片拒审 / Listing 下架 / 账号健康扣分 |
| **TikTok Shop** | AI 生成内容显著标注；禁止 AI 篡改商品外观、捏造不实效果 | 商品下架 / 限流 / 封店 |

**能力落点**：
- `ComplianceCheckerAgent`：AI 内容合规检查（素材属性可从 context 或任务文本自动推断，默认按最严格场景提示）
- `ListingOptimizerAgent` / `AContentGeneratorAgent`：输出 AI 合规 checklist（AI 人物图打标提示 + 实拍替代建议）
- LLM 模式：合规规则注入 prompt，`compliance_checker / listing_optimizer / acontent` 强制输出 `ai_content_compliance` 字段
- 检查函数：`check_ai_content_compliance()` / `ai_image_label_required()` / `tiktok_ai_disclosure_required()`

```python
from compliance import check_ai_content_compliance
# 检查一张含 AI 生成模特、且 TikTok 素材为 AI 视频的素材
r = check_ai_content_compliance(
    platform="all",
    image_has_real_human=True, image_is_ai_generated=True,
    tiktok_is_ai_content=True,
)
print(r["summary"], r["risk_level"], r["all_pass"])
```

## 六、API 与安全

- FastAPI（默认 8080）：`/health`、`/api/v1/agents`、`/api/v1/routing`、`/api/v1/execute`、`/api/v1/batch`、`/api/v1/workflow(s)`、`/api/v1/stats`、`/api/v1/audit`、`/api/v1/feedback`
- 经验记忆（v2.2）：`/api/v1/memory/experience`（增/查）、`/api/v1/memory/experience/{id}/deactivate`（停用）、`/api/v1/memory/rating`（打分回写）
- 工作流复核（v2.3）：`POST /api/v1/workflow/review`（approve/reject）、`GET /api/v1/workflow/review/{run_id}`（状态）
- 鉴权：X-API-Key（HMAC 签名可选）；限流 100/min/Key（内存）
- GUIGuardian：10 类危险操作 BLOCK / 5 类敏感操作 CONFIRM / 全量 AUDIT；凭证 HMAC-SHA256 加密
- 全链路 Tracing：每请求 trace_id，AuditTrail SQLite 落盘，TraceQuery 可回查

## 六-B、经验记忆闭环（v2.2 新增）

> 让 Agent「越用越懂这家店」：运营偏好与修正策略可沉淀、可复用、可淘汰。

```
沉淀经验(POST /memory/experience) ──┐
                                    ▼
任务执行 ──▶ 关键词匹配命中经验 ──▶ 注入 LLM prompt（experience_used 透出）
                                    ▼
用户打分(POST /memory/rating 1-5) ──▶ pos/neg 统计
                                    ▼
                   成功率 < 50% 且负反馈样本≥2 → 自动停用（不再注入）
```

- 存储：SQLite `data/memory/experience.db`（`experiences` + 统计字段），零外部依赖
- 注入：`routing/llm_executor.py` 组装 prompt 时追加「本店历史经验」块；数据型 Agent 与模板回退路径同样生效
- 检索：按 Agent + 任务关键词匹配；命中词数越多排越前；烂经验软过滤
- 评分：rating≥4 记正反馈、≤2 记负反馈；样本足够且成功率<50% 自动停用（闭环收口）
- 用法示例：
  ```bash
  # 教 Agent：以后广告类任务先否定再提预算
  curl -X POST http://localhost:8080/api/v1/memory/experience \
    -H "X-API-Key: xxx" -H "Content-Type: application/json" -d '{
      "agent_id": "ppc_manager", "title": "高ACOS三连招",
      "content": "①否定高花费零转化词 ②给低ACOS活动加预算 ③测试动态竞价",
      "keywords": ["acos","广告","竞价"]}'
  # 执行任务 → 响应里 results.*.experience_used 显示命中经验
  # 对结果打分（好=4/5，差=1/2）
  curl -X POST http://localhost:8080/api/v1/memory/rating \
    -H "X-API-Key: xxx" -H "Content-Type: application/json" \
    -d '{"task_id": "上一步的task_id", "rating": 5}'
  ```
- ⚠️ 诚实边界：这是「半自动经验闭环」——经验由卖家沉淀、打分淘汰；**自动「报错→学习」仍为零实现**（见诚实声明）

## 七、执行算法模块（真实数学内核）

| 模块 | 能力 |
|---|---|
| ProfitMarketCurve | 利润市场曲线拟合（四参数）、最优出价搜索、ACOS 约束求解 |
| ConversionPredictor | 22 维转化率预测、在线学习 |
| IntradayBidder | 三层日内调价（时段/表现/竞品） |

**诚实基准**（`benchmarks/bench_profit_optimizer.py`，同空间/同真值/50 市场×2 场景）：
- 拟合友好市场：vs 规则引擎 +38~55%（胜率 100%）
- 模型失配市场：vs 校准良好的自适应规则 +18.7%（胜率 82%）
- ⚠️ v1.x 宣称的"+19.5%"是矮化基准产物（acos 恒 0.2 → 规则引擎从不动作），已废弃

## 八、测试与运行

```bash
# 运行环境（工作区便携 Python）
.runtime/python312/python.exe

# 统一 CLI 入口 run_ops.py（内置 sys.path 引导，规避嵌入式 Python ._pth 忽略 CWD）
.runtime/python312/python.exe run_ops.py test          # 全量测试 98 项
.runtime/python312/python.exe run_ops.py selftest      # 自测套件 9 项
.runtime/python312/python.exe run_ops.py bench         # 诚实基准
.runtime/python312/python.exe run_ops.py po-test       # ProfitOptimizer 17 项
.runtime/python312/python.exe run_ops.py ingest        # 导入 data/sample 真实数据
.runtime/python312/python.exe run_ops.py workflow inventory_alert   # 跑预置工作流
.runtime/python312/python.exe run_ops.py server 8080   # 启动 API Server
```

## 九、版本说明与诚实声明

- **v2.3.0（2026-09-04）**：工作流复核沙箱层 — `workflows/presets.py`（每步产物校验 + review/risk 标记）+ `workflows/review_gate.py`（approve/reject 复核门 + 审计）+ `/api/v1/workflow/review`；测试 98/98
- **v2.2.0（2026-08-28）**：经验记忆闭环 — `memory/experience_store.py`（SQLite 经验库）+ LLM prompt 注入 + `/api/v1/memory/*` + `/api/v1/memory/rating` 打分淘汰；测试 92/92
- **v2.1.0（2026-03）**：AI 内容合规层 — `compliance/ai_content_rules.py` 双平台规则库、ComplianceCheckerAgent/Listing/A+ 合规检查、LLM prompt 合规注入
- **v2.0.0（2026-08-26）**：真实数据层、真实 LLM 路由、工作流修复（4/4）、测试基建（68/68）、诚实基准、DSH Harness 接入
- v1.3.0：AMS 实时数据管道（OAuth/限速/缓存）——客户端真实，但需真实广告账户凭据
- v1.2.0：ProfitOptimizer 算法模块——真实数学内核
- v1.1.0：端云路由/GUIGuardian/工作流框架——框架真实，业务层当时为 Mock

**规划中（未实现，勿当能力宣传）**：
- ❌ IM 远程调度（飞书/微信/WhatsApp）— 零实现
- ❌ 错误记忆自进化（报错→学习闭环）— 零实现（v2.2 为「半自动经验闭环」：经验由用户沉淀、打分淘汰，Agent 不会自动从报错中学习）
- ❌ 跨渠道归因引擎（Markov/Sankey）— 零实现
- ❌ Layer1 公开爬取竞品情报 — 仅硬编码字符串

## 十、DSH Harness 接入

- Agent Preset：`amazon-ops`（`dsh-home/.agent-presets/amazon-ops/`）— 新会话选择该 preset 即获得本技能 + 引擎驱动能力
- Skill：本文件即 DSH skill（`dsh-home/skills/amazon-ops-silicon-army/SKILL.md`）
- 引擎位置：工作区 `amazon-ops/`（Python 3.12 便携运行时 `.runtime/python312/`）
- 强制规则：默认中文；危险操作（发布/批量改价/删除 Listing/批量触达）先人工确认；LLM 调用受 `AMAZON_OPS_LLM` 与成本护栏约束
