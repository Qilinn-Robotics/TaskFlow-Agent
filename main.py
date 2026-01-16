from __future__ import annotations

import json
import re
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Storage location for persisted tasks inside the tasks/ directory
TASKS_DIR = Path(__file__).parent / "tasks"
TASKS_INDEX = TASKS_DIR / "index.json"
TODAY_PATH = TASKS_DIR / "today.json"


class ParseError(Exception):
    """Raised when the natural language parsing fails."""


class ValidationError(Exception):
    """Raised when parsed data fails validation."""


@dataclass
class Task:
    id: str
    name: str
    description: str
    due_date: Optional[str]  # ISO date string (YYYY-MM-DD) or None
    priority: str  # high, medium, low
    raw: str
    created_at: str  # ISO timestamp
    status: str  # pending | executed
    result: Optional[str]
    subtasks: List[str] = field(default_factory=list)


PRIORITY_KEYWORDS = {
    "high": "high",
    "urgent": "high",
    "important": "high",
    "中": "medium",
    "medium": "medium",
    "normal": "medium",
    "low": "low",
    "低": "low",
    "高": "high",
    "低优先": "low",
    "高优先": "high",
}


WEEKDAY_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
    "mon": 0,
    "tue": 1,
    "tues": 1,
    "wed": 2,
    "thu": 3,
    "thur": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
    "周一": 0,
    "周二": 1,
    "周三": 2,
    "周四": 3,
    "周五": 4,
    "周六": 5,
    "周日": 6,
    "周天": 6,
    "星期一": 0,
    "星期二": 1,
    "星期三": 2,
    "星期四": 3,
    "星期五": 4,
    "星期六": 5,
    "星期日": 6,
    "星期天": 6,
}


DATE_PATTERNS = [
    r"\b\d{4}-\d{1,2}-\d{1,2}\b",  # 2026-01-16
    r"\b\d{4}/\d{1,2}/\d{1,2}\b",  # 2026/01/16
    r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",  # 01/16/2026
]


def _normalize_task_dict(item: Dict[str, Any]) -> Dict[str, Any]:
    if "description" not in item or not item["description"]:
        item["description"] = item.get("raw", "")
    if "subtasks" not in item or item["subtasks"] is None:
        item["subtasks"] = []
    return item


def _load_task_file(path: Path) -> Optional[Task]:
    try:
        item = json.loads(path.read_text(encoding="utf-8"))
        normalized = _normalize_task_dict(item)
        return Task(**normalized)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def load_tasks() -> List[Task]:
    TASKS_DIR.mkdir(parents=True, exist_ok=True)

    # Always load from index. If no index, it's a fresh start or orphan scan.
    order = []
    if TASKS_INDEX.exists():
        try:
            content = TASKS_INDEX.read_text(encoding="utf-8")
            if content:
                order = json.loads(content)
        except json.JSONDecodeError:
            pass  # Treat corrupted index as no index

    tasks: List[Task] = []
    loaded_ids = set()

    if isinstance(order, list):
        for task_id in order:
            path = TASKS_DIR / f"{task_id}.json"
            if path.exists():
                task = _load_task_file(path)
                if task:
                    tasks.append(task)
                    loaded_ids.add(task.id)

    # Load orphans (valid task files not in index)
    for path in TASKS_DIR.glob("*.json"):
        if path.name in {"index.json", "example.json", "today.json"}:
            continue
        if path.stem not in loaded_ids:
            task = _load_task_file(path)
            if task:
                tasks.append(task)
    return tasks


def _load_today_items() -> List[Dict[str, Any]]:
    if not TODAY_PATH.exists():
        return []
    try:
        data = json.loads(TODAY_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        # New format: list of {task_id, subtask_index, subtask}
        if data and isinstance(data[0], dict):
            return data
        # Legacy format (list of task_id strings) is ignored for subtask-based today list
        return []
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def _save_today_items(items: List[Dict[str, Any]]) -> None:
    TODAY_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_tasks(tasks: List[Task]) -> None:
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    # Write each task to its own file
    for task in tasks:
        task_path = TASKS_DIR / f"{task.id}.json"
        task_path.write_text(
            json.dumps(asdict(task), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    # Write index to preserve order
    TASKS_INDEX.write_text(
        json.dumps([t.id for t in tasks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def extract_priority(text: str) -> Tuple[str, str]:
    lowered = text.lower()
    found: Optional[str] = None
    for keyword, value in PRIORITY_KEYWORDS.items():
        if keyword in text or keyword in lowered:
            found = value
            text = re.sub(re.escape(keyword), "", text, flags=re.IGNORECASE)
    return found or "medium", text.strip()


def parse_iso_candidate(token: str) -> Optional[date]:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(token, fmt).date()
        except ValueError:
            continue
    return None


def next_weekday(target: int) -> date:
    today = date.today()
    days_ahead = (target - today.weekday() + 7) % 7
    days_ahead = 7 if days_ahead == 0 else days_ahead
    return today + timedelta(days=days_ahead)


def extract_due_date(text: str) -> Tuple[Optional[date], str]:
    working = text

    # Explicit date tokens
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, working)
        if match:
            token = match.group(0)
            parsed = parse_iso_candidate(token)
            if parsed:
                working = working.replace(token, "").strip()
                return parsed, working

    lowered = working.lower()
    today = date.today()

    relative_keywords = {
        "today": 0,
        "今天": 0,
        "tomorrow": 1,
        "明天": 1,
        "day after tomorrow": 2,
        "后天": 2,
        "next week": 7,
        "下周": 7,
    }
    for key, offset in relative_keywords.items():
        if key in lowered or key in working:
            working = re.sub(re.escape(key), "", working, flags=re.IGNORECASE).strip()
            return today + timedelta(days=offset), working

    # Next weekday handling, English and Chinese
    next_weekday_match = re.search(r"next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", lowered)
    if next_weekday_match:
        wd = next_weekday_match.group(1)
        working = re.sub(r"next\s+" + wd, "", lowered).strip()
        return next_weekday(WEEKDAY_MAP[wd]), working

    cn_next_weekday = re.search(r"下周(一|二|三|四|五|六|日|天)", working)
    if cn_next_weekday:
        wd_token = cn_next_weekday.group(0)
        wd_key = "周" + cn_next_weekday.group(1)
        working = working.replace(wd_token, "").strip()
        return next_weekday(WEEKDAY_MAP[wd_key]), working

    # Plain weekday in this week (or next if already passed today)
    for key, idx in WEEKDAY_MAP.items():
        if key in lowered or key in working:
            working = re.sub(re.escape(key), "", working, flags=re.IGNORECASE).strip()
            candidate = today + timedelta((idx - today.weekday()) % 7)
            return candidate, working

    return None, working.strip()


def clean_task_name(text: str) -> str:
    # Remove stray punctuation and multiple spaces
    cleaned = re.sub(r"\s+", " ", text)
    cleaned = re.sub(r"[,，.。!！?？]", "", cleaned)
    return cleaned.strip()


def parse_task(text: str) -> Dict[str, Any]:
    if not text or not text.strip():
        raise ParseError("Input is empty; cannot parse task.")

    priority, leftover = extract_priority(text)
    due_date, leftover = extract_due_date(leftover)
    name = clean_task_name(leftover)

    if not name:
        raise ParseError("Failed to extract a task name; please provide a clearer description.")

    return {
        "name": name,
        "priority": priority,
        "due_date": due_date,
    }


def validate_task(parsed: Dict[str, Any]) -> None:
    if not parsed["name"]:
        raise ValidationError("Task name cannot be empty.")

    due = parsed.get("due_date")
    if due and due < date.today():
        raise ValidationError("Due date is in the past; please provide a future date.")


def make_task(parsed: Dict[str, Any], raw: str) -> Task:
    return Task(
        id=str(uuid.uuid4()),
        name=parsed["name"],
        description=raw.strip(),
        due_date=parsed["due_date"].isoformat() if parsed.get("due_date") else None,
        priority=parsed["priority"],
        raw=raw,
        created_at=datetime.now().isoformat(timespec="seconds"),
        status="executed",
        result=None,
        subtasks=[],
    )


def execute_task(task: Task) -> str:
    # Placeholder execution: simulate success and return a human-readable result.
    if task.due_date:
        return f"Task scheduled: {task.name}, due {task.due_date}, priority {task.priority}."
    return f"Task scheduled: {task.name}, priority {task.priority}."


class TaskManager:
    """Agent-friendly task manager API."""

    def __init__(self) -> None:
        self._tasks: List[Task] = load_tasks()
        self._today_items: List[Dict[str, Any]] = _load_today_items()

    @property
    def tasks(self) -> List[Task]:
        return list(self._tasks)

    def add_task_from_text(self, text: str) -> Task:
        parsed = parse_task(text)
        validate_task(parsed)
        task = make_task(parsed, text)
        task.result = execute_task(task)
        self._tasks.append(task)
        save_tasks(self._tasks)
        return task

    def list_tasks(self) -> List[Task]:
        return list(self._tasks)

    def list_today_tasks(self) -> List[Task]:
        # Deprecated for subtask-based today list; keep for compatibility
        return []

    def list_today_items(self) -> List[Dict[str, Any]]:
        return list(self._today_items)

    def get_task(self, task_id: str) -> Optional[Task]:
        return next((t for t in self._tasks if t.id == task_id), None)

    def find_task(self, identifier: str) -> Task:
        if not identifier:
            raise ValidationError("Task identifier cannot be empty.")
        by_id = self.get_task(identifier)
        if by_id:
            return by_id
        matches = [t for t in self._tasks if t.name == identifier]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValidationError("Multiple tasks match the same name; please use the task ID.")
        raise ValidationError("Task not found.")

    def update_status(self, task_id: str, status: str) -> Task:
        task = self.find_task(task_id)
        task.status = status
        save_tasks(self._tasks)
        return task

    def mark_today_subtask(self, task_id: str, index: int) -> Dict[str, Any]:
        task = self.find_task(task_id)
        if index < 0 or index >= len(task.subtasks):
            raise ValidationError("Invalid subtask index.")
        subtask_text = task.subtasks[index]
        item = {
            "task_id": task.id,
            "subtask_index": index,
            "subtask": subtask_text,
        }
        if item not in self._today_items:
            self._today_items.append(item)
            _save_today_items(self._today_items)
        return item

    def unmark_today_subtask(self, task_id: str, index: int) -> None:
        self._today_items = [
            i for i in self._today_items
            if not (i.get("task_id") == task_id and i.get("subtask_index") == index)
        ]
        _save_today_items(self._today_items)

    def _sync_today_items_after_subtask_change(self, task: Task, removed_index: int) -> None:
        updated: List[Dict[str, Any]] = []
        for item in self._today_items:
            if item.get("task_id") != task.id:
                updated.append(item)
                continue
            idx = item.get("subtask_index", -1)
            if idx == removed_index:
                continue
            if idx > removed_index:
                new_index = idx - 1
            else:
                new_index = idx
            if 0 <= new_index < len(task.subtasks):
                updated.append(
                    {
                        "task_id": task.id,
                        "subtask_index": new_index,
                        "subtask": task.subtasks[new_index],
                    }
                )
        self._today_items = updated
        _save_today_items(self._today_items)

    def pick_today_by_keyword(self, keyword: str) -> List[Dict[str, Any]]:
        if not keyword or not keyword.strip():
            raise ValidationError("Keyword cannot be empty.")
        lowered = keyword.lower()
        picked: List[Dict[str, Any]] = []
        for task in self._tasks:
            for idx, sub in enumerate(task.subtasks):
                if lowered in sub.lower() or lowered in task.name.lower():
                    item = {
                        "task_id": task.id,
                        "subtask_index": idx,
                        "subtask": sub,
                    }
                    if item not in self._today_items:
                        self._today_items.append(item)
                    picked.append(item)
        if picked:
            _save_today_items(self._today_items)
        return picked

    def add_subtask(self, task_id: str, subtask: str) -> Task:
        if not subtask or not subtask.strip():
            raise ValidationError("Subtask cannot be empty.")
        task = self.find_task(task_id)
        task.subtasks.append(subtask.strip())
        save_tasks(self._tasks)
        return task

    def remove_subtask(self, task_id: str, index: int) -> Task:
        task = self.find_task(task_id)
        if index < 0 or index >= len(task.subtasks):
            raise ValidationError("Invalid subtask index.")
        task.subtasks.pop(index)
        save_tasks(self._tasks)
        self._sync_today_items_after_subtask_change(task, index)
        return task

    def complete_today_subtask(self, task_id: str, index: int) -> str:
        task = self.find_task(task_id)
        if index < 0 or index >= len(task.subtasks):
            raise ValidationError("Invalid subtask index.")
        removed = task.subtasks[index]
        self.remove_subtask(task_id, index)
        return removed

    def delete_task(self, task_id: str) -> None:
        task = self.find_task(task_id)
        self._tasks = [t for t in self._tasks if t.id != task.id]
        task_path = TASKS_DIR / f"{task.id}.json"
        if task_path.exists():
            task_path.unlink()
        save_tasks(self._tasks)
        if self._today_items:
            self._today_items = [i for i in self._today_items if i.get("task_id") != task.id]
            _save_today_items(self._today_items)

    def search_tasks(self, keyword: str) -> List[Task]:
        if not keyword:
            return []
        lowered = keyword.lower()
        return [t for t in self._tasks if lowered in t.name.lower() or lowered in t.raw.lower()]


def handle_input(user_input: str, manager: TaskManager) -> str:
    task = manager.add_task_from_text(user_input)
    return task.result or "Task added."


def list_tasks(tasks: List[Task]) -> str:
    if not tasks:
        return "No tasks yet."
    lines = []
    for t in tasks:
        due = t.due_date or "Not set"
        header = (
            f"- {t.name} | Due: {due} | Priority: {t.priority} | Status: {t.status}"
            f" | Description: {t.description}"
        )
        lines.append(header)
        if t.subtasks:
            for idx, sub in enumerate(t.subtasks, start=1):
                lines.append(f"  Subtask {idx}: {sub}")
        else:
            lines.append("  Subtasks: none")
    return "\n".join(lines)


def list_today_items(items: List[Dict[str, Any]], manager: TaskManager) -> str:
    if not items:
        return "No subtasks for today."
    lines = []
    for item in items:
        task = manager.get_task(item.get("task_id", ""))
        task_name = task.name if task else "Unknown task"
        index = item.get("subtask_index", 0) + 1
        subtask = item.get("subtask", "")
        lines.append(f"- {task_name} | Subtask {index}: {subtask}")
    return "\n".join(lines)


def print_help() -> None:
    print("Enter a natural-language task, e.g., 'Plan a marketing meeting next Monday, high priority'.")
    print(
        "Commands: list (show tasks); today (show today's subtasks); "
        "todayadd <task_id|name> <index> (add subtask to today); "
        "todayrm <task_id|name> <index> (remove subtask from today); "
        "todaypick <keyword> (pick today's subtasks by keyword); "
        "todaydone <task_id|name> <index> (complete a today's subtask); "
        "delete <task_id|name> (delete task); "
        "subadd <task_id|name> <subtask> (add subtask); subrm <task_id|name> <index> (remove subtask); "
        "help; quit/exit."
    )


def main() -> None:
    manager = TaskManager()
    print("Task manager started. Enter a task, or type help, list, or quit.")
    if manager.tasks:
        print(f"Loaded {len(manager.tasks)} tasks.")

    for line in sys.stdin:
        user_input = line.strip()
        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit"}:
            print("Exited successfully.")
            break
        if user_input.lower() == "help":
            print_help()
            continue
        if user_input.lower() == "list":
            print(list_tasks(manager.tasks))
            continue
        if user_input.lower() == "today":
            print(list_today_items(manager.list_today_items(), manager))
            continue
        if user_input.lower().startswith("todayadd "):
            parts = user_input.split(" ", 2)
            if len(parts) < 3:
                print("Error: usage todayadd <task_id> <index>")
                continue
            task_id = parts[1].strip()
            try:
                index = int(parts[2].strip()) - 1
                manager.mark_today_subtask(task_id, index)
                print("Added to today's subtasks.")
            except ValueError:
                print("Error: index must be a number (starting at 1).")
            except ValidationError as exc:
                print(f"Error: {exc}")
            continue
        if user_input.lower().startswith("todayrm "):
            parts = user_input.split(" ", 2)
            if len(parts) < 3:
                print("Error: usage todayrm <task_id> <index>")
                continue
            task_id = parts[1].strip()
            try:
                index = int(parts[2].strip()) - 1
                manager.unmark_today_subtask(task_id, index)
                print("Removed from today's subtasks.")
            except ValueError:
                print("Error: index must be a number (starting at 1).")
            except ValidationError as exc:
                print(f"Error: {exc}")
            continue
        if user_input.lower().startswith("todaypick "):
            keyword = user_input[10:].strip()
            try:
                matches = manager.pick_today_by_keyword(keyword)
                if not matches:
                    print("No matching subtasks found.")
                else:
                    print("Picked today's TODO:")
                    print(list_today_items(matches, manager))
            except ValidationError as exc:
                print(f"Error: {exc}")
            continue
        if user_input.lower().startswith("todaydone "):
            parts = user_input.split(" ", 2)
            if len(parts) < 3:
                print("Error: usage todaydone <task_id> <index>")
                continue
            task_id = parts[1].strip()
            try:
                index = int(parts[2].strip()) - 1
                removed = manager.complete_today_subtask(task_id, index)
                print(f"Completed and removed subtask: {removed}")
            except ValueError:
                print("Error: index must be a number (starting at 1).")
            except ValidationError as exc:
                print(f"Error: {exc}")
            continue
        if user_input.lower().startswith("delete "):
            task_id = user_input[7:].strip()
            try:
                manager.delete_task(task_id)
                print("Task deleted.")
            except ValidationError as exc:
                print(f"Error: {exc}")
            continue
        if user_input.lower().startswith("subadd "):
            parts = user_input.split(" ", 2)
            if len(parts) < 3:
                print("Error: usage subadd <task_id> <subtask>")
                continue
            task_id, subtask = parts[1].strip(), parts[2].strip()
            try:
                manager.add_subtask(task_id, subtask)
                print("Subtask added.")
            except ValidationError as exc:
                print(f"Error: {exc}")
            continue
        if user_input.lower().startswith("subrm "):
            parts = user_input.split(" ", 2)
            if len(parts) < 3:
                print("Error: usage subrm <task_id> <index>")
                continue
            task_id = parts[1].strip()
            try:
                index = int(parts[2].strip()) - 1
                manager.remove_subtask(task_id, index)
                print("Subtask removed.")
            except ValueError:
                print("Error: index must be a number (starting at 1).")
            except ValidationError as exc:
                print(f"Error: {exc}")
            continue

        try:
            result = handle_input(user_input, manager)
            print(result)
        except (ParseError, ValidationError) as exc:
            print(f"Error: {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"Unknown error: {exc}")


if __name__ == "__main__":
    main()
