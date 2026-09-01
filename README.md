# GGPoker 风格多人在线德州扑克系统 (Texas Hold'em Online)

一款高度拟真、参考 **GGPoker** 视觉与交互体验的多人实时在线德州扑克（Texas Hold'em）现金局平台。后端采用 Python 异步架构（FastAPI + WebSocket），前端采用现代响应式前端框架，具备极高准确性的边池计算、精准的超时托管机制、重买记录、战局结束债权自动结算以及全套沉浸式音效。

---

## 🌟 核心特性

### 1. 德州扑克专业算法引擎
- **加密级洗牌算法**：采用 Python `secrets` / CSPRNG 保证发牌绝对随机与不可预测。
- **高精度 7 选 5 牌型评估器**：支持高牌、一对、两对、三条、顺子、同花、葫芦、四条、同花顺、皇家同花顺的快速准确比对。
- **全下（All-in）与多重边池（Side Pots）计算**：严格按照德州扑克国际规则，精确处理多人全下、不同下注额度产生的复杂主池与多个边池分配，杜绝任何算力漏洞。
- **下注合法性校验与尺度控制**：严格遵循最小加注增量规则（Min-Raise Rule），提供 1/3 Pot、1/2 Pot、2/3 Pot、3/4 Pot、Pot、All-In 等快捷尺度与滑块微调。

### 2. GGPoker 风格 UI / UX 与视觉沉浸
- **暗黑高端牌桌**：还原 GGPoker 经典的黑色/墨绿色奢华毛呢桌布与金属包边设计。
- **座位与玩家状态**：环形动态排布座位、庄家位（Dealer Button）、小盲（SB）、大盲（BB）、下注额、手牌及实时倒计时进度光圈。
- **手牌展示机制（Show / Muck）**：牌局结束后支持玩家自主选择亮出单张牌或全部牌（Show One / Show All），打到最后摊牌（Showdown）阶段自动比牌亮牌。
- **全套扑克音效系统**：内置发牌、Check、Call、Raise、Fold、All-in、赢取底池、倒计时提示音等全套音效。

### 3. 现金局（Cash Game）与经济结算系统
- **灵活房间参数配置**：房主创建房间时可配置买入筹码数（Buy-in Chips）、对应现金额度（Cash Value）、小盲/大盲注额（SB/BB）、思考超时时间（Timeout）。
- **重买（Re-buy）与补码追踪**：玩家筹码耗尽或不足时支持重新买入，牌桌上实时展示所有玩家的买入次数与累计买入额。
- **自动转账结算账单（债务最小化算法）**：房主点击结束房间时，系统根据所有玩家的初始买入、补码与最终剩余筹码，自动计算各玩家的净盈亏，并通过**最小现金转账算法（Debt Simplification Flow）**输出最精简的“谁向谁付多少钱”清单。

### 4. 账号与房间管理
- **免注册后台预置用户**：支持预设用户列表或管理员后台录入，保障局域网或私有局的安全便捷接入。
- **超时自动托管**：玩家在倒计时内未操作时，自动执行 Check（若无加注）或 Fold（若有下注）。
- **全端响应式适配**：完美适配 PC 桌面端（支持键盘快捷键）与手机端触摸屏操作。

---

## 🛠️ 技术架构

- **后端架构**：Python 3.11+ / FastAPI / WebSockets / Asyncio
- **核心算法**：纯 Python 实现的高性能 7-Card Evaluator、Side Pot Split Engine、Debt Optimizer
- **前端架构**：React 18 / Vue 3 + Vite + Tailwind CSS + Lucide Icons + Web Audio API
- **通信协议**：WebSocket 双向事件流（实时广播游戏状态、操作确认、动画同步与重连同步）

---

## 🚀 快速启动指南

### 1. 环境准备
确保本机已安装 Python 3.11+ 以及 Node.js 18+。

### 2. 创建并激活 Python 虚拟环境
本项目严格要求使用独立虚拟环境：

```bash
# 进入项目目录
cd /home/hanxu/code/python/poker

# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate
```

### 3. 安装后端依赖并运行
```bash
# 激活环境后安装依赖
pip install -r backend/requirements.txt

# 启动后端服务 (FastAPI + WebSocket)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 安装前端依赖并运行
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
