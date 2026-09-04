"""Template router: CRUD, export, import, and sharing for video templates."""

from __future__ import annotations

import base64
import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..db import db
from ..models import Template, TemplateCreate, TemplateUpdate, new_id, now_iso

router = APIRouter(prefix="/api/templates", tags=["templates"])


class ImportTemplatePayload(BaseModel):
    # Can be a raw JSON string, a Base64 string, or a structured dict
    data: Optional[str] = None
    template: Optional[dict[str, Any]] = None


class ApplyTemplatePayload(BaseModel):
    project_id: str


@router.get("")
async def list_templates() -> list[Template]:
    return await db.list_templates()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_template(payload: TemplateCreate) -> Template:
    tpl = Template(
        id=new_id("tpl"),
        name=payload.name,
        description=payload.description,
        category=payload.category,
        cover_color=payload.cover_color or "from-indigo-600 to-purple-800",
        icon=payload.icon or "LayoutTemplate",
        is_builtin=False,
        config=payload.config,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    return await db.save_template(tpl)


@router.post("/from-project/{project_id}", status_code=status.HTTP_201_CREATED)
async def create_template_from_project(project_id: str, payload: TemplateCreate) -> Template:
    project = await db.get_project(project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "專案不存在")

    tpl = Template(
        id=new_id("tpl"),
        name=payload.name or f"{project.title or '未命名'} 模板",
        description=payload.description or f"從專案「{project.title or project.id}」產生的自訂模板",
        category=payload.category or "custom",
        cover_color=payload.cover_color or "from-indigo-600 to-purple-800",
        icon=payload.icon or "LayoutTemplate",
        is_builtin=False,
        config=payload.config,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    return await db.save_template(tpl)


@router.get("/{template_id}")
async def get_template(template_id: str) -> Template:
    tpl = await db.get_template(template_id)
    if not tpl:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到該模板")
    return tpl


@router.put("/{template_id}")
async def update_template(template_id: str, payload: TemplateUpdate) -> Template:
    tpl = await db.get_template(template_id)
    if not tpl:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到該模板")
    if tpl.is_builtin:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "內建預設模板不可直接修改，請另存為新模板")

    if payload.name is not None:
        tpl.name = payload.name
    if payload.description is not None:
        tpl.description = payload.description
    if payload.category is not None:
        tpl.category = payload.category
    if payload.cover_color is not None:
        tpl.cover_color = payload.cover_color
    if payload.icon is not None:
        tpl.icon = payload.icon
    if payload.config is not None:
        tpl.config = payload.config

    return await db.save_template(tpl)


@router.delete("/{template_id}")
async def delete_template(template_id: str) -> dict[str, bool]:
    tpl = await db.get_template(template_id)
    if not tpl:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到該模板")
    if tpl.is_builtin:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "內建預設模板不可刪除")

    deleted = await db.delete_template(template_id)
    return {"ok": deleted}


@router.get("/{template_id}/export")
async def export_template(template_id: str) -> JSONResponse:
    tpl = await db.get_template(template_id)
    if not tpl:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "找不到該模板")

    export_dict = {
        "version": "1.0",
        "type": "easyaivideo_template",
        "template": {
            "name": tpl.name,
            "description": tpl.description,
            "category": tpl.category,
            "cover_color": tpl.cover_color,
            "icon": tpl.icon,
            "config": tpl.config.model_dump(),
        },
    }
    json_bytes = json.dumps(export_dict, ensure_ascii=False).encode("utf-8")
    share_code = base64.b64encode(json_bytes).decode("utf-8")

    return JSONResponse(
        {
            "filename": f"template_{tpl.id}.json",
            "data": export_dict,
            "share_code": share_code,
        }
    )


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_template(payload: ImportTemplatePayload) -> Template:
    target_dict: Optional[dict[str, Any]] = None

    if payload.template:
        target_dict = payload.template
    elif payload.data:
        raw = payload.data.strip()
        # Try parse as JSON directly
        try:
            target_dict = json.loads(raw)
        except Exception:
            # Try parse as Base64 decoded JSON
            try:
                decoded = base64.b64decode(raw).decode("utf-8")
                target_dict = json.loads(decoded)
            except Exception as exc:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, f"無法解析分享代碼或 JSON 內容: {exc}"
                ) from exc

    if not target_dict:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "請提供有效的模板內容或分享代碼")

    # If wrapped in "template" field from export
    if "template" in target_dict and isinstance(target_dict["template"], dict):
        target_dict = target_dict["template"]

    try:
        name = target_dict.get("name", "匯入的模板")
        description = target_dict.get("description", "透過代碼或檔案匯入的自訂模板")
        category = target_dict.get("category", "imported")
        cover_color = target_dict.get("cover_color", "from-teal-600 to-indigo-900")
        icon = target_dict.get("icon", "Sparkles")
        config_data = target_dict.get("config", {})

        new_tpl = Template(
            id=new_id("tpl"),
            name=f"{name} (匯入)",
            description=description,
            category=category,
            cover_color=cover_color,
            icon=icon,
            is_builtin=False,
            config=config_data,
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        return await db.save_template(new_tpl)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"模板格式無效: {exc}") from exc
