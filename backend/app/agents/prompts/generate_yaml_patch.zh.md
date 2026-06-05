请根据用户修改意图和当前 YAML，生成可验证的 patch operations。

每个 operation 必须包含 type、target_path、reason 和 payload。reason 必须使用中文，payload 必须只包含必要改动。

优先使用局部操作，不要为了小改动 replace_script。

当前可直接应用的操作：

- create_script / replace_script：创建或替换整份剧本。仅在用户明确要求整体重建、整体改写时使用，payload.script 必须是完整 YAML 对象。
- patch_project：修改 project 字段。target_path 固定为 project，payload 直接放要更新的字段。
- upsert_character：新增或更新人物。target_path 为 characters.<character_id>，payload.character 是完整或局部人物对象。
- delete_character：删除人物。target_path 为 characters.<character_id>。
- upsert_location：新增或更新地点。target_path 为 locations.<location_id>，payload.location 是完整或局部地点对象。
- delete_location：删除地点。target_path 为 locations.<location_id>。
- insert_scene：新增场景。target_path 为 scenes 或 scenes.<insert_after_scene_id>，payload.scene 是完整场景对象。
- replace_scene：替换场景。target_path 为 scenes.<scene_id>，payload.scene 是完整场景对象。
- patch_scene：局部修改场景。target_path 为 scenes.<scene_id>，payload 放要更新的字段。
- delete_scene：删除场景。target_path 为 scenes.<scene_id>。
- reorder_scenes：重排场景。target_path 为 scenes，payload.ordered_scene_ids 必须包含所有现有 scene id。
- insert_event：新增事件。target_path 为 scenes.<scene_id>.events 或 scenes.<scene_id>.events.<insert_after_event_id>，payload.event 是完整事件对象。
- replace_event：替换事件。target_path 为 scenes.<scene_id>.events.<event_id>，payload.event 是完整事件对象。
- patch_event：局部修改事件。target_path 为 scenes.<scene_id>.events.<event_id>，payload 放要更新的字段。
- delete_event：删除事件。target_path 为 scenes.<scene_id>.events.<event_id>。
- reorder_events：重排事件。target_path 为 scenes.<scene_id>.events，payload.ordered_event_ids 必须包含该场景所有 event id。
- patch_adaptation_notes：修改改编说明。target_path 为 scenes.<scene_id>.adaptation_notes，payload 放 intent、omitted_or_changed、risks 等字段。

当前不要输出 merge_characters、upsert_act、delete_act、repair_validation_errors；这些操作需要专门工具或当前 Schema 暂不支持。

如果用户请求会导致引用断裂，例如删除正在被对白引用的人物，请优先生成能保持引用完整的操作，或用中文 reason 说明需要同步修改哪些引用。
