# AI Agent 开发与协作工作规范 (AGENT.md)

本文件是针对 AI Agent（包括 Antigravity 及后续迭代代理）与人类开发者的**工作准则与自动化执行规范**。
每次介入本项目时，AI 必须严格遵守以下规范。

---

## 🎯 核心工作准则

> [!IMPORTANT]
> **虚拟环境强制使用**：本项目所有 Python 命令必须使用虚拟环境 `.venv`（`/home/hanxu/code/python/poker/.venv/bin/python`、`/home/hanxu/code/python/poker/.venv/bin/pytest` 等），禁止尝试使用系统原生全局 Python！

1. **虚拟环境隔离原则**：所有 Python 代码运行、依赖管理、测试执行必须在本地虚拟环境 `.venv` 中进行（命令前缀必须使用 `/home/hanxu/code/python/poker/.venv/bin/`）。
2. **Git 原子提交原则**：每完成一个小功能或修复，必须立即执行 Git 提交，清晰记录改动原因与范围。
3. **进度实时勾选原则**：以 [PROGRESS.md](file:///home/hanxu/code/python/poker/PROGRESS.md) 为唯一事实依据，每完成一个小功能，必须立即在对应项打勾 `[x]`。
4. **算法零容错原则**：德州扑克规则极为严密（尤其是 7选5 牌型大小、边池分配、全下池隔离、结算债务简化），核心算法必须附带高覆盖率单元测试。

---

## 🐍 1. Python 虚拟环境规范

- **虚拟环境位置**：项目根目录下的 `.venv` 目录 (`/home/hanxu/code/python/poker/.venv`)。
- **环境初始化**：
  ```bash
  python3 -m venv /home/hanxu/code/python/poker/.venv
  ```
- **命令执行规范**（AI 必须绝对遵循）：
  - 运行 Python 脚本或模块：`/home/hanxu/code/python/poker/.venv/bin/python <script.py>`
  - 安装依赖：`/home/hanxu/code/python/poker/.venv/bin/pip install -r backend/requirements.txt`
  - 运行测试：`/home/hanxu/code/python/poker/.venv/bin/pytest backend/tests/`
  - 启动服务：`/home/hanxu/code/python/poker/.venv/bin/uvicorn backend.main:app --reload`
- **禁止行为**：
  - ❌ 严禁尝试原生 Python 或直接运行 `python`、`pytest` 等全局命令，必须使用 `.venv` 路径。
  - ❌ 禁止在全局系统 Python 环境下直接 `pip install` 或运行项目。
  - ❌ 禁止将 `.venv` 目录提交至 Git 仓库。

---

## 📦 2. Git 提交与版本管理规范

- **提交频率**：微粒度提交。每当一个独立的类、函数、组件、测试或配置完成并通过验证后，立即提交。
- **提交信息格式**：遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：
  - `feat(<scope>): <description>` - 新功能（如 `feat(engine): add side pot calculator`）
  - `fix(<scope>): <description>` - 修复问题（如 `fix(evaluator): fix A-2-3-4-5 wheel straight tie break`）
  - `test(<scope>): <description>` - 添加或修复测试（如 `test(pot): add multi-way allin side pot tests`）
  - `docs(<scope>): <description>` - 文档修改或进度更新（如 `docs: update PROGRESS.md checklist`）
  - `refactor(<scope>): <description>` - 代码重构无功能变更
- **规范工作流**：
  1. 编写/修改代码与测试。
  2. 运行测试，确保通过。
  3. 修改 [PROGRESS.md](file:///home/hanxu/code/python/poker/PROGRESS.md) 标记对应功能为 `[x]`。
  4. 执行 `git add .` 与 `git commit -m "..."`。

---

## ✅ 3. 进度追踪与 PROGRESS.md 维护规范

- **任务颗粒度**：所有功能细分至具体小模块（如：洗牌模块、7选5比牌、主边池计算、下注轮次状态机、结算网络流算法等）。
- **打勾时机**：
  - 代码编写完成 + 单元测试通过 / 功能验证完成 后，方可将 `[ ]` 改为 `[x]`。
  - 若在开发中发现有新的子需求或技术点，应在 [PROGRESS.md](file:///home/hanxu/code/python/poker/PROGRESS.md) 对应章节中新增子项 `[ ]` 再推进。
- **状态同步**：每次回答用户时，简要汇报当前已打勾的任务及下一步即将执行的任务。

---

## 🃏 4. 德州扑克业务逻辑与算法强制要求

### 4.1 发牌与随机性
- 必须使用 Python `secrets` 模块提供的 CSPRNG 实现 Fisher-Yates 洗牌算法，禁止使用可预测的伪随机数种子。

### 4.2 7选5牌型评估与比牌器 (Hand Evaluator)
- 严格支持 10 种标准德州牌型判定：
  1. 皇家同花顺 (Royal Flush)
  2. 同花顺 (Straight Flush) - 注意 A-2-3-4-5 (Wheel) 的低顺判定
  3. 四条 (Four of a Kind) - 四张同点 + 1张最高踢脚牌 (Kicker)
  4. 葫芦 (Full House) - 三张同点 + 两张同点
  5. 同花 (Flush) - 5张同花色，从大到小比踢脚牌
  6. 顺子 (Straight) - 5张连续点数，A可作最高(TJQKA)或最低(A2345)
  7. 三条 (Three of a Kind) - 3张同点 + 2张最高踢脚牌
  8. 两对 (Two Pair) - 高对 + 低对 + 1张最高踢脚牌
  9. 一对 (One Pair) - 1对 + 3张最高踢脚牌
  10. 高牌 (High Card) - 5张最大单牌比对

### 4.3 边池计算与分配 (Side Pots Split Engine)
- 必须支持任意人数全下（All-in）、不同全下金额产生阶梯式边池的场景。
- 每个池子（主池 Main Pot、边池 1, 边池 2...）记录：
  - 该池的筹码总额。
  - 有资格竞争该池的活跃玩家集合（Eligible Players）。
- 结算时，从最高的边池向主池依次由有资格且手牌最大的玩家瓜分；若有多人平局（Tie），平分该池筹码（奇数筹码按标准顺位规则处理）。

### 4.4 现金局买入与战局结束结算算法 (Debt Settlement)
- 记录每个玩家的 `total_buyin`（初始买入 + 所有 Re-buy 补码）和当前筹码 `current_chips`。
- 净收益净额：`net_balance = (current_chips - total_buyin) * cash_ratio`。
- **最小现金转账算法**：
  - 汇总所有盈利者（债权人）与亏损者（债务人）。
  - 使用贪心算法 / 最小费用最大流模型，将原本可能的多对多转账压缩为最少笔数的点对点支付转账明细（如 "张三 付给 李四 ¥50"）。

---

## 🎨 5. 前端交互与 HPoker 体验规范

- **界面设计**：暗黑奢华风、金属光泽按钮、筹码拟真堆叠、动态发牌轨迹与收池动画。
- **操作快捷键与尺度**：
  - 1/3 Pot、1/2 Pot、2/3 Pot、Pot、1.5 Pot、2 Pot、3 Pot、All-in 快捷按钮（含实时筹码金额显示）。
  - 下注滑块支持 +1BB / -1BB 微调。
  - 支持键盘快捷键（Space: Check/Call, F: Fold, R: Raise, A: All-in）。
- **手牌展示（Showdown & Muck）**：
  - 局末未进入摊牌但获胜（其他人均弃牌）时，弹窗或浮动按钮提示是否亮出牌 1、牌 2 或全部展示。
- **音效系统**：
  - 使用 Web Audio API 无损合成或预加载音效（发牌、下注、弃牌、过牌、全下心跳、赢池筹码撞击声、倒计时嘀嗒声）。
- **全端适配**：
  - PC 端大屏沉浸式布局。
  - 手机端横竖屏自适应触控布局，按钮防误触优化。
