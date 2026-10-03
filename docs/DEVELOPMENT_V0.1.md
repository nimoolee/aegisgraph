# AegisGraph v0.1 Development Specification

> 版本：0.1 Draft 1  
> 产品定位：Software Change Assurance / Software Proof Layer（软件变更验证层 / 软件证明层）  
> 核心口号：**Every Change Needs Proof. / 每一次变更，都需要证明。**

---

## 1. Why / 为什么做

现代软件系统本质上是一个高维关系网络，但日常开发通常依赖线性文档、文件级 diff 和局部测试。
结果是：单个修改本身可能正确，但它破坏了系统中其他看不见的语义关系。

AegisGraph 的第一目标不是“自动写代码”，而是回答：

> **一次 Change（变更）修改了哪些 Business Facts（业务事实），影响了哪些 Critical Paths（关键链路），哪些 Invariants（不变量）需要重新证明？**

第一阶段用两个真实项目做 Dogfooding（自用验证）：

- Trading V2.1
- Auto Trading System

这两个系统只作为 Reference Systems（参考系统），不进入 AegisGraph Core 的产品语义。

---

## 2. v0.1 Success Definition / 成功定义

v0.1 只要求跑通以下闭环：

```text
Git Change
   ↓
Semantic Change Detection
语义变更识别
   ↓
Affected Business Facts
受影响业务事实
   ↓
Impact Graph / Blast Radius
影响图 / 变更爆炸半径
   ↓
Affected Rules + Invariants
受影响规则 + 不变量
   ↓
Selective Verification
选择性验证
   ↓
Change Proof
变更证明
```

### v0.1 必须做到

1. 能注册 Business Fact（业务事实）。
2. 能注册 Relationship / Edge（关系 / 边）。
3. 能注册 Rule（规则）。
4. 能注册 Invariant（不变量）。
5. 能表达 Context（上下文），至少支持 Temporal Context（时间上下文）。
6. 能记录 Change（变更）。
7. 能从变更点向外计算 Impact Set（影响集合）。
8. 能选择受影响 Invariant 并运行验证。
9. 能生成结构化 Change Proof（变更证明）。

### v0.1 暂不要求

- 不要求自动理解整个代码库。
- 不要求完整 AI Agent 自主建图。
- 不要求图数据库（Graph Database）。
- 不要求复杂前端 UI。
- **禁止** AegisGraph 自动修复、写入或生成目标业务代码 Patch；修复由独立 Developer AI / 人类开发者完成。
- 不要求成为交易系统运行时依赖。

---

## 3. Product Boundary / 产品边界

### 3.1 AegisGraph Core 只理解通用语义

Core 可以理解：

- Fact Node（事实节点）
- Relationship（关系）
- Rule（规则）
- Invariant（不变量）
- Context（上下文）
- State（状态）
- Change（变更）
- Evidence（证据）
- Proof（证明）

Core **不应该理解**：

- BTC / ETH
- Polymarket
- CLOB
- Trading Cash
- Safety Cash
- Settlement 的具体业务定义

这些都属于 Integration / Domain Adapter（集成 / 领域适配层）。

### 3.2 Sidecar Principle / 旁路原则

AegisGraph 必须是 Observer / Sidecar（旁路观察者）。

```text
Business System
      │
      │ observed / scanned / replayed
      ▼
Integration Adapter
      │
      ▼
AegisGraph Core
```

禁止形成：

```text
Business System
      ↓ hard dependency
AegisGraph
      ↓
业务系统才能运行
```

验收原则：

- 删除 AegisGraph，业务系统仍可运行。
- 删除 integrations，AegisGraph Core 仍可运行。

### 3.3 Read-Only Target Principle / 目标系统只读原则

AegisGraph 是 Verifier / Auditor（验证者 / 审计者），不是 Developer / Fixer（开发者 / 修复者）。

> **AegisGraph never writes the change it judges. / AegisGraph 永远不亲自修改它所审判的代码。**

对被验证项目，v0.1 的 Target Access Policy（目标访问策略）固定为：

- `target_access = read_only`
- `may_modify_target = false`
- `may_generate_target_patch = false`
- `may_emit_repair_contract = true`

允许读取：Source Code、Git Diff、Tests、Logs、Runtime State、Historical Data、Database Snapshot。

禁止直接修改：业务源码、配置、数据库、Runtime State、生产状态。

FAIL 时 AegisGraph 的终点不是提交 Patch，而是输出 **Repair Contract（修复契约）**，交给独立 Developer AI / 人类开发者实现。

```text
Developer AI / Human
        │
        │ writes change
        ▼
      Git Diff
        │
        ▼
   AegisGraph
   read-only verify
        │
   PASS / FAIL / UNKNOWN
        │
        ├── PASS → next stage
        ├── UNKNOWN → request evidence
        └── FAIL → Repair Contract → Developer AI
```

Repair Contract 至少包含：

- `Must Change`：必须改变的语义
- `Must Preserve`：必须保持的系统事实
- `Must Not Change`：禁止通过削弱规则、删测试、改证据制造 PASS
- `Required Verification`：修复后必须重跑的验证
- `Required Evidence`：证明修复成立所需证据

Repair Contract 是 implementation-agnostic（实现无关）的；默认不包含代码 diff。

---

## 4. Core Domain Model / 核心领域模型

### 4.1 Fact Node / 事实节点

Fact Node 代表具有独立业务语义的事实，而不是“所有前端字段”。

示例：

```text
AvailableTradingCash
OrderEligibility
Position
SettlementState
```

最小字段：

- `id`: Semantic Identity（语义身份）
- `name`: 名称
- `description`: 业务含义
- `kind`: 类型
- `status`: ACTIVE / DEPRECATED
- `criticality`: CRITICAL / HIGH / MEDIUM / LOW
- `version`: 版本
- `provenance`: 来源
- `confidence`: 置信度

### 4.2 Semantic Identity / 语义身份

业务事实不能绑定文件名或函数名。

错误：

```text
capital_allocator.py::get_available_cash
```

正确：

```text
cash.available_trading
```

代码可以移动、重命名或重构，Semantic Identity 应保持稳定。

---

## 5. Relationship / Edge / 关系

Relationship 不只是 related_to，而必须尽量表达语义和因果强度。

v0.1 支持：

- `source_from`：来源于
- `derived_from`：派生自
- `depends_on`：依赖于
- `controls`：控制
- `reads`：读取
- `writes`：写入
- `displays`：展示
- `validates`：验证
- `transitions`：状态转换

每条 Edge 预留：

- `criticality`
- `confidence`
- `provenance`
- `version`
- `valid_from`
- `valid_to`

未来目标是形成 Software Causal Graph（软件因果图谱），而不是只有普通 Knowledge Graph（知识图谱）。

---

## 6. Rule / 派生规则

Rule 描述一个或多个事实如何计算、转换或约束另一个事实。

示例：

```text
AvailableCash = TradingCash - ReservedCash
```

Rule 最小字段：

- `id`
- `name`
- `inputs`
- `outputs`
- `expression` 或 executor reference
- `applies_when`（适用上下文）
- `criticality`
- `version`

Rule 本身必须版本化，不能覆盖历史版本。

---

## 7. Invariant / 不变量

Invariant 定义“什么叫系统仍然正确”。

示例：

```text
available_cash >= 0
```

或：

```text
FILLED order -> fill_qty > 0
```

或条件化：

```text
WHEN phase == SETTLING
settling_cash must not become available_cash
```

Invariant 不是文档描述，最终必须可以 Machine Executable（机器执行）。

v0.1 支持：

- Python callable validator
- 简单 expression validator

每个 Invariant 需要知道：

- 它验证哪些 Facts
- 适用于什么 Context / State
- 需要什么 Evidence
- 如何执行
- 失败时输出什么解释

---

## 8. Context / 上下文

同一个 Fact 在不同条件下可能由不同规则控制，因此 Context 必须进入核心模型。

v0.1 首先支持：

### 8.1 Temporal Context / 时间上下文

例如：

```text
PRE_OPEN
OPEN
CORE
LATE
SETTLING
SETTLED
```

时间阶段不是前端自己计算出来的业务规则。
它应该拥有 Single Source of Truth（单一事实来源）。

### 8.2 Temporal Boundary Change / 时间边界变化

例如：

```text
CORE = 120s ~ 60s
```

改成：

```text
CORE = 150s ~ 60s
```

AegisGraph 必须把它识别为 Temporal Semantic Change（时间语义变化），而不是普通常量修改。

它可能影响：

- Signal Generation（信号生成）
- Entry Eligibility（入场资格）
- Risk Control（风险控制）
- Data Sampling（数据采样）
- Historical Replay Label（历史回放标签）

### 8.3 Future Contexts / 后续上下文

Schema 预留：

- Environment Context（环境上下文）
- Account Context（账户上下文）
- Market Context（市场上下文）

---

## 9. State / 状态

很多 bug 并不是值错，而是值在错误状态出现。

因此 v0.1 Schema 必须允许 State-Aware Rule（状态感知规则）。

示例状态：

```text
CREATED
SENT
OPEN
PARTIAL_FILLED
FILLED
CANCELLED
SETTLING
SETTLED
```

示例约束：

```text
WHEN order.state == FILLED
position change must exist
```

---

## 10. Event Time / 事件时间

Temporal Context 表示“处于哪个时间阶段”；Event Time 表示“事件发生顺序”。

AegisGraph 必须预留 Temporal Ordering Constraint（时间顺序约束）。

示例：

```text
FillReceived
must happen before
PositionUpdated
```

```text
SettlementConfirmed
must happen before
SettlingCashReleased
```

v0.1 可先记录 timestamp 与 ordering metadata，不实现完整复杂时序逻辑。

---

## 11. Provenance / 来源证明与 Confidence / 置信度

每一个 Fact / Relationship / Rule 都需要回答：

> Why do we believe this? / 为什么相信它？

来源类型：

- `explicit`：人工 / 配置显式定义
- `static`：静态代码分析
- `observed`：运行时观测
- `replay`：历史回放验证
- `ai_inferred`：AI 推断

Confidence（置信度）建议 0.0 ~ 1.0。

原则：

- AI 推断不能与 Runtime Evidence（运行时证据）拥有相同权重。
- Change Proof 应优先使用可重复验证的 Evidence（证据）。

---

## 12. Versioned Graph / 版本化图谱

所有核心对象必须预留版本字段，至少：

- `version`
- `valid_from`
- `valid_to`
- `commit_sha`

原因：

不能用今天的软件关系图去解释昨天的历史 Replay。

Rule / Node / Relationship / Invariant / Context 都必须允许历史版本共存。

---

## 13. Criticality / 关键等级

不是所有变化都值得跑完整验证。

等级：

- `CRITICAL`
- `HIGH`
- `MEDIUM`
- `LOW`

Impact 未来可近似为：

```text
Impact Score
≈ Graph Distance
× Edge Strength
× Criticality
× Confidence
```

v0.1 不必实现复杂数学模型，但必须保留 Criticality 字段。

---

## 14. Change Types / 变更类型

v0.1 需要显式区分：

- `SOURCE_CHANGE`：事实来源变化
- `RULE_CHANGE`：规则 / 公式变化
- `NODE_CHANGE`：事实语义变化
- `NODE_ADDED`：新增事实
- `NODE_DEPRECATED`：事实废弃
- `RELATIONSHIP_CHANGE`：关系变化
- `INVARIANT_CHANGE`：不变量变化
- `TEMPORAL_CHANGE`：时间规则 / 时间边界变化
- `STATE_CHANGE`：状态模型变化
- `CODE_CHANGE`：仅检测到代码变化、尚未完成语义映射

---

## 15. Change Impact Engine / 变更影响引擎

输入：

- Git diff
- Changed files / symbols
- Manual or AI semantic mapping

输出：

- Changed Facts
- Directly affected Rules
- Dependent Facts
- Affected Critical Paths
- Affected Invariants
- Suggested Tests / Replay

第一版不要无限 BFS（广度优先遍历）整个图。

传播必须考虑：

- Edge Type（边类型）
- Criticality（关键等级）
- Confidence（置信度）
- Graph Distance（图距离）
- Context（上下文）

---

## 16. Selective Verification / 选择性验证

AegisGraph 不应该每次都跑全部数据。

流程：

```text
Change
  ↓
Impact Set
  ↓
Affected Invariants
  ↓
Affected Tests
  ↓
Affected Replay Data
  ↓
Proof
```

v0.1 验证层次：

1. Static Validation（静态验证）
2. Invariant Check（不变量检查）
3. Unit Test（单元测试）
4. Integration Test（集成测试）
5. Chain Test（链路测试）
6. Historical Replay（历史回放）

Runtime Validation（运行时验证）先预留接口。

---

## 17. Change Proof / 变更证明

v0.1 最终产物不是“Graph”，而是 Proof。

建议结构：

```text
CHANGE PROOF

Change ID
Commit SHA
Risk Level

Semantic Changes
- facts changed
- rules changed
- source changes
- temporal changes

Impact
- direct nodes
- dependent nodes
- critical paths

Verification
- invariants checked
- tests executed
- replay events

Unexpected Divergence
- count
- explanations

Evidence
- code path
- test result
- replay result

Verdict
PASS / WARN / FAIL / UNKNOWN
```

`UNKNOWN` 必须是合法结果。
AegisGraph 不应该在证据不足时假装 PASS。

---

## 18. Human Seed + AI Expand / 人工播种 + AI 扩展

第一版不要尝试让 AI 自动理解整个系统。

正确策略：

1. Human Seed（人工播种）
   - 手工定义少量关键 Fact
   - 手工定义关键 Rule
   - 手工定义关键 Invariant

2. AI Expand（AI 扩展）
   - 扫描代码寻找实现位置
   - 提出候选 Relationship
   - 提出候选 Fact
   - 提出可能遗漏的 Invariant

3. Evidence Confirm（证据确认）
   - 静态代码
   - 测试
   - Replay
   - Runtime Evidence

AI 的推断在被确认之前必须保留较低 Confidence。

---

## 19. First Reference Systems / 第一批参考系统

### 19.1 Trading V2.1

优先提供以下场景：

- Data Flow（数据流）
- Source of Truth（权威事实来源）
- UI Consistency（前后端一致性）
- Settlement（结算）
- Manual Trading（手动交易）

### 19.2 Auto Trading System

优先提供：

- Decision Chain（决策链）
- Strategy（策略）
- Order Eligibility（下单资格）
- Risk Control（风险控制）
- Temporal Rules（时间规则）
- State Transition（状态转换）

重要：以上业务概念只能存在于 integrations/reference definitions，不能进入 Core 通用模型。

---

## 20. v0.1 First Domain Slice / 第一条领域切片

第一版只选最痛且最容易验证价值的核心闭环：

```text
Cash
 ↓
Order Eligibility
 ↓
Order
 ↓
Fill
 ↓
Position
 ↓
Settlement
 ↓
Cash
```

建议初始规模：

- 20~30 个 Fact Nodes
- 40~60 条 Relationships
- 15~25 个 Invariants
- 5~10 条 Critical Paths

但这些数字是上限建议，不是启动门槛。

真正的第一个成功案例只要求：

> 一次真实修改触发 AegisGraph，系统正确识别受影响链路，并提前发现或证明一个真实风险。

---

## 21. Architecture / 代码结构

```text
aegis-graph/
├── docs/
├── src/aegis_graph/
│   ├── core/          # 通用 Domain Models
│   ├── graph/         # Software Graph
│   ├── change/        # Change Model / Semantic Change
│   ├── impact/        # Impact Analysis
│   ├── invariants/    # Invariant Engine
│   ├── replay/        # Replay Engine
│   ├── evidence/      # Evidence Model
│   ├── proof/         # Change Proof
│   └── integrations/  # Adapter interfaces only
├── tests/
└── pyproject.toml
```

v0.1 先使用：

- Python 3.11+
- Standard Library 优先
- SQLite 可选，用于后续持久化
- 不引入 Neo4j / Kafka / Vector DB
- Graph 第一版可先用内存邻接结构或轻量实现

---

## 22. Development Principles / 开发原则

### P1. No Change Without Proof
没有影响分析和验证结果的关键变更，不应被视为已完成。

### P2. Evidence Over Opinion
证据优先于 AI 判断。

### P3. Semantic Identity Over File Identity
业务事实身份优先于文件 / 函数身份。

### P4. Selective Verification Over Full Retest
优先重跑真正受影响的链路。

### P5. Unknown Is Better Than False Pass
证据不足时输出 UNKNOWN，而不是虚假 PASS。

### P6. Product Core Must Stay Generic
Reference System 的业务语义不能泄漏进 Core。

### P7. Every Real Bug Becomes Permanent Knowledge
每一个真实 Bug 修复后，应尽量沉淀为 Fact / Relationship / Rule / Invariant / Replay Case。

---

## 23. v0.1 Milestones / 里程碑

### M0 — Skeleton
- 项目目录
- Python virtual environment
- 核心 dataclass / enum
- 基础测试

### M1 — Graph Core
- Node / Relationship
- Rule / Invariant metadata
- Context / version / provenance / confidence / criticality

### M2 — Change + Impact
- Change model
- 从 changed facts 计算影响集合
- 输出 affected invariants

### M3 — Verification
- Invariant executor
- Selective test hooks
- Proof result model

### M4 — First Real Integration
- 接入 Trading V2.1 的一小段 Cash 链路
- 只做 Human Seed

### M5 — Second Real Integration
- 接入 Auto Trading 的 Temporal Rule / Order Eligibility 链路

### M6 — First Real Proof
- 对一个真实 Git change 生成 Change Proof
- 最好提前发现一个真实风险

---

## 24. v0.1 Non-Goals / 非目标

为了防止第一版失控，以下明确不做：

- 漂亮的大型 Graph 可视化前端
- 全仓库自动语义理解
- 自动修改业务代码
- 自研图数据库
- 复杂多 Agent 编排
- 大模型训练
- 全量 Runtime Tracing Platform
- 完整企业权限系统

---

## 25. MVP KPI / 核心指标

第一阶段不要用 LOC（代码行数）衡量价值。

真正 KPI：

1. 真实 Change 中正确识别隐藏影响的次数。
2. 提前发现真实 Bug 的次数。
3. 误报（False Positive）率。
4. 漏报（False Negative）案例。
5. Proof 生成时间。
6. 每次修改额外人工维护成本。

最重要的判断：

> **AegisGraph 是否在开发者发现问题之前，先指出了一条会被破坏的链路？**

如果做到，v0.1 产品假设成立。
