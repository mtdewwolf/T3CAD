from typing import Any, Protocol


class GeometryEngine(Protocol):
    def evaluate(self, features: list[dict[str, Any]]) -> dict[str, Any]: ...


class AnalyticPreviewEngine:
    def evaluate(self, features: list[dict[str, Any]]) -> dict[str, Any]:
        by_id = {feature["id"]: feature for feature in features}
        bodies = []
        for feature in features:
            if feature["kind"] != "extrusion":
                continue
            profile = by_id[feature["profile_id"]]
            width = profile["width"]
            height = profile["height"]
            depth = feature["depth"]
            bodies.append(
                {
                    "feature_id": feature["id"],
                    "dimensions_mm": {"width": width, "height": height, "depth": depth},
                    "bounds_mm": {"min": [0, 0, 0], "max": [width, height, depth]},
                    "volume_mm3": width * height * depth,
                }
            )
        return {
            "engine": "analytic-preview",
            "status": "preview_only",
            "solid_validation": "not_performed",
            "bodies": bodies,
            "limitations": [
                "No boundary-representation geometry is generated or validated.",
                "Rectangles lie on XY at the origin; extrusions run along positive Z.",
                "Bodies are independent; overlap, union, and assembly checks are not performed.",
                "No manufacturing or structural suitability is established.",
            ],
        }
