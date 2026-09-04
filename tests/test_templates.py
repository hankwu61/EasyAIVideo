import pytest
import base64
import json
from easyaivideo.models import ProjectSettings, ProjectUpdate, Template, TemplateConfig, TemplateCreate
from easyaivideo.presets import BUILTIN_TEMPLATES, TRANSITIONS, SUBTITLE_POSITIONS, FONTS
from easyaivideo.db import db
from easyaivideo.services.overlay import render_overlay
from easyaivideo.services.fonts import find_font


def test_presets_loaded():
    assert len(BUILTIN_TEMPLATES) == 6
    assert len(TRANSITIONS) >= 8
    assert len(SUBTITLE_POSITIONS) == 3
    assert len(FONTS) >= 5

    # Check 5 dimensions in builtin templates
    for tpl in BUILTIN_TEMPLATES:
        cfg = tpl["config"]
        assert "style_id" in cfg
        assert "font_family" in cfg
        assert "subtitle_position" in cfg
        assert "transition" in cfg
        assert "bgm" in cfg
        assert "bgm_volume" in cfg


def test_project_settings_fields():
    settings = ProjectSettings(
        font_family="msjh",
        font_size=28,
        subtitle_position="middle",
        transition="wipeleft",
        transition_duration=0.6,
    )
    assert settings.font_family == "msjh"
    assert settings.font_size == 28
    assert settings.subtitle_position == "middle"
    assert settings.transition == "wipeleft"
    assert settings.transition_duration == 0.6


@pytest.mark.asyncio
async def test_db_templates_crud():
    await db.init()
    templates = await db.list_templates()
    # At least 6 builtin templates
    assert len(templates) >= 6
    
    # Check cinematic builtin template
    cinematic = await db.get_template("tpl_cinematic")
    assert cinematic is not None
    assert cinematic.is_builtin is True
    assert cinematic.config.style_id == "cinematic"
    assert cinematic.config.transition == "fade"

    # Save a custom template
    custom = Template(
        id="tpl_custom_test",
        name="測試自訂模板",
        description="單元測試用",
        category="custom",
        config=TemplateConfig(
            style_id="anime",
            font_family="simhei",
            subtitle_position="top",
            transition="slideup",
            transition_duration=0.4,
            bgm=None,
            bgm_volume=0.3,
        ),
    )
    saved = await db.save_template(custom)
    assert saved.id == "tpl_custom_test"

    fetched = await db.get_template("tpl_custom_test")
    assert fetched is not None
    assert fetched.name == "測試自訂模板"
    assert fetched.config.transition == "slideup"
    assert fetched.config.subtitle_position == "top"

    # Delete custom template
    deleted = await db.delete_template("tpl_custom_test")
    assert deleted is True

    fetched_again = await db.get_template("tpl_custom_test")
    assert fetched_again is None


def test_overlay_positions(tmp_path):
    out_bottom = tmp_path / "overlay_bottom.png"
    out_middle = tmp_path / "overlay_middle.png"
    out_top = tmp_path / "overlay_top.png"

    render_overlay(out_bottom, 1080, 1920, title="標題測試", subtitle="底部字幕測試", subtitle_position="bottom")
    assert out_bottom.exists()

    render_overlay(out_middle, 1080, 1920, title=None, subtitle="中央字幕測試", subtitle_position="middle")
    assert out_middle.exists()

    render_overlay(out_top, 1080, 1920, title="標題測試", subtitle="頂部字幕測試", subtitle_position="top")
    assert out_top.exists()


def test_share_code_codec():
    payload = {
        "version": "1.0",
        "template": {
            "name": "分享測試",
            "category": "cinema",
            "config": {
                "style_id": "cinematic",
                "font_family": "msjh",
                "font_size": 24,
                "subtitle_position": "bottom",
                "transition": "fade",
                "transition_duration": 0.5,
                "bgm": None,
                "bgm_volume": 0.2,
            }
        }
    }
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    decoded = json.loads(base64.b64decode(encoded).decode("utf-8"))
    assert decoded["template"]["name"] == "分享測試"
    assert decoded["template"]["config"]["transition"] == "fade"


@pytest.mark.asyncio
async def test_templates_api_endpoints():
    import httpx
    from easyaivideo.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. list templates
        resp = await client.get("/api/templates")
        assert resp.status_code == 200
        tpls = resp.json()
        assert len(tpls) >= 6

        # 2. create template
        create_payload = {
            "name": "API 測試模板",
            "description": "測試建立",
            "category": "cinema",
            "cover_color": "from-blue-600 to-purple-800",
            "icon": "Film",
            "config": {
                "style_id": "anime",
                "style_prompt": "test prompt",
                "font_family": "msjh",
                "font_size": 26,
                "subtitle_position": "middle",
                "transition": "dissolve",
                "transition_duration": 0.5,
                "bgm": None,
                "bgm_volume": 0.2,
            },
        }
        create_resp = await client.post("/api/templates", json=create_payload)
        assert create_resp.status_code == 201
        created = create_resp.json()
        tpl_id = created["id"]
        assert created["name"] == "API 測試模板"

        # 3. export template
        export_resp = await client.get(f"/api/templates/{tpl_id}/export")
        assert export_resp.status_code == 200
        export_data = export_resp.json()
        assert "share_code" in export_data
        share_code = export_data["share_code"]

        # 4. import template via share_code
        import_resp = await client.post("/api/templates/import", json={"data": share_code})
        assert import_resp.status_code == 201
        imported = import_resp.json()
        assert "API 測試模板" in imported["name"]
        imported_id = imported["id"]

        # 5. delete templates
        del1 = await client.delete(f"/api/templates/{tpl_id}")
        assert del1.status_code == 200
        del2 = await client.delete(f"/api/templates/{imported_id}")
        assert del2.status_code == 200

