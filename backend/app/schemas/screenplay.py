from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class ScreenplayFormat(StrEnum):
    short_drama = "short_drama"
    film = "film"
    series_episode = "series_episode"
    stage_play = "stage_play"
    audio_drama = "audio_drama"
    general = "general"


class EventType(StrEnum):
    action = "action"
    dialogue = "dialogue"
    narration = "narration"
    stage_direction = "stage_direction"
    sound = "sound"
    transition = "transition"


class ProjectMetadata(BaseModel):
    title: str = Field(..., description="剧本标题。")
    genre: list[str] = Field(default_factory=list, description="剧本类型标签。")
    format: ScreenplayFormat = Field(
        ScreenplayFormat.short_drama,
        description="目标剧本格式。",
    )
    logline: str = Field(..., description="一句话说明故事核心冲突。")
    target_audience: str | None = Field(default=None, description="目标读者或观众。")
    tone: str | None = Field(default=None, description="整体风格。")


class SourceReference(BaseModel):
    chapter_id: str = Field(..., description="来源章节 ID。")
    range_hint: str = Field(..., description="来源内容范围提示。")
    usage: Literal["adapted", "merged", "compressed", "omitted_context", "inferred"] = Field(
        ...,
        description="该来源在剧本场景中的使用方式。",
    )


class Character(BaseModel):
    id: str = Field(..., description="稳定人物 ID。")
    name: str = Field(..., description="人物显示名称。")
    role: str = Field(..., description="人物在故事中的角色功能。")
    description: str = Field(..., description="人物简述。")
    goals: list[str] = Field(default_factory=list, description="人物目标。")
    conflicts: list[str] = Field(default_factory=list, description="人物内外部冲突。")
    speech_style: str | None = Field(default=None, description="人物说话风格。")
    arc: str | None = Field(default=None, description="人物弧光。")


class Location(BaseModel):
    id: str = Field(..., description="稳定地点 ID。")
    name: str = Field(..., description="地点名称。")
    description: str = Field(..., description="地点描述。")
    visual_motifs: list[str] = Field(default_factory=list, description="地点视觉母题。")


class SceneSetting(BaseModel):
    location_id: str = Field(..., description="引用的地点 ID。")
    time_of_day: str | None = Field(default=None, description="场景发生时段。")
    atmosphere: str | None = Field(default=None, description="场景氛围。")


class ScriptEvent(BaseModel):
    id: str = Field(..., description="稳定事件 ID，用于局部编辑和校验定位。")
    type: EventType = Field(..., description="事件类型。")
    content: str = Field(..., description="事件正文。")
    character_id: str | None = Field(default=None, description="对白事件引用的人物 ID。")
    emotion: str | None = Field(default=None, description="可选的情绪提示。")
    subtext: str | None = Field(default=None, description="可选的潜台词说明。")
    beat: str | None = Field(default=None, description="可选的戏剧节拍说明。")
    duration_hint: str | None = Field(default=None, description="可选的时长提示。")


class AdaptationNotes(BaseModel):
    intent: str = Field(..., description="本场改编意图。")
    omitted_or_changed: list[str] = Field(default_factory=list, description="删改说明。")
    risks: list[str] = Field(default_factory=list, description="可能损失或需要复核的内容。")


class Scene(BaseModel):
    id: str = Field(..., description="稳定场景 ID。")
    title: str = Field(..., description="场景标题。")
    source_refs: list[SourceReference] = Field(..., description="场景来源引用。")
    setting: SceneSetting = Field(..., description="场景设定。")
    dramatic_purpose: str = Field(..., description="该场景的戏剧目的。")
    conflict: str = Field(..., description="该场景的核心冲突。")
    events: list[ScriptEvent] = Field(..., description="结构化剧本事件列表。")
    turning_point: str | None = Field(default=None, description="可选的场景转折点。")
    emotional_shift: str | None = Field(default=None, description="可选的情绪变化。")
    adaptation_notes: AdaptationNotes | None = Field(default=None, description="改编说明。")


class ScreenplayYaml(BaseModel):
    schema_version: str = Field(..., description="剧本 YAML Schema 版本。")
    project: ProjectMetadata = Field(..., description="剧本项目信息。")
    characters: list[Character] = Field(..., description="全局人物表。")
    locations: list[Location] = Field(..., description="全局地点表。")
    scenes: list[Scene] = Field(..., description="剧本场景列表。")

