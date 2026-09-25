"""线路区段业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "section"
REQUIRED_FIELDS = ["区段编码", "区段名称", "所属线路"]
STATUS_ORDER = ["在建", "已投用", "限速运行", "已封闭"]
ACTION_RULES = {"办理投用": "已投用", "申请限速": "限速运行", "封闭区段": "已封闭"}
NEGATIVE_ACTIONS = []

# 列表/导出统一的列顺序，保证页面、导出文件与服务端取数结果逐行对齐。
LIST_FIELDS = ["区段编码", "区段名称", "所属线路", "起止里程", "管辖工区", "投运日期", "限速值", "区段状态"]

# 筛选入口（query 参数名 -> 数据字段名）：列表与导出共用，保证一套条件。
FILTER_FIELDS = {"keyword": "区段编码", "name": "区段名称", "line": "所属线路"}


class SectionService:
    def filter_rows(
        self,
        *,
        keyword: str | None = None,
        name: str | None = None,
        line: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """列表与导出共用的筛选口径：命中条件的区段才返回，顺序与存储顺序一致。"""
        rows = store.rows(MODULE)
        for param, field in FILTER_FIELDS.items():
            value = {"keyword": keyword, "name": name, "line": line}[param]
            if value:
                rows = [row for row in rows if value in str(row.get(field, ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        return rows

    def to_view(self, row: dict[str, Any]) -> dict[str, Any]:
        """按统一列序投影一条记录；id 保留给行定位与动作接口，区段状态取流程状态字段。"""
        view = {"id": row.get("id")}
        view.update({field: row.get(field) for field in LIST_FIELDS})
        view["区段状态"] = row.get("status")
        return view

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        name: str | None = None,
        line: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = self.filter_rows(keyword=keyword, name=name, line=line, status=status)
        total = len(rows)
        start = max(page - 1, 0) * size
        page_rows = [self.to_view(row) for row in rows[start:start + size]]
        return page_rows, total

    def export_entries(
        self,
        *,
        keyword: str | None = None,
        name: str | None = None,
        line: str | None = None,
        status: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """导出走与列表完全相同的筛选与投影，只是不分页，保证内容与行序一致。"""
        rows = self.filter_rows(keyword=keyword, name=name, line=line, status=status)
        return [self.to_view(row) for row in rows], len(rows)

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

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
        return entry, []

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
        return entry, f"线路区段已{action}"
