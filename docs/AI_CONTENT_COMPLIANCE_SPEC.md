# ClawHub 亚马逊生态技能包 · AI 内容合规接入规范

> 版本：v1.0（2026-03） | 适用：brand-accelerator / expansion-playbook / pricing-intelligence / seasonal-planner 及未来所有涉及产品图/Listing 内容生成的亚马逊生态技能
> 背景：亚马逊要求 AI 生成的逼真人物图片添加元数据披露标签；TikTok Shop 要求标注 AI 生成内容并禁止 AI 篡改商品外观/捏造不实效果。凡涉及内容生成的技能，发布前必须通过本文档的合规检查。

---

## 一、新规要点速览（发布前必读）

| 平台 | 要求 | 违规后果 |
|---|---|---|
| **亚马逊** | AI 生成的逼真人物图（Listing 主图/A+/旗舰店/广告）须在图片元数据添加 AI 披露标签（`contains-synthetic-performer` / `synthetic-media`） | 图片拒审、Listing 下架、账号健康度扣分 |
| **TikTok Shop** | ① AI 生成内容（图/视频/直播）须显著标注；② 禁止 AI 篡改商品外观；③ 禁止 AI 捏造不实效果 | 商品下架、限流、封店 |

**判定口诀**：
- 有真人 + AI 生成/深度合成 → 必须打 AI 披露标签
- 纯产品图（无人物）→ 不受人物披露约束，但仍需与实物一致
- 实拍素材 → 完全规避 AI 披露要求（最稳妥）

---

## 二、四个技能各自的合规落点

### 1. brand-accelerator（品牌加速器）
- **涉及内容**：品牌故事、A+ 页面、旗舰店素材、品牌形象图
- **合规要求**：
  - A+ 内容中 AI 人物图（模特/生活方式场景）→ 元数据加 synthetic-media 标签
  - 品牌形象图若用 AI 生成代言人/模特 → 需披露，或改用实拍
  - 输出交付物中必须附带 `ai_content_compliance` 检查结果

### 2. expansion-playbook（扩张作战手册）
- **涉及内容**：多站点/多品类 Listing 模板、市场进入素材包
- **合规要求**：
  - 生成的 Listing 模板需内置 AI 合规占位提示（提醒卖家打标）
  - 跨站点内容需区分亚马逊 vs TikTok Shop 规则
  - 站点扩展清单中增加「AI 内容合规检查」步骤

### 3. pricing-intelligence（定价情报）
- **涉及内容**：价格报告、定价策略、竞品价格对比图
- **合规要求**：
  - 价格对比图/信息图为纯数据图表 → 通常无人物，不涉及 AI 人物披露
  - 但若用 AI 生成"价格趋势模拟场景图"（含人物购物场景）→ 需打标
  - 禁止用 AI 生成虚构价格截图或虚假促销效果

### 4. seasonal-planner（季节营销规划器）
- **涉及内容**：节日营销素材、季节主题 Listing、活动海报
- **合规要求**：
  - 节日海报/主题图大量使用 AI 生成人物（圣诞老人、节日模特）→ **必须打标**
  - 季节营销视频（TikTok Shop 投放）→ 显著标注 AI 生成
  - 禁止 AI 生成"节日爆单效果"类夸大素材

---

## 三、技术接入标准（可直接复用 amazon-ops 合规层）

```python
# 复用 amazon-ops/compliance/ai_content_rules.py（已在 ClawHub 技能包 v2.1 中发布）
from compliance import (
    check_ai_content_compliance,
    ai_image_label_required,
    amazon_ai_metadata_tags,
    tiktok_ai_disclosure_required,
)

# 示例：seasonal-planner 生成一张 AI 圣诞模特海报
r = check_ai_content_compliance(
    platform="all",
    image_has_real_human=True,      # 含模特人物
    image_is_ai_generated=True,     # AI 生成
    tiktok_is_ai_content=True,      # 同时投 TikTok Shop
)
print(r["risk_level"], r["all_pass"])
# → medium, False（需标注）

# 获取应添加的元数据标签
tags = amazon_ai_metadata_tags(has_real_human=True, is_ai_generated=True)
# → ["contains-synthetic-performer", "synthetic-media"]
```

**接入清单（每个技能发布前逐项打勾）**：

- [ ] 引用合规规则库（或内置等价规则）
- [ ] 内容生成类工具/Agent 输出中附带 `ai_content_compliance` 检查结果
- [ ] 交付物模板中包含 AI 打标提示（含具体标签名）
- [ ] clawhub.yaml 的 keywords/triggers 增加 AI 合规相关词（ai-compliance/aigc/AI合规/AI生成）
- [ ] SKILL.md 增加「AI 内容合规」章节
- [ ] 提供实拍替代建议（告诉卖家最稳妥路径）
- [ ] 单元测试覆盖：需标注/不需标注/违规整改三场景

---

## 四、合规检查函数说明

| 函数 | 作用 |
|---|---|
| `ai_image_label_required(has_real_human, is_ai_generated, is_ai_modified)` | 判断亚马逊图片是否必须打 AI 人物披露标签 |
| `amazon_ai_metadata_tags(...)` | 返回应写入元数据的标签列表 |
| `tiktok_ai_disclosure_required(is_ai_content, is_product_appearance_modified, is_fake_effect)` | TikTok Shop AIGC 标注 + 违规判定 |
| `check_ai_content_compliance(platform, ...)` | 双平台综合检查入口 |

---

## 五、给卖家的合规话术（技能内置提示文案）

> ⚠️ **亚马逊新规提醒**：本素材包含 AI 生成人物形象，请在图片元数据中添加 AI 披露标签（`contains-synthetic-performer`），否则可能面临图片拒审/Listing 下架风险。如需完全规避，可改用真人实拍素材。
>
> ⚠️ **TikTok Shop 提醒**：AI 生成内容须显著标注；严禁 AI 篡改商品外观或捏造不实效果，违者下架/封店。

---

*规范维护：ClawHub 亚马逊技能包发布流程 · 配套规则库：`amazon-ops/compliance/ai_content_rules.py`*
