"""线路区段业务规则：状态流转、字段校验与筛选口径都收在这里。

列表与导出共用同一套筛选/排序口径（query_rows），保证页面看到的行和导出的行一致。
"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "section"
REQUIRED_FIELDS = ["区段编码", "区段名称", "所属线路"]
# 页面/导出列：顺序即列序，保证列表与导出不错位
LIST_FIELDS = ["区段编码", "区段名称", "所属线路", "起止里程", "管辖工区", "投运日期", "限速值", "区段状态"]
# 允许参与筛选的列
FILTER_FIELDS = ["区段编码", "区段名称", "所属线路"]
STATUS_ORDER = ["在建", "已投用", "限速运行", "已封闭"]
STATUSES_HINT = "、".join(STATUS_ORDER)
ACTION_RULES = {"办理投用": "已投用", "申请限速": "限速运行", "封闭区段": "已封闭"}
NEGATIVE_ACTIONS = []


class SectionService:
    def query_rows(
        self,
        *,
        filters: dict[str, str] | None = None,
        status: str | None = None,
        page: int = 1,
        size: int | None = None,
    ) -> tuple[list[dict[str, Any]], int, list[str]]:
        """统一筛选入口：返回当前页行、命中总数、实际生效的筛选字段名。

        filters 的 key 为中文列名（区段编码/区段名称/所属线路），多个条件之间是「与」，
        单个条件按包含匹配；空白值忽略。size 为 None 时返回全部命中行（导出用）。
        """
        filters = filters or {}
        active: list[str] = []
        rows = store.rows(MODULE)
        for field in FILTER_FIELDS:
            value = str(filters.get(field) or "").strip()
            if not value:
                continue
            active.append(field)
            rows = [row for row in rows if value in str(row.get(field, ""))]
        if status:
            rows = [row for row in rows if str(row.get("status", "")) == status]
        total = len(rows)
        if size is None:
            return [self._present(row) for row in rows], total, active
        start = max(page - 1, 0) * size
        page_rows = [self._present(row) for row in rows[start:start + size]]
        return page_rows, total, active

    def list_entries(
        self,
        *,
        filters: dict[str, str] | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, list[str]]:
        return self.query_rows(filters=filters, status=status, page=page, size=size)

    def export_entries(
        self,
        *,
        filters: dict[str, str] | None = None,
        status: str | None = None,
    ) -> tuple[list[dict[str, Any]], int, list[str]]:
        return self.query_rows(filters=filters, status=status, page=1, size=None)

    def _present(self, row: dict[str, Any]) -> dict[str, Any]:
        """按列序输出，区段状态以真实状态为准，和投用/封闭动作保持同步。"""
        item: dict[str, Any] = {"id": row.get("id")}
        for field in LIST_FIELDS:
            if field == "区段状态":
                item[field] = row.get("status")
            else:
                item[field] = row.get(field)
        return item

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return self._present(row) if row is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._present(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"线路区段 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于线路区段可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return self._present(entry), f"线路区段已{action}"
