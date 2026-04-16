"""
config/ams_config.py
=====================
AMS API 全局配置管理 — OAuth 2.0 凭证、速率限制、多账户配置

Author: 硅基军团 · AMS数据接入 Agent
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


# ─── 凭证环境变量前缀 ──────────────────────────────────────────────────────────
PREFIX = "AMS"


def _env(key: str, default: Optional[str] = None) -> Optional[str]:
    return os.environ.get(f"{PREFIX}_{key}", default)


# ─── AMS广告类型枚举 ──────────────────────────────────────────────────────────

@dataclass
class AMSAccountConfig:
    """单账户配置"""
    account_id: str                          # MWS/SellerCentral 账户ID
    region: str                              # us-east-1 | eu-west-1 | fe-west-1
    client_id: str                           # OAuth client_id
    client_secret: str                       # OAuth client_secret（建议从环境变量注入）
    refresh_token: str                       # OAuth refresh_token
    profile_id: str                          # Amazon Ads profile ID
    profile_name: str = ""                   # 账户别名
    enabled: bool = True
    rate_limit_rpm: int = 10                 # 每分钟请求上限（默认10RPM，小心SPS API）
    retry_attempts: int = 3
    timeout_seconds: int = 30

    def validate(self) -> list[str]:
        """返回缺失字段列表"""
        missing = []
        for f in ("account_id", "client_id", "client_secret", "refresh_token", "profile_id"):
            if not getattr(self, f):
                missing.append(f)
        return missing


@dataclass
class RateLimitConfig:
    """速率限制配置（各API不同）"""
    # Sponsored Products
    sp_campaigns_rpm: int = 10
    sp_keywords_rpm: int = 20
    sp_portfolio_rpm: int = 5
    sp_reports_rpm: int = 2     # 报告API最严格
    # Sponsored Brands
    sb_rpm: int = 10
    # Sponsored Display
    sd_rpm: int = 10
    # Marketing Stream
    stream_rpm: int = 60
    # 重试退避参数
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    exponential_base: float = 2.0
    jitter_factor: float = 0.1   # ±10% 随机抖动


@dataclass
class CacheConfig:
    """缓存配置"""
    enabled: bool = True
    ttl_seconds: int = 240       # 默认4分钟（<5分钟延迟目标）
    max_entries: int = 10000
    storage_path: str = "data/ams_cache.db"  # SQLite后端
    # 各数据类型TTL（秒）
    ttl_campaigns: int = 300      # 5分钟
    ttl_keywords: int = 120       # 2分钟
    ttl_performance: int = 60     # 1分钟
    ttl_budget: int = 60          # 1分钟


@dataclass
class PipelineConfig:
    """数据管道配置"""
    polling_interval_seconds: int = 60    # 默认每60秒拉取一次
    batch_size: int = 500                  # 每批处理记录数
    max_queue_size: int = 10000
    flush_interval_seconds: int = 30
    enable_stream: bool = True             # 启用Marketing Stream
    stream_base_url: str = "https://advertising-api-eu.amazon.com"
    # 数据保留
    retention_days: int = 90               # 历史数据保留天数
    archive_after_days: int = 30           # 多少天后归档
    # ProfitOptimizer集成
    push_to_optimizer: bool = True         # 是否实时推送ProfitOptimizer
    optimizer_endpoint: str = "http://localhost:8080/api/v1/ams_metrics"


@dataclass
class AMSConfig:
    """AMS全局配置容器"""
    accounts: list[AMSAccountConfig] = field(default_factory=list)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    # 全局
    log_level: str = "INFO"
    log_requests: bool = False              # 是否记录API请求（敏感数据脱敏后）
    global_timeout_seconds: int = 30
    default_region: str = "us-east-1"

    # ── 便捷访问器 ─────────────────────────────────────────────────────────────

    def get_account(self, account_id: str) -> Optional[AMSAccountConfig]:
        return next((a for a in self.accounts if a.account_id == account_id), None)

    def enabled_accounts(self) -> list[AMSAccountConfig]:
        return [a for a in self.accounts if a.enabled]

    def primary_account(self) -> Optional[AMSAccountConfig]:
        """返回第一个启用的账户"""
        enabled = self.enabled_accounts()
        return enabled[0] if enabled else None


# ─── YAML 加载器 ──────────────────────────────────────────────────────────────

DEFAULT_CONFIG_PATH = Path("config/ams.yaml")
ENV_CONFIG_PATH_KEY = "AMS_CONFIG_PATH"


@dataclass
class ConfigLoader:
    """配置加载器（支持YAML + 环境变量覆盖）"""
    path: Path = field(default=DEFAULT_CONFIG_PATH)

    def load(self) -> AMSConfig:
        if not self.path.exists():
            return self._from_env()

        with open(self.path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        return self._parse_yaml(raw)

    def _parse_yaml(self, raw: dict) -> AMSConfig:
        """解析YAML配置"""
        accounts = []
        for acc_raw in raw.get("accounts", []):
            acc = AMSAccountConfig(
                account_id=acc_raw.get("account_id", ""),
                region=acc_raw.get("region", "us-east-1"),
                client_id=acc_raw.get("client_id", ""),
                client_secret=acc_raw.get("client_secret", ""),
                refresh_token=acc_raw.get("refresh_token", ""),
                profile_id=acc_raw.get("profile_id", ""),
                profile_name=acc_raw.get("profile_name", ""),
                enabled=acc_raw.get("enabled", True),
                rate_limit_rpm=acc_raw.get("rate_limit_rpm", 10),
                retry_attempts=acc_raw.get("retry_attempts", 3),
                timeout_seconds=acc_raw.get("timeout_seconds", 30),
            )
            # 允许环境变量覆盖
            env_secret = _env(f"ACCOUNT_{acc.account_id}_CLIENT_SECRET")
            if env_secret:
                acc.client_secret = env_secret
            env_refresh = _env(f"ACCOUNT_{acc.account_id}_REFRESH_TOKEN")
            if env_refresh:
                acc.refresh_token = env_refresh
            accounts.append(acc)

        rate_raw = raw.get("rate_limit", {})
        rate = RateLimitConfig(
            sp_campaigns_rpm=rate_raw.get("sp_campaigns_rpm", 10),
            sp_keywords_rpm=rate_raw.get("sp_keywords_rpm", 20),
            sp_portfolio_rpm=rate_raw.get("sp_portfolio_rpm", 5),
            sp_reports_rpm=rate_raw.get("sp_reports_rpm", 2),
            sb_rpm=rate_raw.get("sb_rpm", 10),
            sd_rpm=rate_raw.get("sd_rpm", 10),
            stream_rpm=rate_raw.get("stream_rpm", 60),
        )

        cache_raw = raw.get("cache", {})
        cache = CacheConfig(
            enabled=cache_raw.get("enabled", True),
            ttl_seconds=cache_raw.get("ttl_seconds", 240),
            max_entries=cache_raw.get("max_entries", 10000),
            storage_path=cache_raw.get("storage_path", "data/ams_cache.db"),
            ttl_campaigns=cache_raw.get("ttl_campaigns", 300),
            ttl_keywords=cache_raw.get("ttl_keywords", 120),
            ttl_performance=cache_raw.get("ttl_performance", 60),
            ttl_budget=cache_raw.get("ttl_budget", 60),
        )

        pipeline_raw = raw.get("pipeline", {})
        pipeline = PipelineConfig(
            polling_interval_seconds=pipeline_raw.get("polling_interval_seconds", 60),
            batch_size=pipeline_raw.get("batch_size", 500),
            max_queue_size=pipeline_raw.get("max_queue_size", 10000),
            flush_interval_seconds=pipeline_raw.get("flush_interval_seconds", 30),
            enable_stream=pipeline_raw.get("enable_stream", True),
            stream_base_url=pipeline_raw.get("stream_base_url", "https://advertising-api-eu.amazon.com"),
            retention_days=pipeline_raw.get("retention_days", 90),
            archive_after_days=pipeline_raw.get("archive_after_days", 30),
            push_to_optimizer=pipeline_raw.get("push_to_optimizer", True),
            optimizer_endpoint=pipeline_raw.get("optimizer_endpoint", "http://localhost:8080/api/v1/ams_metrics"),
        )

        return AMSConfig(
            accounts=accounts,
            rate_limit=rate,
            cache=cache,
            pipeline=pipeline,
            log_level=raw.get("log_level", "INFO"),
            log_requests=raw.get("log_requests", False),
            global_timeout_seconds=raw.get("global_timeout_seconds", 30),
            default_region=raw.get("default_region", "us-east-1"),
        )

    def _from_env(self) -> AMSConfig:
        """纯环境变量模式（无YAML文件时）"""
        account = AMSAccountConfig(
            account_id=_env("ACCOUNT_ID", "dev_account"),
            region=_env("REGION", "us-east-1"),
            client_id=_env("CLIENT_ID", "dev_client_id"),
            client_secret=_env("CLIENT_SECRET", ""),
            refresh_token=_env("REFRESH_TOKEN", ""),
            profile_id=_env("PROFILE_ID", "dev_profile"),
            profile_name=_env("PROFILE_NAME", "Development Account"),
        )
        return AMSConfig(
            accounts=[account],
            log_level=_env("LOG_LEVEL", "INFO"),
        )


# ─── 默认实例 ─────────────────────────────────────────────────────────────────

def load_config(path: Optional[str] = None) -> AMSConfig:
    cfg_path = Path(path or os.environ.get(ENV_CONFIG_PATH_KEY, DEFAULT_CONFIG_PATH))
    loader = ConfigLoader(path=cfg_path)
    return loader.load()


# ─── 验证工具 ─────────────────────────────────────────────────────────────────

def validate_config(cfg: AMSConfig) -> dict[str, list[str]]:
    """
    验证配置完整性，返回 {account_id: [缺失字段列表]}
    """
    issues: dict[str, list[str]] = {}
    for acc in cfg.accounts:
        missing = acc.validate()
        if missing:
            issues[acc.account_id] = missing
    return issues


# ─── 样例YAML（供参考） ───────────────────────────────────────────────────────
SAMPLE_YAML = """
# amazon-ops-agents/config/ams.yaml
# AMS API配置示例（请勿提交真实凭证到版本控制！）

accounts:
  - account_id: "ACTDEV123456"
    region: "us-east-1"
    client_id: "${AMS_ACCOUNT_ACTDEV123456_CLIENT_SECRET}"
    client_secret: "${AMS_ACCOUNT_ACTDEV123456_CLIENT_SECRET}"
    refresh_token: "${AMS_ACCOUNT_ACTDEV123456_REFRESH_TOKEN}"
    profile_id: "123456789"
    profile_name: "US Main Account"
    enabled: true
    rate_limit_rpm: 10
    retry_attempts: 3

rate_limit:
  sp_campaigns_rpm: 10
  sp_keywords_rpm: 20
  sp_portfolio_rpm: 5
  sp_reports_rpm: 2
  sb_rpm: 10
  sd_rpm: 10
  stream_rpm: 60
  base_delay_seconds: 1.0
  max_delay_seconds: 60.0

cache:
  enabled: true
  ttl_campaigns: 300
  ttl_keywords: 120
  ttl_performance: 60
  ttl_budget: 60

pipeline:
  polling_interval_seconds: 60
  batch_size: 500
  push_to_optimizer: true
  optimizer_endpoint: "http://localhost:8080/api/v1/ams_metrics"
  enable_stream: true

log_level: INFO
"""
