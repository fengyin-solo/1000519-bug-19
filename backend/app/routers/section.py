"""线路区段接口：维护线路区段，覆盖办理投用、申请限速、封闭区段等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.section import FILTER_FIELDS, STATUSES_HINT, SectionService

router = APIRouter(prefix="/api/section", tags=["线路区段"])

service = SectionService()

LIST_FIELDS = ["区段编码", "区段名称", "所属线路", "起止里程", "管辖工区", "投运日期", "限速值", "区段状态"]
STATUSES = ["在建", "已投用", "限速运行", "已封闭"]


def _build_filters(code: str | None, name: str | None, line: str | None) -> dict[str, str]:
    """把查询参数收成与页面列名一致的筛选条件；空白值不带入。"""
    raw = {"区段编码": code, "区段名称": name, "所属线路": line}
    return {field: str(value or "").strip() for field, value in raw.items() if field in FILTER_FIELDS}


def _check_status(status: str | None) -> None:
    if status and status not in STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"区段状态「{status}」不在允许范围：{STATUSES_HINT}",
        )


# 注意：/export 必须排在 /{entry_id} 之前，否则「export」会被当成 entry_id 解析而报错
@router.get("/export")
def export_entries(
    区段编码: str | None = Query(default=None, description="按区段编码包含匹配"),
    区段名称: str | None = Query(default=None, description="按区段名称包含匹配"),
    所属线路: str | None = Query(default=None, description="按所属线路包含匹配"),
    keyword: str | None = Query(default=None, description="兼容旧参数：等同区段编码"),
    status: str | None = Query(default=None, description="在建、已投用、限速运行、已封闭"),
) -> dict[str, Any]:
    """导出线路区段清单：与列表接口走同一套筛选条件，取命中行的全量、同列序数据。"""
    _check_status(status)
    filters = _build_filters(区段编码 or keyword, 区段名称, 所属线路)
    items, total, active = service.export_entries(filters=filters, status=status)
    return {
        "module": "section",
        "columns": LIST_FIELDS,
        "filters": active,
        "total": total,
        "items": items,
    }


@router.get("", response_model=PageResult[dict])
def list_entries(
    区段编码: str | None = Query(default=None, description="按区段编码包含匹配"),
    区段名称: str | None = Query(default=None, description="按区段名称包含匹配"),
    所属线路: str | None = Query(default=None, description="按所属线路包含匹配"),
    keyword: str | None = Query(default=None, description="兼容旧参数：等同区段编码"),
    status: str | None = Query(default=None, description="在建、已投用、限速运行、已封闭"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按区段编码、区段名称、所属线路与状态过滤线路区段列表；无条件时返回全量。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    _check_status(status)
    filters = _build_filters(区段编码 or keyword, 区段名称, 所属线路)
    items, total, _active = service.list_entries(filters=filters, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条线路区段明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"线路区段 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条线路区段，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="线路区段已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条线路区段执行办理投用、申请限速、封闭区段；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
