"""Main Entry Point for HPoker CLI Client."""

from __future__ import annotations
import argparse
import asyncio
import sys
from cli.controller import PokerCliController


def parse_args():
    parser = argparse.ArgumentParser(
        description="HPoker 命令行客户端 (Texas Hold'em CLI Edition)"
    )
    parser.add_argument(
        "--server",
        "-s",
        type=str,
        default="http://127.0.0.1:8000",
        help="后端服务地址 (默认: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--user",
        "-u",
        type=str,
        default=None,
        help="指定自动登录用户名 (如: admin, fwd, hx, yy)",
    )
    parser.add_argument(
        "--password",
        "-p",
        type=str,
        default=None,
        help="登录密码",
    )
    parser.add_argument(
        "--mode",
        "-m",
        type=str,
        choices=["dashboard", "stream"],
        default="dashboard",
        help="界面模式: dashboard(仪表盘重绘) 或 stream(极简单行日志流)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="禁用终端 ANSI 颜色",
    )
    return parser.parse_args()


async def main_async():
    args = parse_args()

    controller = PokerCliController(
        server_url=args.server,
        username=args.user,
        password=args.password,
        mode=args.mode,
        enable_color=not args.no_color,
    )

    try:
        logged_in = await controller.login_flow()
        if not logged_in:
            print("未登录，程序退出。")
            return

        await controller.run_lobby_loop()
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n已退出 HPoker CLI。")
    finally:
        await controller.api.close()


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n再见！")
        sys.exit(0)


if __name__ == "__main__":
    main()
