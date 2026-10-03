# AegisGraph

> **面向 AI 生成代码的语义验证层。**  
> 即使代码能运行、测试全绿，也要检查它有没有破坏原来的架构与业务语义。

**Every Change Needs Proof. / 每一次变更，都需要证明。**

AegisGraph 是一个开源的 **Software Change Assurance（软件变更保障）** 产品，适用于 Claude Code、Codex、Cursor、Copilot 以及其他 AI Coding Agent。

它不是另一个“帮你写代码的 Agent”。它站在开发 Agent 旁边，负责四件事：

**Define / 定义 → Observe / 观察 → Judge / 判断 → Prove / 证明。**

## 它解决什么问题

AI 现在写代码越来越快，但真正麻烦的问题变成了：

- 功能看起来正常，却绕过了已经确定的架构规则；
- 新会话忘记旧设计，重复造函数、模块和状态；
- 单元测试通过，但业务不变量已经被破坏；
- 一次局部修改的真实影响范围没人能说清楚；
- Agent 为了让测试通过，顺手把保护规则本身改弱了。

AegisGraph 把这些问题当成“验证问题”，而不是“提示词写得不够好”。

## 5 分钟开始

最快的方式是直接从 GitHub 安装：

```bash
python3 -m pip install "git+https://github.com/nimoolee/aegisgraph.git@v1.0.0"
aegis demo
```

如果你要参与开发，再使用可编辑安装：

```bash
git clone https://github.com/nimoolee/aegisgraph.git
cd aegisgraph
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

先跑一个完全不依赖业务系统的公开 Demo：

```bash
aegis demo
```

然后分析任意 Python 项目：

```bash
aegis discover /path/to/project --conflicts
```

在 CI 中做保守的语义冲突检查：

```bash
aegis check /path/to/project
```

## v1.0 能力

- Python Semantic Discovery（语义发现）
- Semantic Unification（语义统一）
- Conflict Detection（语义冲突检测）
- Fact / Relationship / Rule / Context / Invariant 软件知识图谱
- Change Impact / Blast Radius（变更影响范围）
- Executable Invariants（可执行不变量）
- PASS / FAIL / UNKNOWN Change Proof（变更证明）
- Repair Contract（实现无关的修复验证合同）
- Semantic Change Management（语义规则版本管理）
- REG Dashboard（关系图、状态、Impact 与真实调用审计）

## 最重要的边界

AegisGraph 不会把“自动发现的东西”直接当成业务真理。

`DISCOVERED / CANDIDATE` 只是来自代码的证据；Accepted Rules / Invariants 需要明确的语义权威。证据不足就是 `UNKNOWN`，不能为了好看自动变成 `PASS`。

目标项目在发现和验证阶段保持只读。AegisGraph 也不负责规定你应该使用什么架构、类、模块或重构方案；它只负责告诉开发者：**哪些语义必须恢复、哪些东西不能破坏、还需要什么验证证据。**

## 为什么不是“多写几个测试”

测试通常回答：

> 给定这些输入，程序是否产生这些输出？

AegisGraph 还会问：

> 这次改动影响了什么？哪些规则必须继续成立？我们真的有证据证明它们还成立吗？

这正是 AI Coding Agent 大规模进入真实项目之后最容易缺失的一层。

## 和 AI Agent 配合

```text
人 / Architect 定义需求与不变量
        ↓
Claude Code / Codex / Cursor 实现
        ↓
AegisGraph 独立发现 + 验证
        ↓
PASS → 合并
FAIL → Repair Contract → 交给开发 Agent 修
UNKNOWN → 补证据，不允许假装成功
```

**同一个 Agent 可以写代码，但不应该同时成为“自己证明自己正确”的唯一裁判。**

## License

Apache-2.0。

如果 AegisGraph 帮你抓到了一个“测试没抓到”的真实 Bug，欢迎提交 Issue。真实失败案例会直接决定我们的路线图。
