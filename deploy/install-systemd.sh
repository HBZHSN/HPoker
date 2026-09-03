#!/usr/bin/env bash

set -euo pipefail

SERVICE_NAME="poker.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVICE_SOURCE="$SCRIPT_DIR/$SERVICE_NAME"
SERVICE_TARGET="/etc/systemd/system/$SERVICE_NAME"

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "请使用 sudo 执行：sudo $SCRIPT_DIR/install-systemd.sh" >&2
    exit 1
fi

if [ ! -x "$PROJECT_ROOT/.venv/bin/uvicorn" ]; then
    echo "未找到 $PROJECT_ROOT/.venv/bin/uvicorn，请先初始化项目虚拟环境。" >&2
    exit 1
fi

if [ ! -f "$SERVICE_SOURCE" ]; then
    echo "未找到服务模板：$SERVICE_SOURCE" >&2
    exit 1
fi

SERVICE_USER="${SUDO_USER:-$(stat -c '%U' "$PROJECT_ROOT")}"
if [ "$SERVICE_USER" = "root" ]; then
    SERVICE_USER="$(stat -c '%U' "$PROJECT_ROOT")"
fi
SERVICE_GROUP="$(id -gn "$SERVICE_USER")"
SERVICE_HOME="$(getent passwd "$SERVICE_USER" | cut -d: -f6)"

echo "[1/4] 构建前端生产资源..."
NPM_BIN="$(
    runuser -u "$SERVICE_USER" -- \
        env HOME="$SERVICE_HOME" bash -lc 'command -v npm' 2>/dev/null || true
)"
if [ ! -x "$NPM_BIN" ]; then
    for candidate in /usr/local/bin/npm /usr/bin/npm; do
        if [ -x "$candidate" ]; then
            NPM_BIN="$candidate"
            break
        fi
    done
fi
if [ ! -x "$NPM_BIN" ]; then
    NPM_BIN="$(
        { find -L "$SERVICE_HOME/.nvm/versions/node" \
            -mindepth 3 -maxdepth 3 -path '*/bin/npm' \
            -type f -perm -u+x -print 2>/dev/null || true; } \
            | sort -V | tail -n 1
    )"
fi
if [ ! -x "$NPM_BIN" ]; then
    echo "未找到 npm，请先安装 Node.js 18+ 与 npm。" >&2
    exit 1
fi
NPM_PATH="$(dirname "$NPM_BIN"):/usr/local/bin:/usr/bin:/bin"
runuser -u "$SERVICE_USER" -- \
    env HOME="$SERVICE_HOME" PATH="$NPM_PATH" \
    "$NPM_BIN" --prefix "$PROJECT_ROOT/frontend" run build

echo "[2/4] 安装 $SERVICE_NAME..."
TEMP_UNIT="$(mktemp)"
trap 'rm -f "$TEMP_UNIT"' EXIT
sed \
    -e "s|/home/hanxu/code/python/poker|$PROJECT_ROOT|g" \
    -e "s|^User=hanxu$|User=$SERVICE_USER|" \
    -e "s|^Group=Users$|Group=$SERVICE_GROUP|" \
    "$SERVICE_SOURCE" > "$TEMP_UNIT"
install -m 0644 "$TEMP_UNIT" "$SERVICE_TARGET"

echo "[3/4] 重新加载 systemd 并启用开机自启..."
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo "[4/4] 检查服务状态..."
systemctl is-enabled "$SERVICE_NAME"
systemctl is-active "$SERVICE_NAME"
systemctl --no-pager --full status "$SERVICE_NAME"

echo "部署完成：http://localhost:8000"
