"""Command-line entry point for HPoker."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Optional, Sequence

from cli.controller import PokerCliController

CLI_VERSION = "2.0.0"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse CLI options without touching the network or terminal."""

    parser = argparse.ArgumentParser(
        description="HPoker 德州扑克命令行客户端：大厅、实时牌桌与现金结算",
        epilog=(
            "登录后输入 help 查看命令；示例: poker_cli.py --user fwd "
            '--room ab12cd34 --mode stream'
        ),
    )
    parser.add_argument(
        "--server",
        "-s",
        default=os.environ.get("POKER_SERVER_URL", "http://127.0.0.1:8000"),
        help="后端服务地址（默认: http://127.0.0.1:8000，也可用 POKER_SERVER_URL）",
    )
    parser.add_argument(
        "--user",
        "-u",
        default=None,
        help="自动登录用户名；未提供时启动交互式登录",
    )
    parser.add_argument(
        "--password",
        "-p",
        default=None,
        help="自动登录密码（命令行会暴露在进程列表中，推荐留空后交互输入）",
    )
    parser.add_argument(
        "--room",
        "-r",
        default=None,
        help="登录后直接进入房间 ID（不传则进入大厅）",
    )
    parser.add_argument(
        "--mode",
        "-m",
        choices=("dashboard", "stream"),
        default=os.environ.get("POKER_CLI_MODE", "dashboard"),
        help="显示模式: dashboard（重绘牌桌）或 stream（事件流）",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="禁用 ANSI 颜色，适合日志重定向",
    )
    parser.add_argument(
        "--http-timeout",
        type=float,
        default=10.0,
        metavar="SECONDS",
        help="REST 请求超时秒数（默认: 10）",
    )
    parser.add_argument(
        "--reconnect-attempts",
        type=int,
        default=2,
        metavar="N",
        help="连接失败时自动重试次数（默认: 2，输入 reconnect 也使用此值）",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"HPoker CLI {CLI_VERSION}",
    )
    return parser.parse_args(argv)


async def main_async(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    controller = PokerCliController(
        server_url=args.server,
        username=args.user,
        password=args.password,
        mode=args.mode,
        enable_color=not args.no_color,
        http_timeout=max(0.1, args.http_timeout),
        reconnect_attempts=max(0, args.reconnect_attempts),
    )

    try:
        if not await controller.login_flow():
            print("未登录，程序退出。")
            return 1
        if args.room:
            await controller.enter_room(args.room)
        else:
            await controller.run_lobby_loop()
        return 0
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n已退出 HPoker CLI。")
        return 0
    finally:
        await controller.api.close()


def main(argv: Optional[Sequence[str]] = None) -> None:
    try:
        status = asyncio.run(main_async(argv))
    except KeyboardInterrupt:
        print("\n再见！")
        status = 0
    if status:
        sys.exit(status)


if __name__ == "__main__":
    main()
