#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# Railway 部署启动脚本
# 亚马逊运营硅基军团 — 一键部署到 Railway
# ══════════════════════════════════════════════════════════════════════════════
#
# 使用方法：
#   chmod +x scripts/deploy-railway.sh
#   ./scripts/deploy-railway.sh
#
# 前置条件：
#   1. GitHub 账号 (https://github.com)
#   2. Railway 账号 (https://railway.app，用 GitHub OAuth 注册)
#
# ══════════════════════════════════════════════════════════════════════════════

set -e

echo "═══════════════════════════════════════════════════════"
echo "  亚马逊运营硅基军团 — Railway 云端部署"
echo "═══════════════════════════════════════════════════════"
echo ""

# ── 颜色输出 ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ── 检查依赖 ──────────────────────────────────────────────────────────────────
check_command() {
    if ! command -v $1 &> /dev/null; then
        log_error "$1 未安装，请先安装：$2"
        exit 1
    fi
}

log_info "检查依赖..."
check_command node "npm install -g @railway/cli"
check_command git "brew install git"

# ── Railway CLI 安装 ───────────────────────────────────────────────────────────
install_railway_cli() {
    if command -v railway &> /dev/null; then
        log_info "Railway CLI 已安装: $(railway --version 2>/dev/null || echo 'unknown')"
        return
    fi
    log_info "安装 Railway CLI..."
    npm install -g @railway/cli
}

# ── Railway 登录 ──────────────────────────────────────────────────────────────
railway_login() {
    log_info "开始 Railway 登录..."
    railway login
    log_info "Railway 登录成功！"
}

# ── 项目初始化 ────────────────────────────────────────────────────────────────
init_project() {
    local project_dir="$1"
    
    if [ ! -f "$project_dir/railway.toml" ]; then
        log_error "未找到 railway.toml，请确保在 amazon-ops-agents 目录下运行"
        exit 1
    fi
    
    cd "$project_dir"
    
    log_info "链接 Railway 项目..."
    railway init
    
    log_info "Railway 项目已初始化"
}

# ── 环境变量配置 ──────────────────────────────────────────────────────────────
setup_variables() {
    log_info "配置环境变量..."
    
    echo ""
    echo "请提供以下信息（直接从 .env.example 获取真实值）："
    echo ""
    
    read -p "AMAZON_OPS_API_KEY: " api_key
    read -sp "AMAZON_OPS_API_SECRET: " api_secret
    echo ""
    read -p "DEEPSEEK_API_KEY (可选，留空跳过): " deepseek_key
    read -p "OPENAI_API_KEY (可选，留空跳过): " openai_key
    
    # 设置必需变量
    railway variables set AMAZON_OPS_API_KEY "$api_key"
    railway variables set AMAZON_OPS_API_SECRET "$api_secret"
    railway variables set LOG_LEVEL "INFO"
    railway variables set DEBUG "false"
    
    # 设置 LLM Provider（至少一个）
    if [ -n "$deepseek_key" ]; then
        railway variables set DEEPSEEK_API_KEY "$deepseek_key"
        log_info "✓ DeepSeek API Key 已配置"
    elif [ -n "$openai_key" ]; then
        railway variables set OPENAI_API_KEY "$openai_key"
        log_info "✓ OpenAI API Key 已配置"
    else
        log_warn "未配置 LLM Provider，请在 Railway Dashboard 中配置 DEEPSEEK_API_KEY"
    fi
    
    log_info "环境变量配置完成！"
}

# ── 部署 ──────────────────────────────────────────────────────────────────────
deploy() {
    log_info "开始部署到 Railway..."
    
    railway up --production
    
    echo ""
    log_info "部署完成！"
    echo ""
    echo "获取访问地址："
    railway domain
    echo ""
    echo "健康检查："
    echo "  curl \$(railway domain)/health"
    echo ""
    echo "查看日志："
    echo "  railway logs -f"
    echo ""
}

# ── 主流程 ────────────────────────────────────────────────────────────────────
main() {
    # 确定项目目录
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    
    cd "$PROJECT_DIR"
    
    echo "当前目录: $(pwd)"
    echo ""
    
    # 安装 Railway CLI
    install_railway_cli
    
    # Railway 登录
    railway_login
    
    # 项目初始化
    init_project "$PROJECT_DIR"
    
    # 环境变量配置
    setup_variables
    
    # 部署
    deploy
    
    echo ""
    echo "═══════════════════════════════════════════════════════"
    echo "  部署成功！"
    echo "═══════════════════════════════════════════════════════"
}

main "$@"
