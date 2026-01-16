## TaskFlow Execution Instructions (for AI)

### Critical Constraints
1. **Do not modify any code files** (including `main.py` and any source files).
2. Do not write any new scripts to operate tasks; only use commands via `main.py`.
3. You may only **run the project** and **enter commands** to populate task data.

### How to Run
- In the project root:
	- `python3 main.py`

### Interactive Input
`main.py` reads multiple commands from standard input; you can enter multiple tasks or commands.

### Run Mode (Plan Mode) [Default mode]
When in **Plan Mode**, follow this prompt:
"You are in Plan Mode. First read and understand the user’s request. Produce a draft plan and TODO list, but **do not** write anything into TaskFlow. Only after the user explicitly confirms (e.g., 'confirm/start/agree') may you input tasks via `main.py`."

#### Copy-Paste Interactive Example
After starting, enter in order:
1) `Plan a marketing meeting next Monday, high priority`
2) `Design the Q1 marketing campaign plan, end of month`
3) `Follow up on supplier contract, low priority`
4) `list`
5) `quit`

Available Commands:
- `help` show help
- `list` list saved tasks
- `today` show today's subtasks
- `todayadd <task_id> <index>` add a subtask to today
- `todayrm <task_id> <index>` remove a subtask from today
- `todaypick <keyword>` pick today's subtasks by keyword
- `delete <task_id>` delete a task
- `subadd <task_id> <subtask>` add a subtask
- `subrm <task_id> <index>` remove a subtask (index starts at 1)
- `quit` or `exit` quit

### Task Filling Requirements
You can enter **multiple tasks** in natural language. Examples:
- Plan a marketing meeting next Monday, high priority
- Design the Q1 marketing campaign plan, end of month
- Follow up on supplier contract, low priority

### Verification Steps
1. After entering multiple tasks, run `list` to confirm tasks are saved.
2. Exit the program.

### Notes
Each task is saved as a separate file: `tasks/{task_id}.json`, with ordering in `tasks/index.json`.
Today's subtask list is stored in `tasks/today.json`.
