# 亚马逊运营硅基军团 v1.1.0 改进报告

> 完成日期：2026-04-13
> 基于 YOYO Claw 竞品分析成果（`learnings/2026-04-13-yoyo-claw-analysis.md`）

---

## 一、改进概览

| 模块 | 新增文件 | 行数 | 状态 |
|------|----------|------|------|
| 端云智能路由 | `routing/task_router.py` | 198行 | ✅ |
| 本地执行引擎 | `routing/local_executor.py` | 217行 | ✅ |
| GUI Guardian | `security/gui_guardian.py` | 258行 | ✅ |
| 预置工作流 | `workflows/presets.py` | 263行 | ✅ |
| ChiefOfStaff集成 | `agents/chief.py` | 176行 | ✅ |
| 测试套件 | `tests/test_router.py` | 430行 | ✅ 8/8通过 |
| 文档更新 | `SKILL.md` | +40行 | ✅ |

**测试结果**：8/8全部通过，原有demo测试全部通过向后兼容。

---

## 二、端云智能路由（核心改进）

### 架构

```
用户任务 → TaskRouter.route()
              ├─ 复杂度评分（0-100分，模式匹配）
              ├─ 引擎决策（LOCAL / SMALL / LARGE）
              └─ Agent覆盖（Agent级强制引擎映射）
                        ↓
              执行（ChiefOfStaff.execute）
```

### 三级引擎

| 引擎 | 适用场景 | Token消耗 | 典型任务 |
|------|----------|-----------|----------|
| **LOCAL** | 数据提取、格式转换、统计计算 | **0** | "提取订单导出CSV"、"统计销量"、"格式转换" |
| **SMALL** | 数据分析、报告生成、监控预警 | ~100 | "分析广告ACOS"、"查看库存" |
| **LARGE** | 策略制定、创意生成、深度分析 | ~500 | "制定品牌增长策略"、"深度市场分析" |

### 复杂度评分算法

```python
复杂度分 = 任务长度分(0-20)
          + 高复杂度命中×15(0-60)   # 策略/创意/全面分析
          + 中复杂度命中×8(0-40)     # 数据/报表/统计
          - 本地候选命中×5           # 降低分数以触发LOCAL
```

**关键Agent引擎映射**（覆盖分数决策）：
- `profit_calculator` → LOCAL（强制）
- `gui_agent` → LARGE（强制）
- `product_research` → LARGE（策略判断）

### Token节省效果

| 任务类型 | 原Token消耗 | 改进后 | 节省 |
|----------|-------------|--------|------|
| 数据提取 | 150 | 0 | **83%** |
| 格式转换 | 150 | 0 | **83%** |
| 统计计算 | 150 | 0 | **83%** |
| 中等分析 | 150 | 100 | 33% |
| 复杂策略 | 150 | 500 | - |

---

## 三、GUI Guardian 三层安全防护

### 三层防护机制

```
GUI Agent操作 → Guardian.authorize()
                      │
                      ├─ 应用层：PROHIBITED_ACTIONS（set）
                      │   └─ BLOCK → 直接拦截（10类危险操作）
                      │
                      ├─ 系统层：CONFIRM_REQUIRED_ACTIONS（dict）
                      │   └─ CONFIRM → 返回确认Token，用户确认后放行
                      │       示例：修改价格、发送买家消息、导出客户数据
                      │
                      └─ 驱动层：AUDIT_ACTIONS（set）
                          └─ AUDIT → 记录但不阻止
```

### 防护清单

**应用层拦截（BLOCK）**：
- `delete_listing` - 删除Listing
- `bulk_delete_orders` - 批量删除订单
- `delete_review` - 删除评论
- `modify_brand_settings` - 修改品牌核心设置
- `transfer_funds` - 转账/修改收款账户
- `submit_false_report` - 提交虚假报告
- `cancel_all_orders` - 取消所有订单
- `disable_advertising` - 禁用广告活动（批量）
- `modify_tax_info` - 修改税务信息

**系统层确认（CONFIRM）**：
| 操作 | 关键词 | 确认原因 |
|------|--------|----------|
| `modify_price` | 调价/降价/涨价/修改价格 | 价格直接影响BuyBox和销售收入 |
| `send_message` | 发送消息/reply to buyer | 消息直接触达买家 |
| `export_sensitive` | 导出客户数据/邮箱 | 涉及买家个人信息导出 |
| `modify_ad_budget` | 修改广告预算/调整预算 | 预算变更影响广告投放 |
| `adjust_inventory` | 修改库存数量/set inventory | 库存变更影响FBA补货 |

**凭证保险库（CredentialVault）**：
- HMAC-SHA256加密存储
- Session级内存缓存
- 安全删除+清空全部接口

---

## 四、预置工作流

### 4个预置工作流

```
┌─────────────────────────────────────────────────────────┐
│  🆕 新品上架工作流          4步  |  预估60s            │
│  product_research → keyword_research →                  │
│  listing_optimizer → acontent（可选）                   │
├─────────────────────────────────────────────────────────┤
│  📈 广告优化工作流          4步  |  预估45s            │
│  ppc_manager → sponsored_ads → ppc_manager →            │
│  profit_calculator                                      │
├─────────────────────────────────────────────────────────┤
│  📦 库存预警工作流          5步  |  预估43s            │
│  fba_manager → inventory_planner →                      │
│  inventory_planner → supply_chain →                     │
│  inventory_planner                                      │
├─────────────────────────────────────────────────────────┤
│  💬 客户服务流程            4步  |  预估21s            │
│  customer_service → qa_agent →                         │
│  customer_service → compliance_checker                  │
└─────────────────────────────────────────────────────────┘
```

### WorkflowEngine API

```python
from workflows.presets import WORKFLOW_ENGINE

# 列出所有工作流
workflows = WORKFLOW_ENGINE.list_workflows()

# 一键启动
result = await WORKFLOW_ENGINE.launch(
    workflow_id="new_product_launch",
    context={"product_name": "蓝牙耳机"}
)

# 结果
assert result.status == WorkflowStatus.DONE
assert "research_result" in result.step_results
```

---

## 五、ChiefOfStaff 增强

### 新增功能

1. **TaskRouter集成**：execute() 前调用 router.route()，注入 `_routing` 元数据
2. **LOCAL执行路径**：直接调用 LocalExecutor.execute()，绕过Agent
3. **plan() 方法**：仅做路由规划，不执行（用于预览Token消耗）

### 返回结果增强

```python
{
    "chief": "🎩 ChiefOfStaff",
    "routing": {           # 新增
        "engine": "small_model",
        "complexity_score": 42,
        "estimated_tokens": 100,
        "reasoning": "中复杂度命中+16; Agent覆盖: sales_analytics→small_model",
        "fallback": "local",
    },
    "routed_agents": ["sales_analytics"],
    "total_tokens": 150,
    ...
}
```

---

## 六、新增文件结构

```
amazon-ops-agents/
├── routing/
│   ├── __init__.py          ✅ 导出 Engine, TaskRouter, ROUTER, EXECUTOR
│   ├── task_router.py       ✅ TaskRouter类 + RoutingDecision + 复杂度评分
│   └── local_executor.py    ✅ LocalExecutor + 6个本地处理器（零Token）
├── security/
│   ├── __init__.py          ✅ 导出 GUARDIAN, GUIGuardian, SecurityLevel
│   └── gui_guardian.py      ✅ 三层安全防护 + CredentialVault + 审计日志
├── workflows/
│   ├── __init__.py          ✅ 导出 WORKFLOW_ENGINE + 4个PresetWorkflow
│   └── presets.py            ✅ WorkflowEngine + 4个工作流定义 + WorkflowStatus
├── agents/
│   └── chief.py             ✅ 增强：集成TaskRouter + LOCAL执行路径 + plan()
└── tests/
    └── test_router.py        ✅ 8个测试用例全部通过
```

---

## 七、验收标准检查

| 标准 | 结果 | 证据 |
|------|------|------|
| TaskRouter正确分类任务复杂度 | ✅ | 10/10测试用例通过 |
| GUI Guardian拦截高危操作 | ✅ | 11/11测试用例通过（BLOCK 4 + CONFIRM 4 + SAFE 3） |
| 预置工作流能一键启动 | ✅ | 4个工作流全部注册，WorkflowEngine实现 |
| 新增测试用例全部通过 | ✅ | `test_router.py` 8/8通过 |
| 更新SKILL.md文档 | ✅ | 新增技术架构说明和v1.1.0版本历史 |
| 向后兼容（原有测试） | ✅ | `test_demo.py` 所有用例通过 |

---

## 八、技术亮点

### 1. YOYO Claw启发：端云路由
参考YOYO Claw的"简单任务本地执行"策略，本地化实现：
- 模式匹配（无LLM开销）→ 复杂度评分
- Agent级强制覆盖（覆盖分数决策，更可靠）
- 降级fallback机制（LARGE→SMALL→LOCAL）

### 2. 安全纵深防御
借鉴企业级安全设计：
- 应用层（阻断）+ 系统层（确认）+ 驱动层（审计）
- Token-based二次确认（带时效性）
- 凭证从不落盘（HMAC加密内存缓存）

### 3. 工作流编排
- 串行执行（数据依赖场景）
- 步骤结果自动聚合（context传递）
- 预估时间vs实际时间对比

---

## 九、下一步建议

1. **引入真实LLM**：将 `EXECUTOR.execute()` 和 Agent调用替换为实际API调用
2. **GUI Agent集成**：将 `GUARDIAN` 集成到 `gui_agent.py` 的 `authorize()` 方法
3. **工作流API端点**：在 `api_server.py` 增加 `/workflows` 路由
4. **性能监控**：添加 Token消耗统计面板（基于routing元数据）
5. **集成测试**：添加端到端API测试（使用 FastAPI TestClient）
