"""
memory/__init__.py — 经验记忆闭环（v2.1）
==========================================
Agent 本地经验记忆层：失败修正策略与运营偏好沉淀到 SQLite，
下次同类任务自动检索注入 prompt；用户打分回写，低效经验自动停用。

闭环：注入 → 执行 → 用户打分 → 统计回写 → 坏经验下架/好经验加权
"""
from .experience_store import (
    ExperienceStore,
    apply_rating,
    create_experience,
    deactivate_experience,
    get_experience_store,
    list_experiences,
    retrieve_experiences,
)

__all__ = [
    "ExperienceStore",
    "get_experience_store",
    "create_experience",
    "list_experiences",
    "deactivate_experience",
    "retrieve_experiences",
    "apply_rating",
]
