import pytest
import warnings
from easyaivideo.models import Project, ProjectPublishSettings, ProjectUpdate
from easyaivideo.db import Database
from easyaivideo.services.project_service import ProjectService


def test_project_publish_settings_assignment_coercion():
    p = Project(id="test_p1", title="Test Video", topic="Cute Cats")
    # Assigning raw dict should automatically coerce to ProjectPublishSettings
    p.publish_settings = {
        "enabled": False,
        "auto_publish": False,
        "platforms": ["youtube"],
        "privacy": "private",
        "tags": ["Shorts", "Cat"],
    }
    assert isinstance(p.publish_settings, ProjectPublishSettings)
    assert p.publish_settings.tags == ["Shorts", "Cat"]
    assert p.publish_settings.platforms == ["youtube"]

    # Serialization should not produce any Pydantic warnings
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        dumped = p.model_dump_json()
        assert "Shorts" in dumped
        pydantic_warnings = [
            w for w in recorded if "PydanticSerializationUnexpectedValue" in str(w.message)
        ]
        assert len(pydantic_warnings) == 0


def test_project_update_publish_settings_validation():
    u = ProjectUpdate.model_validate({
        "publish_settings": {
            "enabled": True,
            "platforms": ["youtube", "tiktok"],
            "tags": ["AI", "Video"],
        }
    })
    assert isinstance(u.publish_settings, ProjectPublishSettings)
    assert u.publish_settings.enabled is True
    assert u.publish_settings.tags == ["AI", "Video"]


@pytest.mark.asyncio
async def test_project_service_patch_publish_settings():
    from unittest.mock import AsyncMock
    from easyaivideo.models import ProjectCreate

    db = AsyncMock()
    saved = {}

    async def fake_save(p):
        saved[p.id] = p
        return p

    async def fake_get(pid):
        return saved.get(pid)

    db.save_project = AsyncMock(side_effect=fake_save)
    db.get_project = AsyncMock(side_effect=fake_get)
    db.active_task = AsyncMock(return_value=None)
    svc = ProjectService(db)

    # Create project
    proj = await svc.create(ProjectCreate(title="Test", topic="Topic"))

    # Update with publish_settings
    updated = await svc.update(
        proj.id,
        ProjectUpdate(
            publish_settings=ProjectPublishSettings(
                enabled=True,
                tags=["Shorts", "Cat"],
            )
        ),
    )

    assert isinstance(updated.publish_settings, ProjectPublishSettings)
    assert updated.publish_settings.tags == ["Shorts", "Cat"]

    # Verify model_dump_json without warning
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        dumped = updated.model_dump_json()
        assert "Cat" in dumped
        pydantic_warnings = [
            w for w in recorded if "PydanticSerializationUnexpectedValue" in str(w.message)
        ]
        assert len(pydantic_warnings) == 0
