# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-04-13

### Added
- 初始版本发布
- 1个幕僚长（ChiefOfStaff）智能调度中心
- 20个专业Agent，覆盖亚马逊运营全链路：
  - 选品分析（2个）：ProductResearchAgent、NicheFinderAgent
  - Listing优化（3个）：ListingOptimizerAgent、KeywordResearchAgent、AContentGeneratorAgent
  - 广告投放（2个）：PPCManagerAgent、SponsoredAdsAgent
  - 库存管理（2个）：InventoryPlannerAgent、FbaManagerAgent
  - 定价策略（2个）：PriceOptimizerAgent、RepricingAgent
  - 评论管理（2个）：ReviewMonitorAgent、VINEProgramAgent
  - 品牌保护（2个）：BrandRegistryAgent、HijackerDetectorAgent
  - 数据分析（2个）：SalesAnalyticsAgent、ProfitCalculatorAgent
  - 客户服务（1个）：CustomerServiceAgent
  - 合规风控（2个）：ComplianceCheckerAgent、AccountHealthAgent
- FastAPI服务，端口8080
- Amazon SP-API集成支持
- 关键词路由调度引擎
- 完整定价方案（基础版/专业版/企业版）
- 测试用例（tests/test_demo.py）
