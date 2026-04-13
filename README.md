# 亚马逊运营硅基军团

面向亚马逊跨境电商卖家的AI运营平台——**1个幕僚长 + 20个专业Agent**，覆盖选品/Listing优化/广告投放/库存管理/定价策略/评论管理/品牌保护/数据分析/客户服务/合规风控全链路。

## 🎯 定价方案

| 版本 | 价格 | 周期 | 推荐场景 |
|------|------|------|----------|
| **基础版** | ¥599 | 月 | 新手卖家 |
| **专业版** ⭐ | ¥2,999 | 月 | 成长期卖家 |
| **企业版** | ¥29,999 | 月 | 大卖家/品牌方 |

详见 [PRICING.md](./PRICING.md)

## ⚡ 快速启动

```bash
pip install -r requirements.txt
python api_server.py
# → http://localhost:8080
```

API文档：http://localhost:8080/docs

## 🏗️ 团队架构

### 幕僚长（ChiefOfStaff）
智能任务调度中心，理解用户意图并分发给专业Agent，支持并行执行与结果聚合。

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

## 📌 使用示例

```bash
# 选品分析
curl -X POST http://localhost:8080/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "帮我分析这个产品能不能做：无线蓝牙耳机", "marketplace": "US"}'

# 广告优化
curl -X POST http://localhost:8080/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "我的广告ACOS太高了，怎么优化", "sku": "ABC123"}'

# 差评处理
curl -X POST http://localhost:8080/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "收到一个1星差评，说耳机续航不行，怎么回复", "asin": "B0XXXXXX"}'
```

## 🔧 技术栈

- **语言**：Python 3.10+
- **框架**：FastAPI + Uvicorn
- **调度**：关键词路由 + async 并发
- **API**：Amazon SP-API（官方）
- **集成**：Helium 10 / Jungle Scout / Keepa

## 📁 项目结构

```
amazon-ops-agents/
├── SKILL.md                   # 技能定义（行为手册）
├── README.md                  # 项目说明
├── CHANGELOG.md               # 版本记录
├── PRICING.md                 # 定价方案
├── LICENSE                    # MIT协议
├── requirements.txt           # Python依赖
├── api_server.py             # FastAPI服务入口
├── agents/                   # Agent实现
│   ├── __init__.py
│   ├── chief_of_staff.py     # 幕僚长
│   ├── product_research.py   # 选品分析
│   ├── niche_finder.py       # 细分市场
│   ├── listing_optimizer.py  # Listing优化
│   ├── keyword_research.py   # 关键词研究
│   ├── acontent_generator.py # A+内容
│   ├── ppc_manager.py        # 广告管理
│   ├── sponsored_ads.py      # SP/SB/SD广告
│   ├── inventory_planner.py  # 库存规划
│   ├── fba_manager.py        # FBA管理
│   ├── price_optimizer.py   # 定价策略
│   ├── repricing.py          # 自动调价
│   ├── review_monitor.py     # 评论监控
│   ├── vine_program.py       # Vine计划
│   ├── brand_registry.py     # 品牌保护
│   ├── hijacker_detector.py  # 跟卖检测
│   ├── sales_analytics.py    # 销售分析
│   ├── profit_calculator.py  # 利润计算
│   ├── customer_service.py   # 客服
│   ├── compliance_checker.py # 合规检查
│   └── account_health.py     # 账号健康
├── scripts/                  # 工具脚本
│   ├── routing.py           # 路由逻辑
│   └── utils.py             # 工具函数
├── references/              # 参考文档
│   ├── amazon-api-guide.md  # Amazon API指南
│   └── best-practices.md     # 最佳实践
└── tests/                   # 测试文件
    └── test_agents.py
```

## 🌐 支持站点

- 🇺🇸 Amazon.com（美国）
- 🇬🇧 Amazon.co.uk（英国）
- 🇩🇪 Amazon.de（德国）
- 🇫🇷 Amazon.fr（法国）
- 🇯🇵 Amazon.co.jp（日本）
- 更多站点持续扩展中……

## 📦 版本历史

详见 [CHANGELOG.md](./CHANGELOG.md)

## 📄 License

MIT License
