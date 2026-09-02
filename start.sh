#!/usr/bin/env bash

# ==============================================================================
# HPoker 风格多人在线德州扑克系统 - 一键启动脚本
# ==============================================================================

set -e

# 获取脚本所在根目录绝对路径
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# ANSI 颜色与样式
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# 打印横幅
print_banner() {
    echo -e "${CYAN}${BOLD}"
    echo "======================================================================"
    echo "  ♠ ♥ ♣ ♦   HPoker 风格多人在线德州扑克系统 (Texas Hold'em)   ♦ ♣ ♥ ♠  "
    echo "======================================================================"
    echo -e "${NC}"
}

# 获取本机局域网 IP
get_local_ip() {
    local ip
    ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    if [ -z "$ip" ]; then
        ip=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7}')
    fi
    if [ -z "$ip" ]; then
        ip="127.0.0.1"
    fi
    echo "$ip"
}

# 端口清理工具函数
kill_port() {
    local port=$1
    local name=$2
    local pids=""
    
    if command -v lsof >/dev/null 2>&1; then
        pids=$(lsof -ti :"$port" 2>/dev/null || true)
    elif command -v fuser >/dev/null 2>&1; then
        pids=$(fuser "$port"/tcp 2>/dev/null || true)
    fi

    if [ -n "$pids" ]; then
        echo -e "${YELLOW}  [!] 发现端口 :${port} (${name}) 已被进程占用 (PID: ${pids})，正在释放...${NC}"
        for pid in $pids; do
            kill -9 "$pid" 2>/dev/null || true
        done
        sleep 0.5
        echo -e "${GREEN}  [✓] 端口 :${port} 已释放。${NC}"
    fi
}

# 检查并自动初始化环境
check_and_init_env() {
    echo -e "${BOLD}${BLUE}🔍 检查运行环境与依赖...${NC}"

    # 1. 检查 Python 虚拟环境
    if [ ! -d "$PROJECT_ROOT/.venv" ] || [ ! -f "$PROJECT_ROOT/.venv/bin/python" ]; then
        echo -e "${YELLOW}  [!] 未检测到 Python 虚拟环境，正在自动创建 .venv ...${NC}"
        if ! command -v python3 >/dev/null 2>&1; then
            echo -e "${RED}  [✗] 错误: 未安装 Python 3，请先安装 Python 3.11+ 后重试。${NC}"
            exit 1
        fi
        python3 -m venv "$PROJECT_ROOT/.venv"
        echo -e "${GREEN}  [✓] 虚拟环境创建成功。${NC}"
    fi

    # 2. 检查后端依赖。仅检查 uvicorn 会让旧虚拟环境继续使用不兼容的
    # FastAPI/Starlette 组合，最终使 TestClient 请求永久等待。
    if [ ! -f "$PROJECT_ROOT/.venv/bin/uvicorn" ] || ! "$PROJECT_ROOT/.venv/bin/python" -c \
        'from importlib.metadata import version; expected = {"fastapi": "0.115.6", "starlette": "0.41.3", "httpx": "0.28.1", "anyio": "4.8.0", "httpcore": "1.0.7"}; actual = {name: version(name) for name in expected}; raise SystemExit(0 if actual == expected else 1)' 2>/dev/null; then
        echo -e "${YELLOW}  [!] 正在安装/修复后端依赖 (backend/requirements.txt)...${NC}"
        "$PROJECT_ROOT/.venv/bin/pip" install --upgrade pip >/dev/null 2>&1 || true
        "$PROJECT_ROOT/.venv/bin/pip" install -r "$PROJECT_ROOT/backend/requirements.txt"
        echo -e "${GREEN}  [✓] 后端依赖安装完成。${NC}"
    fi

    # 3. 检查前端 node_modules
    if [ ! -d "$PROJECT_ROOT/frontend/node_modules" ]; then
        echo -e "${YELLOW}  [!] 未检测到前端依赖，正在自动执行 npm install ...${NC}"
        if ! command -v npm >/dev/null 2>&1; then
            echo -e "${RED}  [✗] 错误: 未安装 Node.js/npm，请先安装 Node.js 18+ 后重试。${NC}"
            exit 1
        fi
        (cd "$PROJECT_ROOT/frontend" && npm install)
        echo -e "${GREEN}  [✓] 前端依赖安装完成。${NC}"
    fi

    echo -e "${GREEN}${BOLD}  [✓] 环境检查完毕，所有依赖已就绪！${NC}\n"
}

# 启动开发环境 (前后端联调模式，支持热重载)
start_dev() {
    print_banner
    check_and_init_env

    echo -e "${BOLD}${PURPLE}🚀 正在启动 HPoker 开发服务 (前后端双引擎)...${NC}\n"

    # 清理占用端口
    kill_port 8000 "FastAPI 后端"
    kill_port 5173 "Vite 前端"

    local LOCAL_IP
    LOCAL_IP=$(get_local_ip)

    # 启动后端 (FastAPI + WebSocket)
    "$PROJECT_ROOT/.venv/bin/uvicorn" backend.main:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!

    # 启动前端 (Vite Dev Server)
    (cd "$PROJECT_ROOT/frontend" && npm run dev) &
    FRONTEND_PID=$!

    # 进程优雅退出捕获
    cleanup() {
        echo -e "\n\n${YELLOW}🛑 收到终止信号，正在关闭所有服务...${NC}"
        kill "$BACKEND_PID" 2>/dev/null || true
        kill "$FRONTEND_PID" 2>/dev/null || true
        kill_port 8000 "FastAPI 后端"
        kill_port 5173 "Vite 前端"
        echo -e "${GREEN}✓ 所有服务已安全退出。祝游戏愉快！${NC}"
        exit 0
    }
    trap cleanup SIGINT SIGTERM EXIT

    sleep 1

    echo -e "\n${GREEN}${BOLD}======================================================================${NC}"
    echo -e "${GREEN}${BOLD}  🎉 服务启动成功！请通过以下地址进入游戏：${NC}"
    echo -e "${GREEN}${BOLD}======================================================================${NC}"
    echo -e "  🌐 ${BOLD}本地浏览器访问${NC} :  ${CYAN}${BOLD}http://localhost:5173${NC}"
    echo -e "  📱 ${BOLD}局域网/手机加入${NC} :  ${CYAN}${BOLD}http://${LOCAL_IP}:5173${NC}"
    echo -e "  🔌 ${BOLD}后端 API 服务${NC}  :  ${BLUE}http://localhost:8000${NC}"
    echo -e "  📖 ${BOLD}API 交互式文档${NC} :  ${BLUE}http://localhost:8000/docs${NC}"
    echo -e "${GREEN}${BOLD}======================================================================${NC}"
    echo -e "  ${YELLOW}💡 提示: 按 ${BOLD}Ctrl + C${NC}${YELLOW} 可一键关闭全部服务并释放端口${NC}\n"

    # 阻塞等待子进程
    wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}

# 启动生产模式 (编译前端并由 FastAPI 单端口统一承载)
start_prod() {
    print_banner
    check_and_init_env

    echo -e "${BOLD}${PURPLE}📦 正在编译前端静态资源 (npm run build)...${NC}"
    (cd "$PROJECT_ROOT/frontend" && npm run build)
    echo -e "${GREEN}  [✓] 前端资源编译完成！${NC}\n"

    kill_port 8000 "FastAPI 生产服务"

    local LOCAL_IP
    LOCAL_IP=$(get_local_ip)

    echo -e "${BOLD}${PURPLE}🚀 正在启动生产统一服务 (FastAPI 单端口 8000 托管全站)...${NC}\n"

    # 进程优雅退出捕获
    cleanup_prod() {
        echo -e "\n\n${YELLOW}🛑 收到终止信号，正在关闭服务...${NC}"
        kill_port 8000 "FastAPI 生产服务"
        echo -e "${GREEN}✓ 生产服务已安全退出。${NC}"
        exit 0
    }
    trap cleanup_prod SIGINT SIGTERM EXIT

    echo -e "${GREEN}${BOLD}======================================================================${NC}"
    echo -e "${GREEN}${BOLD}  🎉 生产服务就绪！${NC}"
    echo -e "${GREEN}${BOLD}======================================================================${NC}"
    echo -e "  🌐 ${BOLD}本地浏览器访问${NC} :  ${CYAN}${BOLD}http://localhost:8000${NC}"
    echo -e "  📱 ${BOLD}局域网/手机加入${NC} :  ${CYAN}${BOLD}http://${LOCAL_IP}:8000${NC}"
    echo -e "  📖 ${BOLD}API 接口文档${NC}   :  ${BLUE}http://localhost:8000/docs${NC}"
    echo -e "${GREEN}${BOLD}======================================================================${NC}"
    echo -e "  ${YELLOW}💡 提示: 按 ${BOLD}Ctrl + C${NC}${YELLOW} 可停止服务${NC}\n"

    "$PROJECT_ROOT/.venv/bin/uvicorn" backend.main:app --host 0.0.0.0 --port 8000
}

# 仅启动后端
start_backend_only() {
    print_banner
    check_and_init_env
    kill_port 8000 "FastAPI 后端"
    echo -e "${BOLD}${PURPLE}🚀 启动单独后端服务 (http://localhost:8000)...${NC}\n"
    "$PROJECT_ROOT/.venv/bin/uvicorn" backend.main:app --host 0.0.0.0 --port 8000 --reload
}

# 仅启动前端
start_frontend_only() {
    print_banner
    check_and_init_env
    kill_port 5173 "Vite 前端"
    echo -e "${BOLD}${PURPLE}🚀 启动单独前端服务 (http://localhost:5173)...${NC}\n"
    (cd "$PROJECT_ROOT/frontend" && npm run dev)
}

# 启动轻量 CLI 客户端
start_cli() {
    check_and_init_env
    shift 1 2>/dev/null || true
    "$PROJECT_ROOT/.venv/bin/python" "$PROJECT_ROOT/poker_cli.py" "$@"
}

# 运行自动化测试套件
run_tests() {
    print_banner
    check_and_init_env
    echo -e "${BOLD}${PURPLE}🧪 正在运行后端单元测试套件 (Pytest)...${NC}\n"
    "$PROJECT_ROOT/.venv/bin/pytest" backend/tests/ "$@"
}

# 停止所有相关进程
stop_all() {
    echo -e "${BOLD}${YELLOW}🛑 正在清理所有占用 8000 及 5173 端口的进程...${NC}"
    kill_port 8000 "FastAPI 后端"
    kill_port 5173 "Vite 前端"
    echo -e "${GREEN}✓ 所有服务进程已停止。${NC}"
}

# 帮助说明
show_help() {
    print_banner
    echo -e "${BOLD}使用方法:${NC}"
    echo -e "  ./start.sh [命令]\n"
    echo -e "${BOLD}可用命令列表:${NC}"
    echo -e "  ${CYAN}./start.sh${NC}          - 默认启动：同时启动前后端热重载开发服务 (推荐)"
    echo -e "  ${CYAN}./start.sh dev${NC}      - 等同于默认启动"
    echo -e "  ${CYAN}./start.sh prod${NC}     - 编译前端并以生产模式单端口 (8000) 运行"
    echo -e "  ${CYAN}./start.sh backend${NC}  - 仅启动后端服务 (FastAPI, 端口 8000)"
    echo -e "  ${CYAN}./start.sh frontend${NC} - 仅启动前端服务 (Vite, 端口 5173)"
    echo -e "  ${CYAN}./start.sh cli${NC}      - 启动轻量 CLI 终端客户端"
    echo -e "  ${CYAN}./start.sh test${NC}     - 运行后端单元测试套件"
    echo -e "  ${CYAN}./start.sh stop${NC}     - 停止并杀死后台残留的 8000 与 5173 端口进程"
    echo -e "  ${CYAN}./start.sh help${NC}     - 显示此帮助信息\n"
}

# 参数路由分发
case "$1" in
    ""|"dev")
        start_dev
        ;;
    "prod"|"build-run")
        start_prod
        ;;
    "backend"|"server"|"api")
        start_backend_only
        ;;
    "frontend"|"ui"|"client")
        start_frontend_only
        ;;
    "cli"|"terminal"|"tui")
        start_cli "$@"
        ;;
    "test"|"pytest")
        shift
        run_tests "$@"
        ;;
    "stop"|"kill")
        stop_all
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    *)
        echo -e "${RED}未知命令: $1${NC}\n"
        show_help
        exit 1
        ;;
esac
