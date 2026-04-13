# Amazon Operations Silicon Army - Examples

> 亚马逊运营硅基军团 · 使用示例集

本目录提供从入门到高级的完整使用示例，帮助快速上手。

---

## 📁 目录结构

```
examples/
├── basic/
│   ├── 01_quick_query.py      # 快速查询示例
│   ├── 02_single_agent.py      # 单Agent调用示例
│   └── 03_batch_tasks.py      # 批量任务示例
├── advanced/
│   ├── 01_workflow_launch.py  # 工作流启动示例
│   ├── 02_multi_agent_chain.py # 多Agent协同示例
│   └── 03_api_integration.py   # 外部API集成示例
└── scripts/
    ├── demo_local.sh          # 本地Demo脚本
    └── health_check.sh        # 健康检查脚本
```

---

## 🚀 快速开始

### 启动服务

```bash
# 进入项目目录
cd amazon-ops-agents

# 安装依赖
pip install -r requirements.txt

# 启动API服务
python api_server.py
# 服务地址：http://localhost:8080
```

### 验证服务

```bash
curl http://localhost:8080/health
# 预期输出：{"status":"ok","agents":20,"version":"1.1.0"}
```

---

## 📖 基础示例

### 示例 1：快速查询（Quick Query）

适用场景：用自然语言快速查询运营数据

```python
import httpx

client = httpx.Client(base_url="http://localhost:8080")

# 查询今日销量
resp = client.post("/api/v1/execute", json={
    "task": "帮我查一下今天美国站的销量情况",
    "marketplace": "US"
})
print(resp.json())

# 查询竞品关键词
resp = client.post("/api/v1/execute", json={
    "task": "竞品 ASIN B0XXXXXX 的主要关键词有哪些",
    "asin": "B0XXXXXX"
})
print(resp.json())

# 查询库存状态
resp = client.post("/api/v1/execute", json={
    "task": "SKU ABC123 库存还能维持几天",
    "sku": "ABC123"
})
print(resp.json())
```

**预期输出格式：**
```json
{
  "success": true,
  "agent": "SalesAnalyticsAgent",
  "result": "今日美国站订单量 127 单，GMV $3,842...",
  "tokens_used": 0,
  "engine": "local"
}
```

---

### 示例 2：单Agent调用（Single Agent）

适用场景：直接调用特定专业Agent完成任务

```python
import httpx

client = httpx.Client(base_url="http://localhost:8080")

# === Listing优化 ===
resp = client.post("/api/v1/execute", json={
    "task": "优化这个蓝牙耳机的Listing标题，要求包含核心关键词",
    "asin": "B0XXXXXX",
    "keywords": ["bluetooth earbuds", "wireless earphones", "noise cancelling"]
})
print("Listing优化:", resp.json()["result"][:200])

# === 广告ACOS优化 ===
resp = client.post("/api/v1/execute", json={
    "task": "我的广告ACOS 45%太高了，怎么优化到25%以内",
    "sku": "ABC123",
    "current_acos": 0.45,
    "target_acos": 0.25
})
print("广告优化:", resp.json()["result"][:200])

# === 差评处理 ===
resp = client.post("/api/v1/execute", json={
    "task": "收到一个1星差评，说耳机续航不行，帮我写回复",
    "asin": "B0XXXXXX",
    "review_text": "Battery life is terrible, only lasted 2 hours..."
})
print("差评回复:", resp.json()["result"][:200])

# === 利润计算 ===
resp = client.post("/api/v1/execute", json={
    "task": "计算这个产品的FBA利润",
    "sku": "ABC123",
    "product_cost": 15.0,
    "selling_price": 49.99
})
print("利润分析:", resp.json()["result"][:200])
```

---

### 示例 3：批量任务（Batch Tasks）

适用场景：一次提交多个独立任务并行执行

```python
import httpx
import asyncio

client = httpx.AsyncClient(base_url="http://localhost:8080")

async def batch_example():
    tasks = [
        {"task": "分析无线蓝牙耳机市场趋势", "marketplace": "US"},
        {"task": "优化 SKU-001 的五点描述", "sku": "SKU-001"},
        {"task": "检查账号健康状态", "marketplace": "US"},
        {"task": "计算 SKU-002 的利润", "sku": "SKU-002"},
    ]

    resp = await client.post("/api/v1/batch", json={"tasks": tasks})
    results = resp.json()["results"]

    for r in results:
        print(f"[{r['agent']}] {r['result'][:100]}...")

asyncio.run(batch_example())
```

---

## 🔬 高级示例

### 示例 4：工作流启动（Workflow Launch）

适用场景：一键启动端到端业务流程

```python
import httpx

client = httpx.Client(base_url="http://localhost:8080")

# === 新品上架工作流 ===
resp = client.post("/api/v1/workflow", json={
    "workflow_id": "new_product_launch",
    "input": {
        "product_name": "3D打印灯",
        "category": "Home & Kitchen",
        "marketplace": "US",
        "target_keywords": ["3d printed lamp", "desk lamp", "bedroom decor"]
    }
})
workflow = resp.json()
print(f"工作流ID: {workflow['workflow_id']}")
print(f"总步骤数: {workflow['total_steps']}")
print(f"预计耗时: {workflow['estimated_seconds']}秒")

# 轮询状态
import time
while workflow["status"] in ["pending", "running"]:
    resp = client.get(f"/api/v1/workflow/{workflow['workflow_id']}")
    workflow = resp.json()
    print(f"当前步骤: {workflow['current_step']}/{workflow['total_steps']}")
    time.sleep(5)

print(f"最终状态: {workflow['status']}")
print(f"输出: {workflow['output']}")
```

**可用工作流：**

| 工作流ID | 名称 | 步骤数 | 预估时长 |
|---------|------|--------|----------|
| `new_product_launch` | 🆕 新品上架 | 4步 | 60s |
| `ad_optimization` | 📈 广告优化 | 4步 | 45s |
| `inventory_alert` | 📦 库存预警 | 5步 | 43s |
| `customer_service` | 💬 客户服务 | 4步 | 21s |

---

### 示例 5：多Agent协同（Multi-Agent Chain）

适用场景：复杂任务需要多个Agent顺序协作

```python
import httpx

client = httpx.Client(base_url="http://localhost:8080")

# 场景：从选品到Listing上线的完整流程
# Step 1: 市场调研
result1 = client.post("/api/v1/execute", json={
    "task": "分析宠物喂食器市场，选出3个有潜力的细分品类",
    "marketplace": "US"
}).json()
print("Step 1 选品:", result1["result"][:200])

# Step 2: 关键词研究（基于Step 1选品结果）
result2 = client.post("/api/v1/execute", json={
    "task": "针对宠物喂食器细分品类，挖掘50个长尾关键词",
    "niche": "automatic pet feeder with camera",
    "marketplace": "US"
}).json()
print("Step 2 关键词:", result2["result"][:200])

# Step 3: Listing创建（整合Step 1+2结果）
result3 = client.post("/api/v1/execute", json={
    "task": "创建宠物喂食器(自动款带摄像头)的完整Listing",
    "keywords": result2["result"],  # 传入上一步关键词
    "marketplace": "US"
}).json()
print("Step 3 Listing:", result3["result"][:200])

# Step 4: A+内容生成
result4 = client.post("/api/v1/execute", json={
    "task": "为宠物喂食器生成A+页面内容",
    "asin": result3.get("asin", "B0XXXXXX"),
    "brand_story": "让每一个宠物主人随时随地关爱宠物"
}).json()
print("Step 4 A+:", result4["result"][:200])
```

---

### 示例 6：外部API集成（API Integration）

适用场景：集成Helium 10、Jungle Scout、Keepa等第三方工具

```python
import httpx

client = httpx.Client(base_url="http://localhost:8080")

# === 集成Helium 10进行选品 ===
resp = client.post("/api/v1/execute", json={
    "task": "使用Helium 10分析厨房用品类目，找到月销>1000、竞争度低的产品",
    "tool": "helium10",
    "category": "Kitchen & Dining",
    "filters": {
        "monthly_revenue_min": 5000,
        "review_count_max": 100,
        "bsr_range": "1-50000"
    }
})
print("Helium 10选品:", resp.json()["result"][:200])

# === 使用Keepa分析价格趋势 ===
resp = client.post("/api/v1/execute", json={
    "task": "用Keepa分析竞品B0XXXXXX的180天价格历史和BuyBox价格",
    "tool": "keepa",
    "asin": "B0XXXXXX",
    "days": 180
})
print("Keepa价格分析:", resp.json()["result"][:200])

# === 船长ERP数据同步 ===
resp = client.post("/api/v1/execute", json={
    "task": "同步船长ERP中的库存数据到FBA管理系统",
    "tool": "captain_erp",
    "operation": "inventory_sync"
})
print("ERP同步:", resp.json()["result"][:200])
```

---

## 🛠️ 运维脚本

### 本地Demo脚本

```bash
# examples/scripts/demo_local.sh

#!/bin/bash
echo "🚀 启动亚马逊运营硅基军团 Demo..."

# 健康检查
echo "1. 健康检查..."
curl -s http://localhost:8080/health | python3 -m json.tool

# 快速查询
echo -e "\n2. 快速查询（销量）..."
curl -s -X POST http://localhost:8080/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "帮我查一下今天美国站的销量"}' | python3 -m json.tool

# Listing优化
echo -e "\n3. Listing优化示例..."
curl -s -X POST http://localhost:8080/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "优化蓝牙耳机标题，核心词：wireless earbuds"}' | python3 -m json.tool

echo -e "\n✅ Demo完成！"
```

### 健康检查脚本

```bash
# examples/scripts/health_check.sh

#!/bin/bash

BASE_URL="${1:-http://localhost:8080}"
echo "🔍 健康检查: $BASE_URL"

# 1. 服务健康
STATUS=$(curl -s "$BASE_URL/health" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
echo "  服务状态: $STATUS"

# 2. Agent数量
AGENTS=$(curl -s "$BASE_URL/health" | python3 -c "import sys,json; print(json.load(sys.stdin)['agents'])")
echo "  Agent数量: $AGENTS"

# 3. 路由表
ROUTES=$(curl -s "$BASE_URL/api/v1/routing" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['routes']))")
echo "  路由规则: $ROUTES"

# 4. 测试任务执行
RESULT=$(curl -s -X POST "$BASE_URL/api/v1/execute" \
  -H "Content-Type: application/json" \
  -d '{"task": "Hello world"}')
SUCCESS=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success', False))")
echo "  任务执行: $([ "$SUCCESS" = "True" ] && echo '✅ 正常' || echo '❌ 异常')"

if [ "$STATUS" = "ok" ] && [ "$AGENTS" = "20" ] && [ "$SUCCESS" = "True" ]; then
    echo -e "\n🎉 所有检查通过！"
    exit 0
else
    echo -e "\n⚠️ 部分检查未通过，请检查服务日志"
    exit 1
fi
```

---

## 📊 常见使用场景

| 场景 | 推荐Agent | 示例任务 |
|------|----------|---------|
| 新品调研 | ProductResearchAgent | "分析户外露营装备市场" |
| Listing优化 | ListingOptimizerAgent | "优化我的瑜伽垫标题" |
| 广告调价 | PPCManagerAgent | "ACOS 40%太高，怎么优化" |
| 库存预警 | InventoryPlannerAgent | "补货建议，SKU-001" |
| 差评处理 | ReviewMonitorAgent | "收到差评怎么回复" |
| 跟卖检测 | HijackerDetectorAgent | "检测是否有跟卖" |
| 利润核算 | ProfitCalculatorAgent | "计算FBA利润" |
| 合规检查 | ComplianceCheckerAgent | "检查主图合规性" |

---

> 📌 完整API文档：http://localhost:8080/docs
