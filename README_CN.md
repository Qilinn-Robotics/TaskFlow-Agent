## TaskFlow-AI 使用指南

### 概述
TaskFlow-AI 是一个智能体友好的任务管理器，支持自然语言解析、任务存储与子任务拆分，并提供稳定的 Python API 与 CLI 命令，方便 agent 进行理解、推理与调度。

### 快速启动（CLI）
1. 在项目根目录运行：`python3 main_cn.py`
2. 连续输入自然语言任务或命令。
3. 常用命令：
	- `list` 查看任务
	- `today` 查看今天子任务
	- `todayadd <task_id> <index>` 添加今日子任务
	- `todayrm <task_id> <index>` 取消今日子任务
	- `todaypick <关键词>` 按关键词摘取今日子任务
	- `delete <task_id>` 删除任务
	- `subadd <task_id> <子任务>` 添加子任务
	- `subrm <task_id> <index>` 删除子任务
	- `quit` 退出

### 任务存储
每个任务会保存为单独文件：tasks/{task_id}.json，并由 tasks/index.json 记录顺序。
今日子任务清单会保存到 tasks/today.json。
旧版单文件 tasks/tasks.json 会在首次运行时自动迁移。

### Python 接口（适合 agent 集成）
`TaskManager` 提供一组稳定接口：
- `add_task_from_text(text)` 添加任务并执行
- `list_tasks()` 获取全部任务
- `list_today_items()` 获取今天子任务清单
- `get_task(task_id)` 按 ID 获取任务
- `update_status(task_id, status)` 更新任务状态
- `search_tasks(keyword)` 搜索任务
- `add_subtask(task_id, subtask)` 添加子任务
- `remove_subtask(task_id, index)` 删除子任务
- `delete_task(task_id)` 删除任务
- `mark_today_subtask(task_id, index)` 标记今日子任务
- `unmark_today_subtask(task_id, index)` 取消今日子任务
- `pick_today_by_keyword(keyword)` 按关键词摘取今日子任务

### CLI 与 Agent 使用方式
- CLI 使用方式适合终端交互。

- Agent/工具集成建议使用 `TaskManager` Python 接口，结构化、可控、便于自动化。

### CLI Agent 示例（Gemini CLI）
参考工具：[Gemini CLI](https://github.com/google-gemini/gemini-cli)

#### 1) 初始化
![Initialization](img/init.png)

#### 2) 创建任务
自然语言输入：
![Create task (NL)](img/creat_tasks1.png)

通过提示调整子任务：
![Refine subtasks](img/creat_tasks2.png)

确认任务创建：
![Confirm task](img/creat_tasks3.png)

#### 3) 摘取今日子任务
![Pick today](img/today.png)

#### 4) 完成子任务（CLI 命令）
![Complete subtask](img/today2.png)

#### 5) 列出剩余任务与今日子任务
![List remaining and today](img/today3.png)

### Python 接口使用示例（伪代码）
```python
from main import TaskManager

manager = TaskManager()
task = manager.add_task_from_text("完成 CHAMP 论文，下周三，高优先")
manager.add_subtask(task.id, "整理实验记录")
manager.add_subtask(task.id, "补全图表")
today = manager.list_today_items()
```

### 启动 Prompt（让 agent 先读指令）
默认启动 prompt（要求 agent 先阅读 [Agent_CN.md](Agent_CN.md)）：

“你是 TaskFlow 任务管理智能体。现在进行初始化！默认使用 plan 模式。请先完整阅读并遵守 [Agent_CN.md](Agent_CN.md) 中的约束与流程，然后在 CLI 中运行 `list`，成功返回即视为初始化成功。”