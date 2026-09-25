"""线路区段接口：维护线路区段，覆盖办理投用、申请限速、封闭区段等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.section import FILTER_FIELDS, LIST_FIELDS, STATUS_ORDER
from app.services.section import SectionService

router = APIRouter(prefix="/api/section", tags=["线路区段"])

service = SectionService()

# 查询与导出共用的筛选参数；状态不在此列，单独校验取值。
SUPPORTED_PARAMS = set(FILTER_FIELDS) | {"status", "page", "size"}


def _read_filters(request: Request) -> dict[str, Any]:
    """列表与导出共用的条件解析：未知参数、空白取值、非法状态都要说明原因。"""
    unknown = sorted(set(request.query_params) - SUPPORTED_PARAMS)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=(
                f"不支持的筛选条件：{'、'.join(unknown)}；"
                f"可用条件为 keyword（区段编码）、name（区段名称）、line（所属线路）、status（区段状态）"
            ),
        )
    status = (request.query_params.get("status") or "").strip() or None
    if status and status not in STATUS_ORDER:
        raise HTTPException(
            status_code=400,
            detail=f"区段状态「{status}」无效，可选值：{'、'.join(STATUS_ORDER)}",
        )
    return {
        "keyword": (request.query_params.get("keyword") or "").strip() or None,
        "name": (request.query_params.get("name") or "").strip() or None,
        "line": (request.query_params.get("line") or "").strip() or None,
        "status": status,
    }


@router.get("", response_model=PageResult[dict])
def list_entries(request: Request, page: int = 1, size: int = 20) -> PageResult[dict]:
    """按区段编码、区段名称、所属线路、区段状态过滤线路区段列表；没有命中时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    filters = _read_filters(request)
    items, total = service.list_entries(**filters, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries(request: Request) -> dict[str, Any]:
    """导出线路区段清单：与列表共用同一套筛选条件与取数口径，只去掉分页。"""
    filters = _read_filters(request)
    items, total = service.export_entries(**filters)
    return {
        "module": "section",
        "columns": LIST_FIELDS,
        "filters": filters,
        "total": total,
        "items": items,
    }


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
