"""Explicit asset snapshots and retained scene media versions."""
from ..models import BoundAsset, MediaVersion
from . import storage


def catalog(project):
    assets = list(project.assets)
    assets += [BoundAsset(id=f"character:{c.id or c.name}", kind="character", name=c.name,
                         description=c.appearance or c.description, image_path=c.image_path)
               for c in project.characters if c.name]
    assets += [BoundAsset(id=f"location:{c.name}", kind="location", name=c.name,
                         description=c.description) for c in project.locations if c.name]
    return assets


def remember(scene, kind):
    if kind not in ("image", "end_image", "video"):
        return
    path = getattr(scene, f"{kind}_path")
    if path and storage.abs_path(path).is_file() and not any(v.path == path for v in scene.media_history):
        scene.media_history.append(MediaVersion(kind=kind, path=path))


def binding_prompt(scene):
    if not scene.asset_bindings:
        return staging_prompt(scene)
    return staging_prompt(scene) + "\nBound assets:\n" + "\n".join(
        f"{a.kind}: {a.name}. {a.description}" for a in scene.asset_bindings)


def binding_refs(scene):
    return [storage.abs_path(a.image_path) for a in scene.asset_bindings
            if a.image_path and storage.abs_path(a.image_path).is_file()]


def staging_prompt(scene):
    if not scene.stage_positions:
        return ""
    return (
        "\nScene blocking (top-down planning coordinates, not an overhead camera instruction): "
        "x=0 left, x=100 right; y=0 far/back, y=100 near/front. "
        "Facing degrees clockwise: 0 toward back, 90 right, 180 front, 270 left. "
        "Place these characters at the specified starting positions; preserve their relative spacing "
        "and identities, then follow the described action. Render a single cinematic shot, never the diagram.\n"
        + "\n".join(f"{p.name}: x={p.x:g}%, y={p.y:g}%, facing={p.facing:g} degrees."
                    for p in scene.stage_positions)
    )
