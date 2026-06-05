from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

import yaml

from app.schemas.yaml_patch import YamlPatchOperation


class YamlPatchError(Exception):
    """Base error for screenplay YAML patch application."""


class UnsupportedYamlOperationError(YamlPatchError):
    """Raised when an operation type is unknown or not implemented for the current schema."""


class YamlPatchPayloadError(YamlPatchError):
    """Raised when an operation payload is missing required structured data."""


class YamlPatchTargetError(YamlPatchError):
    """Raised when an operation target path cannot be resolved."""


class YamlPatchNoChangeError(YamlPatchError):
    """Raised when applying operations does not change the YAML document."""


class YamlPatchApplier:
    """Apply structured create/edit operations to a ScreenplayYaml document."""

    def apply(self, current_yaml: str, operations: list[YamlPatchOperation]) -> str:
        raw = yaml.safe_load(current_yaml)
        if not isinstance(raw, dict):
            raise YamlPatchPayloadError("Current script YAML root must be a mapping.")
        if not operations:
            raise YamlPatchNoChangeError("YAML patch plan has no operations.")

        original = deepcopy(raw)
        document = cast(dict[str, Any], raw)
        for operation in operations:
            document = self.apply_operation(document, operation)
        if document == original:
            raise YamlPatchNoChangeError("YAML patch operations did not change the document.")
        return yaml.safe_dump(document, allow_unicode=True, sort_keys=False)

    def apply_operation(
        self,
        document: dict[str, Any],
        operation: YamlPatchOperation,
    ) -> dict[str, Any]:
        match operation.type:
            case "create_script" | "replace_script":
                return self._replace_script(operation)
            case "patch_project":
                return self._patch_project(document, operation)
            case "upsert_character":
                return self._upsert_collection_item(
                    document,
                    operation,
                    group="characters",
                    payload_key="character",
                    item_label="character",
                )
            case "delete_character":
                return self._delete_collection_item(document, operation, "characters", "character")
            case "upsert_location":
                return self._upsert_collection_item(
                    document,
                    operation,
                    group="locations",
                    payload_key="location",
                    item_label="location",
                )
            case "delete_location":
                return self._delete_collection_item(document, operation, "locations", "location")
            case "insert_scene":
                return self._insert_scene(document, operation)
            case "replace_scene":
                return self._replace_collection_item(document, operation, "scenes", "scene")
            case "patch_scene":
                return self._patch_collection_item(document, operation, "scenes", "scene")
            case "delete_scene":
                return self._delete_collection_item(document, operation, "scenes", "scene")
            case "reorder_scenes":
                return self._reorder_collection(
                    document,
                    operation,
                    group="scenes",
                    id_payload_keys=("ordered_scene_ids", "scene_ids", "ids"),
                )
            case "insert_event" | "replace_event" | "patch_event" | "delete_event":
                return self._apply_event_operation(document, operation)
            case "reorder_events":
                return self._reorder_events(document, operation)
            case "patch_adaptation_notes":
                return self._patch_adaptation_notes(document, operation)
            case "merge_characters" | "upsert_act" | "delete_act" | "repair_validation_errors":
                raise UnsupportedYamlOperationError(
                    f"Unsupported YAML operation for current schema: {operation.type}"
                )
            case _:
                raise UnsupportedYamlOperationError(
                    f"Unknown YAML operation type: {operation.type}"
                )

    def _replace_script(self, operation: YamlPatchOperation) -> dict[str, Any]:
        return deepcopy(self._payload_object(operation, "script"))

    def _patch_project(
        self,
        document: dict[str, Any],
        operation: YamlPatchOperation,
    ) -> dict[str, Any]:
        if operation.target_path != "project":
            raise YamlPatchTargetError(
                f"patch_project target_path must be project: {operation.target_path}"
            )
        project = document.get("project")
        if not isinstance(project, dict):
            raise YamlPatchTargetError("project is not a mapping.")
        patch = self._payload_patch(operation, nested_key="project")
        self._deep_update(cast(dict[str, Any], project), patch)
        return document

    def _upsert_collection_item(
        self,
        document: dict[str, Any],
        operation: YamlPatchOperation,
        group: str,
        payload_key: str,
        item_label: str,
    ) -> dict[str, Any]:
        collection = self._collection(document, group)
        item = deepcopy(self._payload_object(operation, payload_key, allow_direct_payload=True))
        target_id = self._parse_optional_item_path(operation.target_path, group)
        item_id = item.get("id") or target_id
        if not isinstance(item_id, str) or not item_id:
            raise YamlPatchPayloadError(f"{item_label} payload must include an id.")
        if target_id is not None and item.get("id") not in {None, target_id}:
            raise YamlPatchPayloadError(
                f"{item_label} payload id must match target path: {target_id}"
            )
        item["id"] = item_id

        index = self._find_index(collection, item_id)
        if index is None:
            collection.append(item)
        else:
            self._deep_update(collection[index], item)
        return document

    def _insert_scene(
        self,
        document: dict[str, Any],
        operation: YamlPatchOperation,
    ) -> dict[str, Any]:
        scenes = self._collection(document, "scenes")
        scene = deepcopy(self._payload_object(operation, "scene"))
        scene_id = scene.get("id")
        if not isinstance(scene_id, str) or not scene_id:
            raise YamlPatchPayloadError("insert_scene payload.scene must include an id.")
        if self._find_index(scenes, scene_id) is not None:
            raise YamlPatchTargetError(f"scene already exists: {scene_id}")

        insert_index = self._insert_index(
            collection=scenes,
            operation=operation,
            group="scenes",
            after_payload_key="insert_after_scene_id",
        )
        scenes.insert(insert_index, scene)
        return document

    def _replace_collection_item(
        self,
        document: dict[str, Any],
        operation: YamlPatchOperation,
        group: str,
        payload_key: str,
    ) -> dict[str, Any]:
        collection = self._collection(document, group)
        item_id = self._parse_item_path(operation.target_path, group)
        index = self._require_index(collection, item_id, payload_key)
        replacement = deepcopy(self._payload_object(operation, payload_key))
        replacement_id = replacement.get("id")
        if replacement_id is None:
            replacement["id"] = item_id
        elif replacement_id != item_id:
            raise YamlPatchPayloadError(
                f"{payload_key} replacement id must match target path: {item_id}"
            )
        collection[index] = replacement
        return document

    def _patch_collection_item(
        self,
        document: dict[str, Any],
        operation: YamlPatchOperation,
        group: str,
        item_label: str,
    ) -> dict[str, Any]:
        collection = self._collection(document, group)
        item_id = self._parse_item_path(operation.target_path, group)
        item = collection[self._require_index(collection, item_id, item_label)]
        patch = self._payload_patch(operation, nested_key=item_label)
        self._deep_update(item, patch)
        return document

    def _delete_collection_item(
        self,
        document: dict[str, Any],
        operation: YamlPatchOperation,
        group: str,
        item_label: str,
    ) -> dict[str, Any]:
        collection = self._collection(document, group)
        item_id = self._parse_item_path(operation.target_path, group)
        index = self._require_index(collection, item_id, item_label)
        collection.pop(index)
        return document

    def _apply_event_operation(
        self,
        document: dict[str, Any],
        operation: YamlPatchOperation,
    ) -> dict[str, Any]:
        if operation.type == "insert_event":
            scene_id, after_event_id = self._parse_event_collection_path(operation.target_path)
            scene = self._scene(document, scene_id)
            events = self._event_collection(scene)
            event = deepcopy(self._payload_object(operation, "event"))
            event_id = event.get("id")
            if not isinstance(event_id, str) or not event_id:
                raise YamlPatchPayloadError("insert_event payload.event must include an id.")
            if self._find_index(events, event_id) is not None:
                raise YamlPatchTargetError(f"event already exists: {event_id}")

            after_from_payload = operation.payload.get("insert_after_event_id")
            if isinstance(after_from_payload, str):
                after_event_id = after_from_payload
            index = len(events)
            if after_event_id is not None:
                index = self._require_index(events, after_event_id, "event") + 1
            events.insert(index, event)
            return document

        scene_id, event_id = self._parse_event_path(operation.target_path)
        scene = self._scene(document, scene_id)
        events = self._event_collection(scene)
        index = self._require_index(events, event_id, "event")
        if operation.type == "replace_event":
            replacement = deepcopy(self._payload_object(operation, "event"))
            replacement_id = replacement.get("id")
            if replacement_id is None:
                replacement["id"] = event_id
            elif replacement_id != event_id:
                raise YamlPatchPayloadError(
                    f"event replacement id must match target path: {event_id}"
                )
            events[index] = replacement
        elif operation.type == "patch_event":
            patch = self._payload_patch(operation, nested_key="event")
            self._deep_update(events[index], patch)
        elif operation.type == "delete_event":
            events.pop(index)
        return document

    def _reorder_events(
        self,
        document: dict[str, Any],
        operation: YamlPatchOperation,
    ) -> dict[str, Any]:
        scene_id, _ = self._parse_event_collection_path(operation.target_path)
        scene = self._scene(document, scene_id)
        events = self._event_collection(scene)
        scene["events"] = self._reordered_items(
            events,
            self._payload_ids(operation, ("ordered_event_ids", "event_ids", "ids")),
            label="event",
        )
        return document

    def _reorder_collection(
        self,
        document: dict[str, Any],
        operation: YamlPatchOperation,
        group: str,
        id_payload_keys: tuple[str, ...],
    ) -> dict[str, Any]:
        collection = self._collection(document, group)
        document[group] = self._reordered_items(
            collection,
            self._payload_ids(operation, id_payload_keys),
            label=group.removesuffix("s"),
        )
        return document

    def _patch_adaptation_notes(
        self,
        document: dict[str, Any],
        operation: YamlPatchOperation,
    ) -> dict[str, Any]:
        parts = operation.target_path.split(".")
        if len(parts) != 3 or parts[0] != "scenes" or parts[2] != "adaptation_notes":
            raise YamlPatchTargetError(
                f"patch_adaptation_notes target must be scenes.<id>.adaptation_notes: "
                f"{operation.target_path}"
            )
        scene = self._scene(document, parts[1])
        notes = scene.get("adaptation_notes")
        if not isinstance(notes, dict):
            notes = {}
            scene["adaptation_notes"] = notes
        patch = self._payload_patch(operation, nested_key="adaptation_notes")
        self._deep_update(cast(dict[str, Any], notes), patch)
        return document

    def _payload_object(
        self,
        operation: YamlPatchOperation,
        key: str,
        allow_direct_payload: bool = False,
    ) -> dict[str, Any]:
        value = operation.payload.get(key)
        if value is None and allow_direct_payload:
            value = operation.payload
        if not isinstance(value, dict) or not value:
            raise YamlPatchPayloadError(f"{operation.type} payload.{key} must be an object.")
        return cast(dict[str, Any], value)

    def _payload_patch(
        self,
        operation: YamlPatchOperation,
        nested_key: str,
    ) -> dict[str, Any]:
        value = operation.payload.get(nested_key)
        if value is None:
            value = operation.payload
        if not isinstance(value, dict) or not value:
            raise YamlPatchPayloadError(f"{operation.type} payload must contain a patch object.")
        return cast(dict[str, Any], value)

    def _payload_ids(
        self,
        operation: YamlPatchOperation,
        keys: tuple[str, ...],
    ) -> list[str]:
        value: Any = None
        for key in keys:
            value = operation.payload.get(key)
            if value is not None:
                break
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            joined = ", ".join(keys)
            raise YamlPatchPayloadError(f"{operation.type} payload must include one of: {joined}.")
        return cast(list[str], value)

    def _insert_index(
        self,
        collection: list[dict[str, Any]],
        operation: YamlPatchOperation,
        group: str,
        after_payload_key: str,
    ) -> int:
        raw_index = operation.payload.get("index")
        if isinstance(raw_index, int):
            if raw_index < 0 or raw_index > len(collection):
                raise YamlPatchPayloadError(f"insert index out of range: {raw_index}")
            return raw_index

        after_id = operation.payload.get(after_payload_key)
        if not isinstance(after_id, str):
            after_id = self._parse_optional_item_path(operation.target_path, group)
        if after_id is None:
            return len(collection)
        return self._require_index(collection, after_id, group.removesuffix("s")) + 1

    def _collection(self, document: dict[str, Any], group: str) -> list[dict[str, Any]]:
        value = document.setdefault(group, [])
        if not isinstance(value, list):
            raise YamlPatchTargetError(f"{group} must be a list.")
        if not all(isinstance(item, dict) for item in value):
            raise YamlPatchTargetError(f"{group} must only contain objects.")
        return cast(list[dict[str, Any]], value)

    def _scene(self, document: dict[str, Any], scene_id: str) -> dict[str, Any]:
        scenes = self._collection(document, "scenes")
        return scenes[self._require_index(scenes, scene_id, "scene")]

    def _event_collection(self, scene: dict[str, Any]) -> list[dict[str, Any]]:
        value = scene.setdefault("events", [])
        if not isinstance(value, list):
            raise YamlPatchTargetError("scene.events must be a list.")
        if not all(isinstance(item, dict) for item in value):
            raise YamlPatchTargetError("scene.events must only contain objects.")
        return cast(list[dict[str, Any]], value)

    def _reordered_items(
        self,
        items: list[dict[str, Any]],
        ordered_ids: list[str],
        label: str,
    ) -> list[dict[str, Any]]:
        existing_ids = [item.get("id") for item in items]
        if not all(isinstance(item_id, str) for item_id in existing_ids):
            raise YamlPatchTargetError(f"all {label}s must have stable ids before reorder.")
        if set(ordered_ids) != set(existing_ids) or len(ordered_ids) != len(existing_ids):
            raise YamlPatchPayloadError(
                f"reorder_{label}s must include every existing {label} id exactly once."
            )
        by_id = {cast(str, item["id"]): item for item in items}
        return [by_id[item_id] for item_id in ordered_ids]

    def _parse_item_path(self, target_path: str, group: str) -> str:
        item_id = self._parse_optional_item_path(target_path, group)
        if item_id is None:
            raise YamlPatchTargetError(f"target path must be {group}.<id>: {target_path}")
        return item_id

    def _parse_optional_item_path(self, target_path: str, group: str) -> str | None:
        if target_path == group:
            return None
        parts = target_path.split(".")
        if len(parts) == 2 and parts[0] == group and parts[1]:
            return parts[1]
        raise YamlPatchTargetError(f"unsupported target path for {group}: {target_path}")

    def _parse_event_path(self, target_path: str) -> tuple[str, str]:
        parts = target_path.split(".")
        if len(parts) != 4 or parts[0] != "scenes" or parts[2] != "events":
            raise YamlPatchTargetError(
                f"target path must be scenes.<id>.events.<id>: {target_path}"
            )
        return parts[1], parts[3]

    def _parse_event_collection_path(self, target_path: str) -> tuple[str, str | None]:
        parts = target_path.split(".")
        if len(parts) == 3 and parts[0] == "scenes" and parts[2] == "events":
            return parts[1], None
        if len(parts) == 4 and parts[0] == "scenes" and parts[2] == "events":
            return parts[1], parts[3]
        raise YamlPatchTargetError(
            f"target path must be scenes.<id>.events or scenes.<id>.events.<id>: {target_path}"
        )

    def _find_index(self, items: list[dict[str, Any]], item_id: str) -> int | None:
        for index, item in enumerate(items):
            if item.get("id") == item_id:
                return index
        return None

    def _require_index(self, items: list[dict[str, Any]], item_id: str, label: str) -> int:
        index = self._find_index(items, item_id)
        if index is None:
            raise YamlPatchTargetError(f"{label} not found: {item_id}")
        return index

    def _deep_update(self, target: dict[str, Any], patch: dict[str, Any]) -> None:
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                self._deep_update(cast(dict[str, Any], target[key]), value)
            else:
                target[key] = value
