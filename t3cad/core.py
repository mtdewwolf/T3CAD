import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any

from .geometry import AnalyticPreviewEngine, GeometryEngine


class CadError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def fields(value: Any, required: set[str], optional: set[str] | None = None) -> dict:
    if not isinstance(value, dict):
        raise CadError("invalid_input", "Expected a JSON object.")
    missing = required - value.keys()
    unknown = value.keys() - required - (optional or set())
    if missing or unknown:
        raise CadError(
            "invalid_input",
            f"Missing fields: {sorted(missing)}; unknown fields: {sorted(unknown)}.",
        )
    return value


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", value):
        raise CadError("invalid_input", "IDs must start with a letter and contain 1–64 letters, digits, _ or -.")
    return value


def dimension(value: Any) -> float:
    if type(value) not in (int, float):
        raise CadError("invalid_input", "Dimensions must be finite, positive numbers in millimeters.")
    try:
        converted = float(value)
    except (OverflowError, ValueError):
        raise CadError("invalid_input", "Dimension is outside the supported numeric range.") from None
    if not math.isfinite(converted) or not 0 < converted <= 1_000_000:
        raise CadError("invalid_input", "Dimensions must be greater than 0 and at most 1,000,000 mm.")
    return converted


def revision_number(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise CadError("invalid_input", "Revision must be a non-negative integer.")
    return value


def validate_features(features: Any) -> None:
    if not isinstance(features, list):
        raise CadError("invalid_input", "Features must be an array.")
    previous = {}
    for feature in features:
        if not isinstance(feature, dict):
            raise CadError("invalid_input", "Each feature must be an object.")
        kind = feature.get("kind")
        if kind == "rectangle":
            fields(feature, {"id", "kind", "width", "height"})
            dimension(feature["width"])
            dimension(feature["height"])
        elif kind == "extrusion":
            fields(feature, {"id", "kind", "profile_id", "depth"})
            dimension(feature["depth"])
            profile_id = identifier(feature["profile_id"])
            if previous.get(profile_id, {}).get("kind") != "rectangle":
                raise CadError("invalid_reference", "An extrusion must reference an earlier rectangle.")
        else:
            raise CadError("unsupported_feature", f"Unsupported feature kind: {kind!r}.")
        feature_id = identifier(feature["id"])
        if feature_id in previous:
            raise CadError("duplicate_id", f"Feature {feature_id!r} already exists.")
        previous[feature_id] = feature


@dataclass
class Document:
    document_id: str
    revision: int = 0
    features: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        identifier(self.document_id)
        revision_number(self.revision)
        validate_features(self.features)

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(
            {
                "schema_version": 1,
                "document_id": self.document_id,
                "units": "mm",
                "revision": self.revision,
                "features": self.features,
                "history": self.history,
            }
        )

    @classmethod
    def from_dict(cls, value: Any) -> "Document":
        fields(value, {"schema_version", "document_id", "units", "revision", "features", "history"})
        if type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["units"] != "mm":
            raise CadError("unsupported_document", "Only schema version 1 and millimeter units are supported.")
        document = cls(value["document_id"], value["revision"], copy.deepcopy(value["features"]))
        history = value["history"]
        if not isinstance(history, list) or len(history) != document.revision:
            raise CadError("invalid_document", "History must contain one entry per revision.")
        request_ids = set()
        replay = cls(document.document_id)
        replay_harness = Harness()
        for expected_revision, entry in enumerate(history):
            fields(entry, {"revision", "request", "response"})
            revision_number(entry["revision"])
            request = entry["request"]
            replay, response = replay_harness.apply(replay, request)
            request_id = request["request_id"]
            if (
                request_id in request_ids
                or entry["revision"] != expected_revision + 1
                or replay_harness._digest(entry["response"]) != replay_harness._digest(response)
            ):
                raise CadError("invalid_document", "History is inconsistent with its recorded requests.")
            request_ids.add(request_id)
        if replay.features != document.features:
            raise CadError("invalid_document", "Features do not match the recorded command history.")
        document.history = copy.deepcopy(history)
        return document


class Harness:
    def __init__(self, engine: GeometryEngine | None = None):
        self.engine = engine if engine is not None else AnalyticPreviewEngine()

    def capabilities(self) -> dict[str, Any]:
        return {
            "protocol_version": 1,
            "units": "mm",
            "operations": {
                "sketch.create_rectangle": ["feature_id", "width", "height"],
                "feature.extrude": ["feature_id", "profile_id", "depth"],
                "feature.set_parameter": ["feature_id", "parameter", "value"],
            },
            "reads": ["inspect"],
            "atomic_batches": True,
            "optimistic_concurrency": True,
            "persisted_idempotency": True,
            "geometry": "analytic-preview",
            "solid_modeling": False,
            "export": False,
        }

    def inspect(self, document: Document) -> dict[str, Any]:
        validate_features(document.features)
        return {
            "document_id": document.document_id,
            "revision": document.revision,
            "units": "mm",
            "features": copy.deepcopy(document.features),
            "validation": {
                "document_structure": "passed",
                "geometry": self.engine.evaluate(copy.deepcopy(document.features)),
            },
        }

    def apply(self, document: Document, request: Any) -> tuple[Document, dict[str, Any]]:
        fields(request, {"request_id", "document_id", "expected_revision", "actor", "commands"})
        request_id = identifier(request["request_id"])
        identifier(request["document_id"])
        identifier(request["actor"])
        revision_number(request["expected_revision"])
        if request["document_id"] != document.document_id:
            raise CadError("document_mismatch", "The request targets a different document.")
        commands = request["commands"]
        if not isinstance(commands, list) or not 1 <= len(commands) <= 100:
            raise CadError("invalid_input", "A batch must contain between 1 and 100 commands.")
        digest = self._digest(request)
        for entry in document.history:
            if entry["request"]["request_id"] == request_id:
                if self._digest(entry["request"]) != digest:
                    raise CadError("request_id_conflict", "This request ID was already used with a different payload.")
                response = copy.deepcopy(entry["response"])
                response["replayed"] = True
                return copy.deepcopy(document), response
        if request["expected_revision"] != document.revision:
            raise CadError("revision_conflict", f"Expected revision {request['expected_revision']}; current revision is {document.revision}.")
        candidate = copy.deepcopy(document)
        for command in commands:
            self._execute(candidate, command)
            validate_features(candidate.features)
        candidate.revision += 1
        response = {
            "request_id": request_id,
            "document_id": candidate.document_id,
            "revision": candidate.revision,
            "replayed": False,
            "report": self.inspect(candidate),
        }
        candidate.history.append(
            {"revision": candidate.revision, "request": copy.deepcopy(request), "response": copy.deepcopy(response)}
        )
        return candidate, response

    @staticmethod
    def _digest(request: dict[str, Any]) -> str:
        try:
            serialized = json.dumps(request, sort_keys=True, allow_nan=False, separators=(",", ":"))
        except (TypeError, ValueError, OverflowError):
            raise CadError("invalid_input", "Requests must contain only finite JSON values.") from None
        return hashlib.sha256(serialized.encode()).hexdigest()

    def _execute(self, document: Document, command: Any) -> None:
        if not isinstance(command, dict) or not isinstance(command.get("op"), str):
            raise CadError("invalid_input", "Each command must have a string op field.")
        operation = command["op"]
        specifications = self.capabilities()["operations"]
        if operation not in specifications:
            raise CadError("unsupported_operation", f"Unsupported operation: {operation!r}.")
        fields(command, {"op", *specifications[operation]})
        feature_id = identifier(command["feature_id"])
        if operation == "sketch.create_rectangle":
            document.features.append(
                {"id": feature_id, "kind": "rectangle", "width": dimension(command["width"]), "height": dimension(command["height"])}
            )
        elif operation == "feature.extrude":
            document.features.append(
                {"id": feature_id, "kind": "extrusion", "profile_id": identifier(command["profile_id"]), "depth": dimension(command["depth"])}
            )
        elif operation == "feature.set_parameter":
            feature = next((item for item in document.features if item["id"] == feature_id), None)
            if feature is None:
                raise CadError("feature_not_found", f"Feature {feature_id!r} does not exist.")
            allowed = {"width", "height"} if feature["kind"] == "rectangle" else {"depth"}
            parameter = command["parameter"]
            if not isinstance(parameter, str) or parameter not in allowed:
                raise CadError("invalid_parameter", f"Editable parameters are {sorted(allowed)}.")
            feature[parameter] = dimension(command["value"])
