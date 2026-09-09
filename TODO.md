结论：**目前不宜把这个项目视为可可靠承载真实资金记账的现金局系统。** 已确认的问题包括身份冒用、错误下注状态转换、资金凭空入账、退款漏记，以及结算与持久化不一致。这些不是单纯的代码风格问题。

按你最新要求，现在收敛并交付审查结果。先说明边界：后端业务代码、WebSocket、React 主要组件、CLI、部署脚本及后端测试已审阅；**尚未完成所有 CSS、全部前端测试的逐行审阅，也没有完成真实浏览器、多进程和故障注入测试**。因此不能声称已经达到最初要求的“所有自有代码 100% 审查完成”。下文区分已复现、静态确认和待验证风险。

仓库未修改，未更新 PROGRESS、未提交代码。

## 1. 验证结果

审查基准：`dbc4a3e`。

| 检查 | 结果 |
|---|---|
| 后端测试 | 200 passed，15.48 秒 |
| 前端测试 | 15 个测试文件通过 |
| 前端生产构建 | 通过；输出至 `/tmp`，未覆盖项目产物 |
| Python 语法检查 | 66 个文件 AST 解析通过 |
| Python 依赖检查 | `pip check` 通过 |
| Shell 语法检查 | `start.sh`、systemd 安装脚本通过 |
| Git 状态 | 无代码改动 |

没有配置完整的 lint、类型检查和浏览器端集成测试。上述结果**不代表业务正确性通过**：部分测试本身固化了错误规则。

以下高风险问题已在隔离环境确认：

| 复现 | 实际结果 |
|---|---|
| 无令牌，仅传管理员 ID | 管理员用户列表返回 200 |
| 无令牌，仅传房主 ID | 删除房间返回 200 |
| 无令牌，仅传目标用户 ID | 修改资料返回 200 |
| 匿名以机器人 ID 连接 | 收到机器人的两张私牌 |
| 最高下注 20，加注到 40 | 下家最小再加注被要求为 80，而非 60 |
| 面对 100，短码以 Raise 全下到 50 | 桌面最高下注被降为 50 |
| 四人局，非当前玩家离桌 | 当前行动座位从 3 跳到 0 |
| 单挑 BB 盲注全下 | SB 尚未补齐，直接进入 RIT |
| 测试账号局中加入后，再加入真人 | 真人无买入扣款，离桌却获得兑回款 |
| 已离桌玩家有本手投入，房主中止本手 | 报表显示平衡，钱包合计仍少退款 |
| immediate 结束房间 | 盈亏仍保留为待结余额 |
| 清除已批结的测试记录 | 外键异常；内存与数据库状态不同 |

## 2. 架构与关键数据流

### 实际架构

```text
React / CLI
  ├─ REST：登录、用户管理、房间管理、余额、历史、胜率计算
  └─ WebSocket：行动、准备、亮牌、RIT、聊天、状态广播
                  │
        endpoints.py / router.py
                  │
       全局单例服务 + 内存对象
       ├─ UserManager：用户、永久 token
       ├─ RoomManager → Room → TableStateMachine
       │                         ├─ Deck / Evaluator
       │                         └─ PotManager
       ├─ TimeoutManager：行动、机器人、离线、清理任务
       ├─ BalanceManager：买入、兑回、批量结算
       └─ HandHistoryManager
                  │
              SQLite
```

这是一个**以内存为运行时事实来源、SQLite 保存检查点和账本**的单进程系统，而不是以数据库事务驱动的游戏服务。

### 四条关键数据流

1. **入座与买入**
   连接或入座请求 → 创建座位 → 更新历史参与者 → 写钱包扣款 → 广播时保存房间。
   座位、钱包、房间检查点不在同一事务中。

2. **下注与结算**
   WebSocket 行动 → 修改筹码和底池 → 状态机推进 → 比牌分池 → 发音效 → 保存历史与检查点 → 广播。
   网络等待与业务变更交织，缺少房间级串行化。

3. **离桌与现金结算**
   弃牌／移除座位 → 更新历史筹码 → 兑回钱包 → 后续批量结算。
   同时还保留旧的“整桌盈亏生成转账报表”路径，两套结算语义没有完全统一。

4. **断线与恢复**
   断线 → 宽限期任务 → 自动离桌或标记延期离桌。
   重启不恢复进行中的牌局，而是将检查点中的本手投入退回并恢复为 IDLE；这是设计策略，但其资金对账实现有漏洞。

## 3. 按严重程度排序的问题清单

标记含义：

- **复现**：隔离运行已确认。
- **静态确认**：代码路径清楚，尚未做完整运行复现。
- **待验证**：需要并发、浏览器或部署环境进一步确认。

### P0：应立即处理

**01｜管理员鉴权可绕过【复现】**
位置：[endpoints.py:66](/home/hanxu/code/python/poker/backend/app/api/endpoints.py:66)。
原因／触发：令牌缺失或无效时，仍接受调用者传入的 `admin_id`，只检查该 ID 是否属于管理员。
影响：可冒用管理员执行创建／修改／删除用户、批量结算、清空账本等操作。
建议：管理员身份只从有效认证上下文取得，删除所有 ID 鉴权回退。

**02｜房间管理接口可以冒用房主或其他玩家【复现】**
位置：[endpoints.py:275](/home/hanxu/code/python/poker/backend/app/api/endpoints.py:275)、[endpoints.py:341](/home/hanxu/code/python/poker/backend/app/api/endpoints.py:341)、[endpoints.py:404](/home/hanxu/code/python/poker/backend/app/api/endpoints.py:404)、[endpoints.py:421](/home/hanxu/code/python/poker/backend/app/api/endpoints.py:421)。
原因／触发：创建房间信任 `host_player_id`；离桌、踢人、结束、删除等操作信任 `requester_id`。
影响：未经登录即可破坏牌局、强制他人离桌或触发资金兑回。
建议：统一认证依赖，服务器绑定操作者身份，再执行房间权限检查。

**03｜仓库包含认证材料及历史账务数据【静态确认；有效性待验证】**
位置：[users.json](/home/hanxu/code/python/poker/backend/data/users.json)、[balance_ledger.json](/home/hanxu/code/python/poker/backend/data/balance_ledger.json)。
证据：被 Git 跟踪的用户文件含 7 个用户、5 个 token；账本含历史条目。默认生产迁移会读取这些文件。
影响：仓库访问者可能获取凭据；新部署可能导入历史身份、令牌和账务。当前令牌是否仍有效未访问生产验证。
建议：按已暴露凭据处理并轮换；移除真实种子数据，检查 Git 历史，改用脱敏模板。

### P1：规则、资金与身份安全

**04｜局中入座可获得未扣款筹码【复现】**
位置：[room.py:483](/home/hanxu/code/python/poker/backend/app/models/room.py:483)、[room.py:515](/home/hanxu/code/python/poker/backend/app/models/room.py:515)。
原因／触发：真人现金局进行中，测试账号先加入，随后真人加入；`money_mode` 仍为 real，但买入条件因存在测试玩家而跳过扣款。
影响：后加入真人离桌时仍按 real 兑回。已复现无买入记录却获得 ¥10。
建议：以明确的资金模式决定每笔买入，局中新增座位的资金属性不可由未生效模式切换影响。

**05｜结束房间漏退已离桌玩家的本手投入【复现】**
位置：[room.py:867](/home/hanxu/code/python/poker/backend/app/models/room.py:867)。
原因／触发：玩家投入后离桌，本手尚未结束时房主结束房间；退款只加到历史 `cashed_out_chips`，没有相应钱包流水。
影响：报表 `is_balanced=True`，实际钱包仍缺钱；已复现差额 ¥0.50。
建议：统一中止退款与兑回流程，对离桌参与者也写入幂等退款流水。

**06｜重启恢复存在同类离桌退款漏记【静态确认】**
位置：[room.py:214](/home/hanxu/code/python/poker/backend/app/models/room.py:214)、[room.py:287](/home/hanxu/code/python/poker/backend/app/models/room.py:287)。
原因／触发：进行中检查点将离桌者投入退到历史值，恢复后牌局已变 IDLE，但未完成钱包退款。
影响：重启后差额被固化，原始待退款上下文消失。
建议：恢复作为显式事务处理，保存中止事件和待对账状态，而不是仅改序列化值。

**07｜immediate 结算实际上没有结清钱包【复现】**
位置：[room.py:867](/home/hanxu/code/python/poker/backend/app/models/room.py:867)、[balance_manager.py:186](/home/hanxu/code/python/poker/backend/app/services/balance_manager.py:186)。
原因／触发：选择 immediate 只改变报表标记，兑回流水仍为 `balance/unsettled`。
影响：按即时账单线下付款后，同一盈亏还能进入后续批量结算。
建议：定义唯一结算生命周期；即时支付必须对应已结清条目或冲销记录。

**08｜座位与钱包没有跨模块原子性【静态确认】**
位置：[room.py:515](/home/hanxu/code/python/poker/backend/app/models/room.py:515)、[room.py:723](/home/hanxu/code/python/poker/backend/app/models/room.py:723)、[room_manager.py:87](/home/hanxu/code/python/poker/backend/app/services/room_manager.py:87)。
原因／触发：内存座位、历史参与者、钱包和房间快照分步修改；任一步失败或进程退出。
影响：可能重复兑回、扣款无座位、座位无扣款；单条流水幂等不能保证整个业务操作幂等。
建议：引入事务化应用服务，将座位资金变更和持久化关联为一次提交。

**09｜写库失败不会回滚内存【复现其一】**
位置：[balance_manager.py:253](/home/hanxu/code/python/poker/backend/app/services/balance_manager.py:253)、[balance_manager.py:399](/home/hanxu/code/python/poker/backend/app/services/balance_manager.py:399)、[user_manager.py:138](/home/hanxu/code/python/poker/backend/app/services/user_manager.py:138)。
原因／触发：先修改缓存，再保存；异常仅回滚 SQLite。
影响：请求失败后运行时仍使用修改后的状态，后续操作可能将其再次写回。清理测试记录已复现此问题。
建议：先构造新状态、事务提交成功后替换缓存，或实现明确的内存回滚。

**10｜匿名连接可以冒用机器人身份并读取私牌【复现】**
位置：[router.py:442](/home/hanxu/code/python/poker/backend/app/websocket/router.py:442)、[connection_manager.py:128](/home/hanxu/code/python/poker/backend/app/websocket/connection_manager.py:128)。
原因／触发：只有“用户表存在该 ID”才验证令牌；机器人不在用户表，之后按该 ID 序列化私牌、处理行动。
影响：机器人私牌泄露，且具备代其行动的代码路径；删除账号后的残留座位也存在类似风险。
建议：匿名观察者使用服务器生成且与玩家隔离的身份；所有玩家命令要求认证主体与座位一致。

**11｜最小再加注规则错误【复现】**
位置：[state_machine.py:581](/home/hanxu/code/python/poker/backend/app/engine/state_machine.py:581)、[state_machine.py:667](/home/hanxu/code/python/poker/backend/app/engine/state_machine.py:667)。
原因／触发：使用 `highest_bet * 2`，没有使用上一笔完整加注的增量。
影响：20→40 后，合法的再加注到 60 被拒绝，要求至少 80。
建议：正确维护完整加注增量，并由合法动作与执行器共用同一规则。

**12｜短码 Raise 全下会降低最高下注【复现】**
位置：[state_machine.py:667](/home/hanxu/code/python/poker/backend/app/engine/state_machine.py:667)。
原因／触发：全下绕过最低金额校验，然后无条件将最高下注赋为 `target_bet`。
影响：100 被降为 50，已跟注玩家出现负的待跟金额，Check/Call 均不可用。CLI 的 Raise-allin 路径可触及。
建议：统一 CALL／短码 ALL_IN 归类；最高下注只能非递减。

**13｜不足额全下错误重新开放加注权【静态确认】**
位置：[state_machine.py:738](/home/hanxu/code/python/poker/backend/app/engine/state_machine.py:738)。
原因／触发：全下金额只要高于当前下注，就重置其他玩家行动状态。
影响：此前已行动的玩家可能在不足额加注后再次加注。
建议：分别记录“还需响应”和“有权加注”，覆盖累计不足额加注情形。

上述加注规则及奇数筹码规则参照 [Poker TDA 官方规则](https://www.pokertda.com/view-poker-tda-rules/)；现金局特殊房规应另行明确，不能一边宣称标准无限注规则，一边隐式替换。

**14｜盲注全下过早进入 RIT【复现】**
位置：[state_machine.py:491](/home/hanxu/code/python/poker/backend/app/engine/state_machine.py:491)、[state_machine.py:844](/home/hanxu/code/python/poker/backend/app/engine/state_machine.py:844)。
原因／触发：仅依据还能行动的人数判断 runout，没有检查其是否仍欠跟注。
影响：单挑 BB 投入 20 全下、SB 只投 10 时，SB 的 Call/Fold 权利被跳过，私牌直接公开。
建议：进入 runout 前必须确认没有未完成的下注决定。

**15｜非当前行动者离桌会跳过当前玩家【复现】**
位置：[state_machine.py:320](/home/hanxu/code/python/poker/backend/app/engine/state_machine.py:320)、[state_machine.py:776](/home/hanxu/code/python/poker/backend/app/engine/state_machine.py:776)。
原因／触发：离桌弃牌调用通用轮次完成检查，后者无条件推进当前行动座位。
影响：第三方离桌改变其他玩家的行动顺序。
建议：将“检查是否结束”与“消费当前回合并推进”分开。

**16｜边池的单一资格者被错误视为未跟注退款【复现】**
位置：[pot.py:184](/home/hanxu/code/python/poker/backend/app/engine/pot.py:184)。
原因／触发：以剩余 eligible 人数而非该层贡献者人数判断退款。
影响：包含弃牌者投入的争夺池被标为退款，破坏边池展示和辅助折让；更高无资格层还可能错误并入主池。
证据：A100、B200、C300 且 C 弃牌，得到 A/B 可争夺 400 的主池，超过 A 的资格上限 300。
建议：贡献分层与获胜资格独立计算；只有真正未被任何人匹配的投入才退款。

**17｜RIT 无人投票时可以永久卡桌【静态确认】**
位置：[router.py:79](/home/hanxu/code/python/poker/backend/app/websocket/router.py:79)、[test_allin_and_rit.py:84](/home/hanxu/code/python/poker/backend/tests/test_allin_and_rit.py:84)。
原因／触发：要求全部参与者投票，明确禁用超时；全下玩家又不能被移除。
影响：断线或拒绝投票即可冻结牌局，其他玩家不能正常完成结算。
建议：定义断线与投票超时策略，通常默认发一次；这是需产品确认的规则，但当前可用性缺陷明确。

**18｜正常 RIT 发牌结束未处理延期离桌【静态确认】**
位置：[router.py:43](/home/hanxu/code/python/poker/backend/app/websocket/router.py:43)。
原因／触发：慢发牌完成后直接摊牌、广播，没有调用统一的手后处理。
影响：全下断线玩家的延期离桌／兑回可能长期不执行。
建议：所有结束手牌的路径进入同一终结流程。

**19｜离线自动离桌后没有重新调度行动流程【静态确认】**
位置：[router.py:362](/home/hanxu/code/python/poker/backend/app/websocket/router.py:362)。
原因／触发：超时离桌改变行动者或街道，但只保存、广播、检查空房。
影响：旧计时器按旧座位退出，新行动者没有计时器，或进入 RIT 后未启动后续处理。
建议：复用完整的行动后调度，并以 hand/turn 标识验证定时任务。

**20｜开始新手误取消离线清理与补卡任务【静态确认】**
位置：[router.py:631](/home/hanxu/code/python/poker/backend/app/websocket/router.py:631)、[router.py:757](/home/hanxu/code/python/poker/backend/app/websocket/router.py:757)。
原因／触发：开局调用 `cancel_all_timers`，涵盖房间生命周期任务。
影响：离线玩家不再按宽限期离桌；周期补卡任务也可能停止。
建议：分离手牌级和房间级任务，开局仅取消前一手任务。

**21｜REST 与 WebSocket 同房间操作没有统一串行化【待验证具体交错】**
位置：[router.py](/home/hanxu/code/python/poker/backend/app/websocket/router.py)、[endpoints.py:404](/home/hanxu/code/python/poker/backend/app/api/endpoints.py:404)。
原因／触发：多个 WS 任务跨 `await` 修改同一对象；同步 REST 结束接口还在线程池修改对象、取消异步任务。
影响：结束、行动、机器人计算、兑回之间可能交错；SQLite 的锁不保护这段业务状态。
建议：每房间命令队列或统一锁；所有入口进入同一应用服务。

**22｜多实例／多 worker 会产生多个事实来源【静态确认】**
位置：[room_manager.py](/home/hanxu/code/python/poker/backend/app/services/room_manager.py)、[balance_manager.py:99](/home/hanxu/code/python/poker/backend/app/services/balance_manager.py:99)、[database.py:507](/home/hanxu/code/python/poker/backend/app/database.py:507)。
原因／触发：每个进程维护独立缓存，保存采用全表替换。
影响：扩容或误启两个服务时，状态分裂、后写覆盖新账目。当前 systemd 单 worker 不直接触发。
建议：明确并强制单实例限制；长期采用单房间所有权、增量数据库写入和版本控制。

**23｜默认密码、永久令牌与密码变更不失效【静态确认】**
位置：[user_manager.py:18](/home/hanxu/code/python/poker/backend/app/services/user_manager.py:18)、[user_manager.py:145](/home/hanxu/code/python/poker/backend/app/services/user_manager.py:145)。
原因／触发：生产默认 admin/admin、普通账号 123；登录复用永久 token，密码变更不撤销会话。
影响：初始部署可直接被登录；密码更换无法赶走已持有 token 的人。
建议：一次性安全初始化、强制改密、会话期限和撤销机制。

**24｜预置账号维护会恢复或覆盖管理员修改【静态确认】**
位置：[user_manager.py:86](/home/hanxu/code/python/poker/backend/app/services/user_manager.py:86)。
原因／触发：每次启动按用户名补建固定 ID 预置账号，并重置角色；给预置账号改名后重启会再次写同一 ID。
影响：改名后的资料／密码可能被默认账号覆盖，删除账号复活，角色变更失效。
建议：种子初始化只运行一次，以迁移记录标识，启动不能重写正常业务数据。

**25｜清理已结算测试账目会破坏内存一致性【复现】**
位置：[balance_manager.py:487](/home/hanxu/code/python/poker/backend/app/services/balance_manager.py:487)。
原因／触发：删除 entry，但 batch 仍引用它，保存时外键失败。
影响：数据库保留原记录，内存已删除；后续保存继续异常。
建议：事务化处理批次关联，历史已结算账务优先使用作废／归档。

**26｜进行中清空账本会毁掉资金基线【静态确认】**
位置：[balance_manager.py:500](/home/hanxu/code/python/poker/backend/app/services/balance_manager.py:500)。
原因／触发：桌上仍有筹码时允许清除全部买入与批次。
影响：后续兑回只有正向流水，资金无法对账。
建议：禁止有在桌敞口时清空；管理重置应有明确基准账和审计。

**27｜公开余额接口泄露他人财务信息【静态确认】**
位置：[endpoints.py:488](/home/hanxu/code/python/poker/backend/app/api/endpoints.py:488)。
原因／触发：overview、records、batches 无认证，my 接受任意 user_id。
影响：未登录者可查询个人盈亏、流水和付款关系。
建议：个人数据绑定当前用户，跨用户汇总限管理员或明确授权。

**28｜资料修改接口存在 IDOR【复现】**
位置：[endpoints.py:118](/home/hanxu/code/python/poker/backend/app/api/endpoints.py:118)。
原因／触发：认证失败时回退到请求中的 `user_id`。
影响：他人昵称、头像可被未登录者修改；更改密码另有旧密码检查，不等同任意改密。
建议：删除回退，区分本人资料接口和管理员修改接口。

### P2：功能、可靠性、性能和维护风险

**29｜现金金额舍入无法保证守恒【静态确认】**
位置：[balance_manager.py:186](/home/hanxu/code/python/poker/backend/app/services/balance_manager.py:186)、[settlement.py:94](/home/hanxu/code/python/poker/backend/app/services/settlement.py:94)。
触发／影响：任意筹码兑现金比例下逐笔四舍五入。例如 300 筹码=¥1，三人最终 400/400/100，兑回合计 ¥2.99，买入为 ¥3，批结可能因一分钱无法平衡。
建议：使用明确的整数最小货币单位和尾差分配规则。

**30｜贪心算法不保证最少转账笔数【静态确认】**
位置：[settlement.py:94](/home/hanxu/code/python/poker/backend/app/services/settlement.py:94)。
触发／影响：债权 8、7、5，债务 12、8；当前排序贪心产生 4 笔，实际 12→7+5、8→8 只需 3 笔。
建议：改称“简化转账”，或为小规模玩家实现严格最优搜索；最小费用流也不能未经建模就保证最少笔数。

**31｜游戏币阶段与整桌现金报表混算【静态确认】**
位置：[room.py:620](/home/hanxu/code/python/poker/backend/app/models/room.py:620)、[room.py:867](/home/hanxu/code/python/poker/backend/app/models/room.py:867)。
触发／影响：房间经历 real/play 切换后，报表仍按累计买入／最终筹码和现金比例计算，可能展示与钱包无关的游戏币盈亏、机器人转账。
建议：按资金会话分段；现金报告从真实资金流水生成。

**32｜测试身份判定在多处不一致【静态确认】**
位置：[user.py:35](/home/hanxu/code/python/poker/backend/app/models/user.py:35)、[room.py:431](/home/hanxu/code/python/poker/backend/app/models/room.py:431)、[balance_manager.py:219](/home/hanxu/code/python/poker/backend/app/services/balance_manager.py:219)。
触发／影响：`is_test`、用户名 test 前缀、bot 前缀、历史标记共同决定身份；管理员修改标记不一定同步已入座对象和历史分类。
建议：用不可歧义的账号类型和入座时固定的资金属性。

**33｜零筹码／坐出玩家保留上一手私牌与统计标记【静态确认】**
位置：[state_machine.py:460](/home/hanxu/code/python/poker/backend/app/engine/state_machine.py:460)、[state_machine.py:304](/home/hanxu/code/python/poker/backend/app/engine/state_machine.py:304)。
触发／影响：上一手参与、下一手不符合发牌资格时，只设 folded；旧牌、亮牌、VPIP 标记保留，按“有手牌”计数会虚增参局和奖励。
建议：所有座位清理上一手状态，再给合格参与者发牌；统计使用显式本手参与者集合。

**34｜单挑 RIT 奇数筹码顺位错误【静态确认】**
位置：[state_machine.py:970](/home/hanxu/code/python/poker/backend/app/engine/state_machine.py:970)。
触发／影响：从 SB 开始分配奇数筹码；单挑 SB 是按钮，而标准公共牌游戏应从按钮左侧起。RIT 分板可以形成奇数池。
建议：使用按钮后的座位顺序，而不是复用 SB 顺序。

**35｜辅助折让依赖客户端自行申报【静态确认】**
位置：[router.py:777](/home/hanxu/code/python/poker/backend/app/websocket/router.py:777)、[state_machine.py:1269](/home/hanxu/code/python/poker/backend/app/engine/state_machine.py:1269)、[endpoints.py:625](/home/hanxu/code/python/poker/backend/app/api/endpoints.py:625)。
触发／影响：直接调用胜率接口无需标记，标记还可以传 false 撤销；内置辅助的折让约束可绕过。
建议：内置计算绑定玩家和手牌，使用记录本手单向置位。外部辅助无法可靠检测，应明确边界。

**36｜多人平局胜率被当成平分一半【静态确认】**
位置：[equity.py:451](/home/hanxu/code/python/poker/backend/app/engine/equity.py:451)。
触发／影响：统一 `win_rate + tie_rate * 0.5`，三人及以上平局会高估期望权益，影响建议和机器人决策。
建议：模拟时累积实际 `1 / 获胜人数` 权益。

**37｜胜率建议忽略可争夺边池和有效跟注金额【静态确认】**
位置：[EquityDrawer.jsx:161](/home/hanxu/code/python/poker/frontend/src/components/EquityDrawer.jsx:161)、[PokerTable.jsx](/home/hanxu/code/python/poker/frontend/src/components/PokerTable.jsx)。
触发／影响：直接使用总底池和最高下注差额；短码玩家不能赢所有边池，也不一定需要跟满差额。
建议：服务器计算玩家专属可争夺池、有效 call 和对应 EV。

**38｜胜率接口输入与资源边界不足【静态确认】**
位置：[endpoints.py:615](/home/hanxu/code/python/poker/backend/app/api/endpoints.py:615)、[equity.py:401](/home/hanxu/code/python/poker/backend/app/engine/equity.py:401)。
触发／影响：重复牌、非法公共牌数量缺少完整验证；未认证、无限流 CPU 计算可占满线程池并拖慢服务。
建议：请求层限制牌数及唯一性，认证、限流、并发额度和短期缓存。

**39｜房间及身份字段缺少有效上限【静态确认】**
位置：[endpoints.py:229](/home/hanxu/code/python/poker/backend/app/api/endpoints.py:229)、[user_manager.py:237](/home/hanxu/code/python/poker/backend/app/services/user_manager.py:237)。
触发／影响：筹码、金额、文本等主要有下限但缺上限／有限数约束，可导致 SQLite 整数溢出、序列化失败或巨量文本广播。
建议：端到端定义有界整数、有限金额和文本长度，拒绝而不是失败后残留状态。

**40｜WS 合法 JSON 的非法结构会导致断线【静态确认】**
位置：[router.py:515](/home/hanxu/code/python/poker/backend/app/websocket/router.py:515)、[router.py:660](/home/hanxu/code/python/poker/backend/app/websocket/router.py:660)。
触发／影响：传 `[]`、`null`、错误 payload 类型，或金额转换溢出；只保护 JSON 解析，后续 `.get`、比较和转换可异常。
建议：按事件定义验证模型，每条命令独立捕获预期错误，返回稳定错误码。

**41｜慢连接拖住广播与业务推进【静态确认】**
位置：[connection_manager.py:128](/home/hanxu/code/python/poker/backend/app/websocket/connection_manager.py:128)。
触发／影响：逐 socket 顺序 await，无发送超时或有界队列；音效广播经常位于持久化和调度之前。
建议：业务提交与广播解耦，每连接有界发送队列，超时剔除慢连接。

**42｜历史、检查点和广播互相耦合【静态确认】**
位置：[room_manager.py:87](/home/hanxu/code/python/poker/backend/app/services/room_manager.py:87)、[connection_manager.py:128](/home/hanxu/code/python/poker/backend/app/websocket/connection_manager.py:128)。
触发／影响：广播负责落库，历史写入和房间保存又是两个事务；历史记录在内存先标记完成，失败后可能无法正常重试。
建议：显式业务提交；历史与关键结算结果一起提交，广播只读取提交后的快照。

**43｜全量快照重写造成随历史增长的性能退化【静态确认】**
位置：[database.py:340](/home/hanxu/code/python/poker/backend/app/database.py:340)、[database.py:386](/home/hanxu/code/python/poker/backend/app/database.py:386)、[database.py:507](/home/hanxu/code/python/poker/backend/app/database.py:507)。
触发／影响：一次买入重写全部账目与批次，一次广播保存全部房间；房间还携带持续增长的历史。
建议：增量 append/update，避免历史账本参与每次操作的全量序列化。

**44｜手牌历史分页仍加载最多十万条详情【静态确认】**
位置：[hand_history_manager.py:18](/home/hanxu/code/python/poker/backend/app/services/hand_history_manager.py:18)。
触发／影响：每页另查十万条用于总数、汇总和最大盈亏；CPU、内存和响应时间增长，超过十万条后统计错误。
建议：数据库执行 COUNT/SUM/MAX，详情只取当前页，并提供稳定次排序键。

**45｜浏览器倒计时与服务端不一致【静态确认】**
位置：[PlayerSeat.jsx:50](/home/hanxu/code/python/poker/frontend/src/components/PlayerSeat.jsx:50)、[ActionBar.jsx:272](/home/hanxu/code/python/poker/frontend/src/components/ActionBar.jsx:272)、[PokerTable.jsx:396](/home/hanxu/code/python/poker/frontend/src/components/PokerTable.jsx:396)。
触发／影响：重新挂载或重连时从本地当前时间开始，而不是使用服务端 `turn_started_at`；界面还有时间但服务器已行动。CLI 已使用服务器时间。
建议：统一基于服务端 deadline 渲染，并考虑时钟偏移。

**46｜断线仍可操作，命令可能静默丢失【静态确认】**
位置：[App.jsx:387](/home/hanxu/code/python/poker/frontend/src/App.jsx:387)、[PokerTable.jsx:200](/home/hanxu/code/python/poker/frontend/src/components/PokerTable.jsx:200)。
触发／影响：保留旧牌桌状态且未把连接状态传入操作区；发送失败没有命令确认，离桌／揭牌的等待标记可能不恢复。
建议：禁用未同步状态下的动作，加入 command ID、确认及失败恢复。

**47｜旧连接回调和身份失效重连处理不足【待验证浏览器交错】**
位置：[App.jsx:296](/home/hanxu/code/python/poker/frontend/src/App.jsx:296)、[App.jsx:415](/home/hanxu/code/python/poker/frontend/src/App.jsx:415)。
触发／影响：重连缺少连接代次校验；旧 `onmessage` 可继续处理；认证失败未作为终止条件；spectate 变化触发重建连接。
建议：为连接加 generation，清除全部旧回调，认证失败退出登录，座位状态以服务端确认为准。

**48｜自动预操作可能被状态广播取消或跨街执行【待验证】**
位置：[ActionBar.jsx:325](/home/hanxu/code/python/poker/frontend/src/components/ActionBar.jsx:325)。
触发／影响：先清预操作再延时发送；依赖对象更新会清除 timer，清除街道状态与执行 effect 也有时序风险。
建议：预操作绑定 hand/street/turn，在确认发送或明确失效后才清除，补 React 定时器测试。

**49｜键盘操作未排除组合键、重复按键及所有弹窗【静态确认；交互待验证】**
位置：[ActionBar.jsx:535](/home/hanxu/code/python/poker/frontend/src/components/ActionBar.jsx:535)、[PokerTable.jsx:239](/home/hanxu/code/python/poker/frontend/src/components/PokerTable.jsx:239)。
触发／影响：Ctrl/Meta+A、R、长按 Space 等可与牌桌快捷键冲突，弹窗缺少统一焦点约束。
建议：统一快捷键入口，检查 modifier、repeat、defaultPrevented 和模态状态。

**50｜胜率请求乱序覆盖且重复计算【静态确认】**
位置：[EquityDrawer.jsx:161](/home/hanxu/code/python/poker/frontend/src/components/EquityDrawer.jsx:161)。
触发／影响：没有 AbortController／请求序号；快照新数组改变 callback 依赖，可重复计算；旧请求最后返回会覆盖新街结果。
建议：以规范化牌面键去重，取消旧请求，仅接收当前计算版本。

**51｜REST 结束与 WS 结束的终态协议不同【静态确认】**
位置：[endpoints.py:404](/home/hanxu/code/python/poker/backend/app/api/endpoints.py:404)、[router.py:838](/home/hanxu/code/python/poker/backend/app/websocket/router.py:838)。
触发／影响：REST 结束删除房间但不通知现有连接；WS 结束发送终态却未统一关闭连接，处理器仍持有旧 Room。
建议：统一“结算提交→终态广播→关闭连接→移除房间”流程。

**52｜Web 缺少当前结算终态入口，CLI 与 Web 功能不同步【静态确认】**
位置：[App.jsx](/home/hanxu/code/python/poker/frontend/src/App.jsx)、[SettlementModal.jsx](/home/hanxu/code/python/poker/frontend/src/components/SettlementModal.jsx)、[EndRoomConfirmModal.jsx](/home/hanxu/code/python/poker/frontend/src/components/EndRoomConfirmModal.jsx)。
触发／影响：旧结束确认／整桌结算组件未接入主流程，CLI 却仍提供 end 和 bill。
建议：先明确“解散、结束、兑回、批结”的产品语义，再统一客户端入口，移除失效组件。

**53｜CLI 管理员 users 命令引用不存在属性【静态确认】**
位置：[controller.py:346](/home/hanxu/code/python/poker/cli/controller.py:346)。
触发／影响：使用 `self.token`，实际字段为 `self.auth_token`，命令报错。
建议：修正字段并通过真实方法测试，不能只 mock `_show_users`。

**54｜CLI 房间详情请求不带认证【静态确认】**
位置：[api_client.py:126](/home/hanxu/code/python/poker/cli/api_client.py:126)。
触发／影响：只传 `viewer_id`，但后端已正确要求 token 才展示私牌；REST 刷新／回退可丢失自己的私牌和合法动作。
建议：HTTP 客户端统一设置认证上下文。

**55｜CLI 离桌与浏览器离桌语义不同【静态确认】**
位置：[controller.py](/home/hanxu/code/python/poker/cli/controller.py)。
触发／影响：CLI leave 退出连接而非明确 STAND_UP，实际座位和资金等待断线宽限期处理。
建议：明确区分“断开连接”和“离桌兑回”，离桌等待服务器确认。

**56｜启动脚本无差别 SIGKILL 端口占用者【静态确认】**
位置：[start.sh:47](/home/hanxu/code/python/poker/start.sh:47)。
触发／影响：启动、停止、退出均可能杀掉占用 8000/5173 的任意进程；可能误杀其他服务，也绕过优雅退出。
建议：使用受管理 PID 或 systemd，验证进程归属，先 TERM 并等待。

**57｜账务清理脚本备份与删除不安全【静态确认】**
位置：[cleanup_dirty_test_balances.py:26](/home/hanxu/code/python/poker/scripts/cleanup_dirty_test_balances.py:26)。
触发／影响：运行中 WAL 数据库只复制主文件可能不是完整备份；未启用外键，未处理结算批次引用，在线服务缓存还可能写回旧数据。
建议：停写维护或 SQLite backup API；同一事务处理关联，执行真实守恒断言，不仅打印“verified”。

### P3：设计与工程债务

**58｜密码散列、会话传输与部署安全基线不足【静态确认】**
位置：[user.py:12](/home/hanxu/code/python/poker/backend/app/models/user.py:12)、[main.py](/home/hanxu/code/python/poker/backend/main.py)、[poker.service](/home/hanxu/code/python/poker/deploy/poker.service)。
原因／影响：固定盐 SHA-256、宽泛 CORS、默认 HTTP 和 URL token 增加离线猜密、日志泄露等风险；真实反向代理配置未知。
建议：专用密码哈希、HTTPS、敏感日志脱敏、受限来源；公网暴露时应提升至 P1。

**59｜用户资料更新验证顺序错误【静态确认】**
位置：[user_manager.py:221](/home/hanxu/code/python/poker/backend/app/services/user_manager.py:221)。
触发／影响：先改昵称／头像，随后验证旧密码；返回改密失败时内存资料已改变。
建议：先完整校验，再一次性应用修改。

**60｜前后端存在多套重复规则与废弃路径【静态确认】**
位置：[ActionBar.jsx](/home/hanxu/code/python/poker/frontend/src/components/ActionBar.jsx)、[betSizing.js](/home/hanxu/code/python/poker/frontend/src/utils/betSizing.js)、[tableShortcuts.js](/home/hanxu/code/python/poker/frontend/src/utils/tableShortcuts.js)、[equityCalculator.js](/home/hanxu/code/python/poker/frontend/src/utils/equityCalculator.js)。
原因／影响：桌面／手机 JSX 大量复制；测试工具函数与真实组件实现并非始终共用；本地 Monte Carlo 与服务端计算并存。
建议：先消除重复业务逻辑，再抽组件；避免为“抽象”额外添加转发层。

**61｜CLI 与 Web 的 Pot 尺度定义不同【静态确认】**
位置：[commands.py](/home/hanxu/code/python/poker/cli/commands.py)、[ActionBar.jsx](/home/hanxu/code/python/poker/frontend/src/components/ActionBar.jsx)。
触发／影响：CLI 主要按现有底池直接乘比例，Web 还考虑跟注和本轮投入，相同标签产生不同金额。
建议：共享明确的公式和协议契约；UI 标签说明是 raise-to 还是追加金额。

**62｜本地状态、显示字段存在直接缺陷【静态确认】**
位置：[App.jsx:18](/home/hanxu/code/python/poker/frontend/src/App.jsx:18)、[Lobby.jsx](/home/hanxu/code/python/poker/frontend/src/components/Lobby.jsx)。
触发／影响：损坏的用户 JSON 直接导致初始化异常；大厅读取顶层 `action_timeout`，与房间列表返回结构不符。
建议：集中处理存储迁移／容错，用契约测试覆盖列表字段。

**63｜PWA 更新策略会打断牌局【静态确认；设备表现待验证】**
位置：[pwa.js:8](/home/hanxu/code/python/poker/frontend/src/utils/pwa.js:8)、[sw.js](/home/hanxu/code/python/poker/frontend/public/sw.js)。
触发／影响：新 worker 安装后立即 reload；缓存版本手工固定，清理还覆盖同源其他缓存名。
建议：安全阶段提示更新，构建版本化缓存，仅清理本应用命名空间。

**64｜测试和工具链不能支持“长期安全接手”的信心【静态确认】**
位置：[conftest.py:13](/home/hanxu/code/python/poker/backend/tests/conftest.py:13)、[package.json](/home/hanxu/code/python/poker/frontend/package.json)、[test_state_machine.py:317](/home/hanxu/code/python/poker/backend/tests/test_state_machine.py:317)。
原因／影响：固定测试库在收集时删除，不适合并行测试；部分测试直接注入筹码／街道，绕过真实生命周期；错误的 2 倍再加注和无限 RIT 被测试明确接受；没有 CI/lint/typecheck 基线。
建议：临时隔离库、独立规则 oracle、真实生命周期集成测试和持续检查。

## 4. 其他需要保留的待验证风险

以下没有足够动态证据，不计作已确认故障，但不应丢失：

- **机器人决策过期**：[router.py:203](/home/hanxu/code/python/poker/backend/app/websocket/router.py:203) 将可变 table 传入线程，返回后缺少完整 hand/turn 代次复核；需验证计算期间结束／推进牌局。
- **定时任务自取消**：[timeout_manager.py](/home/hanxu/code/python/poker/backend/app/services/timeout_manager.py) 部分取消函数不排除当前任务；需验证回调内切换流程后，在下一 await 被取消的影响。
- **重连后的延期离桌状态未撤销**：[router.py:483](/home/hanxu/code/python/poker/backend/app/websocket/router.py:483) 只取消离线 timer；需验证已设置的 `pending_auto_leave_ids/is_sitting_out` 是否导致回来仍被移除。
- **同手离桌再入座的历史归属**：[room.py:105](/home/hanxu/code/python/poker/backend/app/models/room.py:105) 座位、底池和 departed snapshot 均按 player ID 聚合，需验证历史投入、期末余额和中止退款是否重复／错配。
- **重复摊牌付款**：[state_machine.py](/home/hanxu/code/python/poker/backend/app/engine/state_machine.py) 统计有手号保护，但付款缺少等价幂等保护；需证明外部并发可达性。
- **预操作全下绕过确认、移动端筹码显示与桌面不一致**：[ActionBar.jsx](/home/hanxu/code/python/poker/frontend/src/components/ActionBar.jsx) 需要组件级点击和定时器测试。
- **数据库迁移及多查询读取一致性**：[database.py](/home/hanxu/code/python/poker/backend/app/database.py) 需补真实旧版本升级、迁移中断和并发读取测试，不能仅依据新建库成功判断安全。

## 5. 跨模块不一致与技术债归纳

最重要的不是“不同 AI 的写法不统一”，而是同一业务概念已经存在不同定义：

| 概念 | 当前冲突 |
|---|---|
| 身份 | REST 信任 ID，WS 部分验证 token，匿名 ID 又可能对应座位 |
| 资金 | 旧整桌净盈亏报表与新买入／兑回流水并存 |
| 事务 | SQLite 单次写原子，但业务操作跨多个独立写入 |
| 房间生命周期 | REST、WS、离线任务、机器人分别实现部分流程 |
| 行动计时 | 服务端／CLI 使用服务器时间，Web 本地重新计时 |
| 下注金额 | raise-to、追加额、Pot 比例在不同客户端定义不统一 |
| 游戏币身份 | 用户字段、名称前缀、机器人前缀、座位快照共同判定 |
| 测试事实来源 | 一些测试验证复制逻辑，而非实际组件；一些断言维护错误规则 |
| 依赖边界 | Room 动态导入全局钱包，ConnectionManager 负责持久化，领域对象与基础设施互相依赖 |

应优先建立**一个明确的房间应用服务和一套资金事务边界**。不建议先做全仓“统一风格”或大规模类拆分，那会增加改动量，却不能先消除资金风险。

## 6. 最缺的测试

按价值排序：

1. **鉴权矩阵**：每个 REST/WS 命令覆盖无令牌、无效令牌、错误用户、普通用户、管理员、匿名、机器人 ID、已删除用户。
2. **下注规则矩阵**：完整再加注、不足额全下、累计不足额、短码 Raise 与 ALL_IN 等价、盲注全下。
3. **边池性质测试**：筹码守恒、资格上限、弃牌死钱、未跟注退款、RIT、平局奇数筹码、辅助折让组合。
4. **资金生命周期测试**：买入→下注→离桌→重连→再入座→中止／结束→恢复→批结，比较钱包、在桌筹码和历史。
5. **故障注入**：每次持久化前后失败、事务失败、进程退出、重复命令、重复兑回。
6. **定时与断线集成测试**：离线玩家跨开局、RIT 断线、重连晚于宽限期、慢 socket、计时器自取消。
7. **真实前端组件测试**：按键、弹窗、预操作、请求乱序、断线禁用、手机／桌面同一操作。
8. **跨语言契约测试**：真实 API 返回喂给 React/CLI；牌型结果、下注金额、终态、字段名一致。
9. **长期数据规模测试**：大量手牌历史、账目、房间检查点，以及单实例限制。
10. **生产初始化与迁移测试**：默认账号、安全初始化、预置账号改名、备份恢复和清理历史批次。

当前所谓 CLI “端到端”测试主要直接操作 TestClient，并未贯穿真实 CLI 网络客户端；部分前端布局测试计算的是测试文件里重新写的尺寸公式，不能证明实际 CSS 布局正确。

## 7. 最值得优先处理的 Top 10

1. **封堵全部 ID 鉴权回退**，统一 REST 与 WS 身份来源。
2. **轮换仓库中暴露的认证材料**，停止默认生产账号自动补建。
3. **修复未扣买入却能兑回的 real/play 切换漏洞**。
4. **统一钱包、座位、退款和检查点的事务边界**。
5. **修复中止／恢复时离桌玩家漏退款**。
6. **修复加注增量、不足额全下和最高下注回退**。
7. **修复边池资格与未跟注退款计算**。
8. **修复盲注全下、离桌跳行动和 RIT 卡死**。
9. **统一结束、离线清理、手后处理及定时器生命周期**。
10. **先加入上述问题的回归测试，再调整 immediate／批结语义和客户端交互**。

**接手建议：先处理权限、资金守恒和扑克规则，再做结构整理。当前 200 个后端测试通过，只能证明已有断言通过，不能作为真实资金系统的验收依据。**
