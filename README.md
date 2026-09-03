# HPoker 风格多人在线德州扑克系统 (Texas Hold'em Online)

一款高度拟真、参考 **HPoker** 视觉与交互体验的多人实时在线德州扑克（Texas Hold'em）现金局平台。后端采用 Python 异步架构（FastAPI + WebSocket），前端采用现代响应式前端框架，具备极高准确性的边池计算、精准的超时托管机制、重买记录、战局结束债权自动结算以及全套沉浸式音效。

---

## 🌟 核心特性

### 1. 德州扑克专业算法引擎
- **加密级洗牌算法**：采用 Python `secrets` / CSPRNG 保证发牌绝对随机与不可预测。
- **高精度 7 选 5 牌型评估器**：支持高牌、一对、两对、三条、顺子、同花、葫芦、四条、同花顺、皇家同花顺的快速准确比对。
- **全下（All-in）与多重边池（Side Pots）计算**：严格按照德州扑克国际规则，精确处理多人全下、不同下注额度产生的复杂主池与多个边池分配，杜绝任何算力漏洞。
- **下注合法性校验与尺度控制**：严格遵循最小加注增量规则（Min-Raise Rule），提供 1/3 Pot、1/2 Pot、2/3 Pot、Pot、1.5 Pot、2 Pot、3 Pot、All-In 等快捷尺度与实时计算金额直观显示，配合滑块微调。

### 2. HPoker 风格 UI / UX 与视觉沉浸
- **UI风格**：还原 HPoker 页面风格，按钮排布等。
- **座位与玩家状态**：环形动态排布座位、庄家位（Dealer Button）、小盲（SB）、大盲（BB）、下注额、手牌及实时倒计时进度光圈。
- **手牌展示机制（Show / Muck）**：牌局结束后支持玩家自主选择亮出单张牌或全部牌（Show One / Show All），打到最后摊牌（Showdown）阶段自动比牌亮牌。
- **全套扑克音效系统**：内置发牌、Check、Call、Raise、Fold、All-in、赢取底池、倒计时提示音等全套音效。

### 3. 现金局（Cash Game）与经济结算系统
- **灵活房间参数配置**：房主创建房间时可配置买入筹码数（默认 1000）、对应现金额度（默认 ¥100）、小盲注（默认 10）和思考超时时间（Timeout）；大盲注固定按小盲注的 2 倍自动计算。
- **重买（Re-buy）与补码追踪**：玩家筹码耗尽或不足时支持重新买入，牌桌上实时展示所有玩家的买入次数与累计买入额。
- **自动转账结算账单（债务最小化算法）**：房主点击结束房间时，系统根据所有玩家的初始买入、补码与最终剩余筹码，自动计算各玩家的净盈亏，并通过**最小现金转账算法（Debt Simplification Flow）**输出最精简的“谁向谁付多少钱”清单。

### 4. 账号与房间管理
- **免注册后台预置用户**：支持预设用户列表或管理员后台录入，保障局域网或私有局的安全便捷接入。
- **超时自动托管**：玩家在倒计时内未操作时，自动执行 Check（若无加注）或 Fold（若有下注）。
- **全端响应式适配**：完美适配 PC 桌面端（支持键盘快捷键）与手机端触摸屏操作。
- **小盲步进下注**：下注金额输入与滑块按小盲注的整数倍步进，避免出现非标准筹码档位。

---

## 🛠️ 技术架构

- **后端架构**：Python 3.11+ / FastAPI / WebSockets / Asyncio
- **核心算法**：纯 Python 实现的高性能 7-Card Evaluator、Side Pot Split Engine、Debt Optimizer
- **前端架构**：React 18 / Vue 3 + Vite + Tailwind CSS + Lucide Icons + Web Audio API
- **通信协议**：WebSocket 双向事件流（实时广播游戏状态、操作确认、动画同步与重连同步）

---

## 🚀 快速启动指南

### ⚡ 方式一：一键极速启动 (推荐)

项目内置了自动化启动脚本 `start.sh`，会自动检查并配置虚拟环境、安装缺失依赖、释放冲突端口并同时启动前后端服务：

```bash
# 进入项目目录直接运行
./start.sh
```

- 🌐 本地桌面访问：`http://localhost:5173`
- 📱 局域网/手机访问：`http://<局域网IP>:5173`（脚本启动时会自动显示对应 IP）
- 💻 **Textual TUI 终端客户端**：`./start.sh cli` 或 `.venv/bin/python poker_cli.py`
- 📖 后端 API 文档：`http://localhost:8000/docs`
- 🛑 按 `Ctrl + C` 即可一键安全停止所有服务。

> **脚本常用命令**：
> - `./start.sh` 或 `./start.sh dev`：前后端热重载开发模式（默认）
> - `./start.sh cli`：启动轻量 CLI 终端客户端（支持创建房间、打牌、加注、秀牌、结算）
> - `./start.sh prod`：编译前端并以单端口（8000）生产模式运行
> - `./start.sh backend`：仅启动后端服务
> - `./start.sh test`：运行全部单元测试
> - `./start.sh stop`：强制停止占用 8000 / 5173 端口的残留进程
> - `./start.sh help`：查看全部命令帮助

### 🔄 systemd 开机自启（生产环境）

仓库提供 `deploy/poker.service` 和自动安装脚本，由 systemd 直接托管虚拟环境中的 Uvicorn。执行：

```bash
cd /home/hanxu/code/python/poker
sudo ./deploy/install-systemd.sh
```

脚本会自动构建前端，按当前项目路径与项目所有者生成服务单元，然后安装、启动并设为开机自启。

常用管理命令：

```bash
systemctl status poker.service
journalctl -u poker.service -f
sudo systemctl restart poker.service
sudo systemctl disable --now poker.service
```

服务默认监听 `0.0.0.0:8000`，前端静态资源由 FastAPI 同端口提供；房间和用户持久化数据保存在 `backend/data/`。

---

### 💻 Textual TUI 终端客户端

CLI 支持大厅、实时牌桌、断线重连、单手结算页、终局结算页和两套视图模式（`dashboard` TUI / `stream` 事件流）。每手结束后会自动展示公共牌、玩家手牌、牌型、投入、返还、盈亏和余额，可输入 `q` 返回牌桌、用 `result` 再次查看；房间结束后则进入终局结算页，集中展示玩家收支、最简转账路线和导出入口。默认 `dashboard` 基于 Textual：宽屏时左侧展示牌桌、公共牌与手牌，右侧展示当前可执行操作、下注尺度和最近动态；窄终端自动切换为上下布局，并将手牌和公共牌收为低调的单行小牌，同时压缩顶栏、边框与次要提示。终端尺寸恢复后会自动切回完整牌面。底部输入框固定显示，`↑` / `↓` 可浏览命令历史。需要纯日志输出时使用 `stream`。CLI 启动不会检查前端 `node_modules`。

```bash
# 交互式登录并进入大厅
./start.sh cli

# 自动登录、直接进房间、使用事件流模式
./start.sh cli --user fwd --room ROOM_ID --mode stream

# 直接运行入口；密码建议留空后交互输入，避免出现在进程列表
.venv/bin/python poker_cli.py --user fwd --no-color
```

命令行参数：

- `--server URL`：后端地址，也可设置 `POKER_SERVER_URL`。
- `--user NAME`、`--password PASSWORD`：自动登录；不提供时交互登录。
- `--room ROOM_ID`：登录后直接进入指定房间。
- `--mode dashboard|stream`：选择 Textual TUI 或纯事件流，也可设置 `POKER_CLI_MODE`。
- `--no-color`：关闭 ANSI 颜色，适合日志重定向。
- `--http-timeout SECONDS`、`--reconnect-attempts N`：控制请求超时和自动重连次数。

大厅常用命令：

- `rooms` / `refresh`：刷新活跃房间；输入房间编号或 ID 直接加入。
- `create "房间名"`：交互创建房间；也支持 `create "现金桌" --buyin 2000 --cash 200 --sb 10 --timeout 20 --seats 6`。
- `users`：查看预置用户；`info ROOM_ID`：查看房间详情。
- `info`、`refresh`、`users`、`mode`、`color`、`help` 在大厅和牌桌中均可使用，并作用于当前上下文。
- `q` / `quit` / `exit`：关闭当前详情页；在牌桌中返回大厅。大厅首页不会因这些命令退出，退出程序请按 `Ctrl+C`。

命令别名由大厅与牌桌共用的命令注册表维护，但会按场景解析：大厅中 `c` / `r` 表示创建 / 刷新，牌桌中则表示过牌或跟注 / 加注。右侧操作栏和 `help` 均从同一注册表生成。

牌桌常用命令：

- `check` / `call` / `fold` / `allin`：过牌、跟注、弃牌、全下；快捷键为 `c`、`f`、`a`。
- `bet <额度>` / `raise <额度>`：下注或加注；界面优先提示 `raise 200` 这样的明确筹码额，快捷键为 `r`。
- 底池比例可紧凑输入：`r0.5` 表示半池、`r1` 表示整池；也兼容 `r 1/2p`、`r 2/3p`、`r 1.5p` 和 `r pot`。
- 额度还支持 `min`、`max`、`10bb`、`20sb`；系统会自动按小盲步长对齐并限制在合法范围。
- `ready`、`start`、`sit 2`、`rebuy`：准备、开局、入座和补码。
- `show 1` / `show 2` / `show all` / `muck`：摊牌时秀牌或盖牌；`rit 1` / `rit 2`：Run It Twice 投票。
- `reconnect`：手动重连；`status`、`history`、`redraw`：查看状态、行动记录或重绘。`r` 专用于下注，不再作为重绘别名。
- `bill` / `export settlement.txt`：查看或导出结算报表；房主使用 `end` 结束房间，`delete` 删除已结束房间。
- `leave` / `lobby`：返回大厅；`q` / `quit` / `exit` 返回当前页面的上一层（结算页返回牌桌，牌桌返回大厅）。退出程序请按 `Ctrl+C`。

---

### 🛠️ 方式二：手动分步启动

#### 1. 环境准备
确保本机已安装 Python 3.11+ 以及 Node.js 18+。

#### 2. 创建并激活 Python 虚拟环境
```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### 3. 安装后端依赖并运行
```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 4. 安装前端依赖并运行
```bash
cd frontend
npm install
npm run dev
```

打开浏览器访问 `http://localhost:5173` 即可进入游戏大厅与牌桌。

---

## 📁 目录结构规划

```text
poker/
├── .venv/                      # Python 虚拟环境 (git ignored)
├── backend/                    # 后端核心工程
│   ├── app/
│   │   ├── engine/             # 德州扑克核心算法与状态机
│   │   │   ├── card.py         # 扑克牌与花色点数定义
│   │   │   ├── deck.py         # CSPRNG 加密级洗牌与发牌
│   │   │   ├── evaluator.py    # 7选5牌型评估与比牌器
│   │   │   ├── pot.py          # 边池计算与分配引擎
│   │   │   └── state_machine.py# 牌局流程状态机 (Preflop->Flop->Turn->River->Showdown)
│   │   ├── models/             # 数据模型 (User, Room, Player, Action, Settlement)
│   │   ├── services/           # 业务服务 (RoomManager, SettlementService, UserManager)
│   │   ├── websocket/          # WebSocket 路由、连接管理器与事件分发
│   │   └── api/                # REST API (房间管理、用户列表、结算查询)
│   ├── tests/                  # 单元测试与边池算法压测
│   ├── main.py                 # FastAPI 入口
│   └── requirements.txt        # 后端 Python 依赖清单
├── frontend/                   # 前端工程
│   ├── src/
│   │   ├── components/         # 牌桌、玩家、手牌、公共牌、下注控件、结算面板
│   │   ├── hooks/              # WebSocket 通信 Hook、音效 Hook、倒计时 Hook
│   │   ├── sound/              # Web Audio API 音效生成与音效库
│   │   └── utils/              # 筹码计算、格式化、自适应辅助
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── README.md                   # 项目整体说明文档
├── AGENT.md                    # AI Agent 规范与工作守则 (环境、Git、进度维护)
└── PROGRESS.md                 # 详细功能分解与完成度进度表 (打勾追踪)
```

---

## 📖 协作与开发规范

详细的 AI 协作规范、虚拟环境管理机制、Git 提交工作流与进度勾选规则，请参阅：
- [AGENT.md](file:///home/hanxu/code/python/poker/AGENT.md)
- [PROGRESS.md](file:///home/hanxu/code/python/poker/PROGRESS.md)
