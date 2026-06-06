import {
  Alert,
  Button,
  Card,
  Collapse,
  Empty,
  Flex,
  Form,
  Input,
  Select,
  Space,
  Tag,
  Typography,
} from 'antd'
import { InfoCircleOutlined, PlusOutlined } from '@ant-design/icons'

const { Paragraph, Text } = Typography
const { TextArea } = Input

export type ScreenplayDraft = {
  schema_version?: string
  project?: ProjectDraft
  characters?: CharacterDraft[]
  locations?: LocationDraft[]
  scenes?: SceneDraft[]
  [key: string]: unknown
}

type ProjectDraft = {
  title?: string
  genre?: string[]
  format?: string
  logline?: string
  target_audience?: string | null
  tone?: string | null
}

type CharacterDraft = {
  id?: string
  name?: string
  role?: string
  description?: string
  goals?: string[]
  conflicts?: string[]
  speech_style?: string | null
  arc?: string | null
}

type LocationDraft = {
  id?: string
  name?: string
  description?: string
  visual_motifs?: string[]
}

type SceneSettingDraft = {
  location_id?: string
  time_of_day?: string | null
  atmosphere?: string | null
}

type ScriptEventDraft = {
  id?: string
  type?: string
  content?: string
  character_id?: string | null
  emotion?: string | null
  subtext?: string | null
  beat?: string | null
  duration_hint?: string | null
}

type AdaptationNotesDraft = {
  intent?: string
  omitted_or_changed?: string[]
  risks?: string[]
}

type SceneDraft = {
  id?: string
  title?: string
  setting?: SceneSettingDraft
  dramatic_purpose?: string
  conflict?: string
  events?: ScriptEventDraft[]
  turning_point?: string | null
  emotional_shift?: string | null
  adaptation_notes?: AdaptationNotesDraft | null
}

type ScriptVisualEditorProps = {
  draft: ScreenplayDraft
  onDraftChange: (draft: ScreenplayDraft) => void
}

const SCRIPT_FORMAT_OPTIONS = [
  { label: '短剧', value: 'short_drama' },
  { label: '电影', value: 'film' },
  { label: '剧集单集', value: 'series_episode' },
  { label: '舞台剧', value: 'stage_play' },
  { label: '广播剧', value: 'audio_drama' },
  { label: '通用', value: 'general' },
]

const EVENT_TYPE_OPTIONS = [
  { label: '动作', value: 'action' },
  { label: '对白', value: 'dialogue' },
  { label: '旁白', value: 'narration' },
  { label: '舞台指示', value: 'stage_direction' },
  { label: '声音', value: 'sound' },
  { label: '转场', value: 'transition' },
]

function cloneDraft(draft: ScreenplayDraft): ScreenplayDraft {
  return structuredClone(draft)
}

function compactString(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function normalizeList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : []
}

function updateProject(
  draft: ScreenplayDraft,
  patch: Partial<ProjectDraft>,
): ScreenplayDraft {
  const next = cloneDraft(draft)
  next.project = { ...(next.project ?? {}), ...patch }
  return next
}

function updateCharacter(
  draft: ScreenplayDraft,
  index: number,
  patch: Partial<CharacterDraft>,
): ScreenplayDraft {
  const next = cloneDraft(draft)
  const characters = [...(next.characters ?? [])]
  characters[index] = { ...(characters[index] ?? {}), ...patch }
  next.characters = characters
  return next
}

function updateLocation(
  draft: ScreenplayDraft,
  index: number,
  patch: Partial<LocationDraft>,
): ScreenplayDraft {
  const next = cloneDraft(draft)
  const locations = [...(next.locations ?? [])]
  locations[index] = { ...(locations[index] ?? {}), ...patch }
  next.locations = locations
  return next
}

function updateScene(
  draft: ScreenplayDraft,
  index: number,
  patch: Partial<SceneDraft>,
): ScreenplayDraft {
  const next = cloneDraft(draft)
  const scenes = [...(next.scenes ?? [])]
  scenes[index] = { ...(scenes[index] ?? {}), ...patch }
  next.scenes = scenes
  return next
}

function updateSceneSetting(
  draft: ScreenplayDraft,
  sceneIndex: number,
  patch: Partial<SceneSettingDraft>,
): ScreenplayDraft {
  const scene = draft.scenes?.[sceneIndex] ?? {}
  return updateScene(draft, sceneIndex, {
    setting: { ...(scene.setting ?? {}), ...patch },
  })
}

function updateSceneEvent(
  draft: ScreenplayDraft,
  sceneIndex: number,
  eventIndex: number,
  patch: Partial<ScriptEventDraft>,
): ScreenplayDraft {
  const next = cloneDraft(draft)
  const scenes = [...(next.scenes ?? [])]
  const scene = { ...(scenes[sceneIndex] ?? {}) }
  const events = [...(scene.events ?? [])]
  events[eventIndex] = { ...(events[eventIndex] ?? {}), ...patch }
  scene.events = events
  scenes[sceneIndex] = scene
  next.scenes = scenes
  return next
}

function ensureAdaptationNotes(draft: ScreenplayDraft, sceneIndex: number): ScreenplayDraft {
  const scene = draft.scenes?.[sceneIndex] ?? {}
  return updateScene(draft, sceneIndex, {
    adaptation_notes: scene.adaptation_notes ?? {
      intent: '',
      omitted_or_changed: [],
      risks: [],
    },
  })
}

function updateAdaptationNotes(
  draft: ScreenplayDraft,
  sceneIndex: number,
  patch: Partial<AdaptationNotesDraft>,
): ScreenplayDraft {
  const scene = draft.scenes?.[sceneIndex] ?? {}
  return updateScene(draft, sceneIndex, {
    adaptation_notes: {
      ...(scene.adaptation_notes ?? { intent: '', omitted_or_changed: [], risks: [] }),
      ...patch,
    },
  })
}

export function ScriptVisualEditor({ draft, onDraftChange }: ScriptVisualEditorProps) {
  const project = draft.project ?? {}
  const characters = draft.characters ?? []
  const locations = draft.locations ?? []
  const scenes = draft.scenes ?? []
  const characterOptions = characters.map((character) => ({
    label: character.name ?? character.id ?? '未命名角色',
    value: character.id ?? '',
  })).filter((option) => option.value)
  const locationOptions = locations.map((location) => ({
    label: location.name ?? location.id ?? '未命名地点',
    value: location.id ?? '',
  })).filter((option) => option.value)

  if (!draft.project && characters.length === 0 && scenes.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前 YAML 暂无法可视化展示" />
  }

  return (
    <div className="sw-visual-editor">
      <div className="sw-visual-note" role="note">
        <InfoCircleOutlined aria-hidden />
        <Text type="secondary">
          当前为本地草稿编辑，复制或下载会使用表单修改后的 YAML。
        </Text>
      </div>

      <Card size="small" title="项目基础信息" variant="borderless">
        <Form layout="vertical" component="div" className="sw-visual-form">
          <div className="sw-visual-section">
            <Text strong>元数据配置</Text>
            <Form.Item label="标题">
              <Input
                value={compactString(project.title)}
                onChange={(event) =>
                  onDraftChange(updateProject(draft, { title: event.target.value }))
                }
              />
            </Form.Item>
            <Form.Item label="类型标签">
              <Select
                mode="tags"
                value={normalizeList(project.genre)}
                tokenSeparators={['，', ',', ' ']}
                onChange={(genre) => onDraftChange(updateProject(draft, { genre }))}
              />
            </Form.Item>
            <Flex gap={12} wrap>
              <Form.Item label="格式" className="sw-visual-form-half">
                <Select
                  value={project.format ?? 'short_drama'}
                  options={SCRIPT_FORMAT_OPTIONS}
                  onChange={(format) => onDraftChange(updateProject(draft, { format }))}
                />
              </Form.Item>
              <Form.Item label="目标受众" className="sw-visual-form-half">
                <Input
                  value={compactString(project.target_audience)}
                  onChange={(event) =>
                    onDraftChange(updateProject(draft, { target_audience: event.target.value }))
                  }
                />
              </Form.Item>
            </Flex>
          </div>
          <div className="sw-visual-section">
            <Text strong>核心故事大纲</Text>
            <Form.Item label="一句话故事">
              <TextArea
                autoSize={{ minRows: 2, maxRows: 5 }}
                value={compactString(project.logline)}
                onChange={(event) =>
                  onDraftChange(updateProject(draft, { logline: event.target.value }))
                }
              />
            </Form.Item>
            <Form.Item label="整体风格">
              <TextArea
                autoSize={{ minRows: 2, maxRows: 4 }}
                value={compactString(project.tone)}
                onChange={(event) =>
                  onDraftChange(updateProject(draft, { tone: event.target.value }))
                }
              />
            </Form.Item>
          </div>
        </Form>
      </Card>

      <Card
        size="small"
        title={
          <Flex align="center" justify="space-between" gap={8}>
            <span>角色管理</span>
            <Tag>{characters.length} 个角色</Tag>
          </Flex>
        }
        variant="borderless"
      >
        <Space orientation="vertical" size={10} style={{ width: '100%' }}>
          {characters.map((character, index) => (
            <Card
              key={character.id ?? index}
              size="small"
              title={
                <Flex align="center" justify="space-between" gap={8}>
                  <Text strong>{character.name || `角色 ${index + 1}`}</Text>
                  <Text type="secondary" code>
                    {character.id}
                  </Text>
                </Flex>
              }
            >
              <Form layout="vertical" component="div" className="sw-visual-form">
                <Flex gap={12} wrap>
                  <Form.Item label="姓名" className="sw-visual-form-half">
                    <Input
                      value={compactString(character.name)}
                      onChange={(event) =>
                        onDraftChange(updateCharacter(draft, index, { name: event.target.value }))
                      }
                    />
                  </Form.Item>
                  <Form.Item label="角色功能" className="sw-visual-form-half">
                    <Input
                      value={compactString(character.role)}
                      onChange={(event) =>
                        onDraftChange(updateCharacter(draft, index, { role: event.target.value }))
                      }
                    />
                  </Form.Item>
                </Flex>
                <Form.Item label="人物描述">
                  <TextArea
                    autoSize={{ minRows: 2, maxRows: 5 }}
                    value={compactString(character.description)}
                    onChange={(event) =>
                      onDraftChange(updateCharacter(draft, index, { description: event.target.value }))
                    }
                  />
                </Form.Item>
                <Form.Item label="目标">
                  <Select
                    mode="tags"
                    value={normalizeList(character.goals)}
                    tokenSeparators={['，', ',', '；', ';']}
                    onChange={(goals) => onDraftChange(updateCharacter(draft, index, { goals }))}
                  />
                </Form.Item>
                <Form.Item label="冲突">
                  <Select
                    mode="tags"
                    value={normalizeList(character.conflicts)}
                    tokenSeparators={['，', ',', '；', ';']}
                    onChange={(conflicts) =>
                      onDraftChange(updateCharacter(draft, index, { conflicts }))
                    }
                  />
                </Form.Item>
              </Form>
            </Card>
          ))}
        </Space>
      </Card>

      <Card size="small" title="地点管理" variant="borderless">
        <Collapse
          size="small"
          items={locations.map((location, index) => ({
            key: location.id ?? String(index),
            label: (
              <Flex align="center" justify="space-between" gap={8}>
                <Text>{location.name || `地点 ${index + 1}`}</Text>
                <Text type="secondary" code>
                  {location.id}
                </Text>
              </Flex>
            ),
            children: (
              <Form layout="vertical" component="div" className="sw-visual-form">
                <Form.Item label="地点名称">
                  <Input
                    value={compactString(location.name)}
                    onChange={(event) =>
                      onDraftChange(updateLocation(draft, index, { name: event.target.value }))
                    }
                  />
                </Form.Item>
                <Form.Item label="地点描述">
                  <TextArea
                    autoSize={{ minRows: 2, maxRows: 5 }}
                    value={compactString(location.description)}
                    onChange={(event) =>
                      onDraftChange(updateLocation(draft, index, { description: event.target.value }))
                    }
                  />
                </Form.Item>
                <Form.Item label="视觉母题">
                  <Select
                    mode="tags"
                    value={normalizeList(location.visual_motifs)}
                    tokenSeparators={['，', ',', '；', ';']}
                    onChange={(visual_motifs) =>
                      onDraftChange(updateLocation(draft, index, { visual_motifs }))
                    }
                  />
                </Form.Item>
              </Form>
            ),
          }))}
        />
      </Card>

      <Card
        size="small"
        title={
          <Flex align="center" justify="space-between" gap={8}>
            <span>场景/剧幕管理</span>
            <Tag>{scenes.length} 个场景</Tag>
          </Flex>
        }
        variant="borderless"
      >
        <Collapse
          size="small"
          items={scenes.map((scene, sceneIndex) => {
            const notes = scene.adaptation_notes
            return {
              key: scene.id ?? String(sceneIndex),
              label: (
                <Flex align="center" justify="space-between" gap={8}>
                  <Text ellipsis>{scene.title || `场景 ${sceneIndex + 1}`}</Text>
                  <Text type="secondary" code>
                    {scene.id}
                  </Text>
                </Flex>
              ),
              children: (
                <Space orientation="vertical" size={12} style={{ width: '100%' }}>
                  <Form layout="vertical" component="div" className="sw-visual-form">
                    <Form.Item label="场景标题">
                      <Input
                        value={compactString(scene.title)}
                        onChange={(event) =>
                          onDraftChange(updateScene(draft, sceneIndex, { title: event.target.value }))
                        }
                      />
                    </Form.Item>
                    <Flex gap={12} wrap>
                      <Form.Item label="地点" className="sw-visual-form-half">
                        <Select
                          allowClear
                          value={scene.setting?.location_id}
                          options={locationOptions}
                          onChange={(location_id) =>
                            onDraftChange(updateSceneSetting(draft, sceneIndex, { location_id }))
                          }
                        />
                      </Form.Item>
                      <Form.Item label="时段" className="sw-visual-form-half">
                        <Input
                          value={compactString(scene.setting?.time_of_day)}
                          onChange={(event) =>
                            onDraftChange(
                              updateSceneSetting(draft, sceneIndex, {
                                time_of_day: event.target.value,
                              }),
                            )
                          }
                        />
                      </Form.Item>
                    </Flex>
                    <Form.Item label="戏剧目的">
                      <TextArea
                        autoSize={{ minRows: 2, maxRows: 4 }}
                        value={compactString(scene.dramatic_purpose)}
                        onChange={(event) =>
                          onDraftChange(
                            updateScene(draft, sceneIndex, {
                              dramatic_purpose: event.target.value,
                            }),
                          )
                        }
                      />
                    </Form.Item>
                    <Form.Item label="核心冲突">
                      <TextArea
                        autoSize={{ minRows: 2, maxRows: 4 }}
                        value={compactString(scene.conflict)}
                        onChange={(event) =>
                          onDraftChange(updateScene(draft, sceneIndex, { conflict: event.target.value }))
                        }
                      />
                    </Form.Item>
                  </Form>

                  <div className="sw-event-list">
                    <Text strong>事件</Text>
                    {scene.events?.map((event, eventIndex) => (
                      <Card key={event.id ?? eventIndex} size="small" className="sw-event-card">
                        <Flex gap={12} wrap>
                          <Select
                            className="sw-event-type"
                            value={event.type}
                            options={EVENT_TYPE_OPTIONS}
                            onChange={(type) =>
                              onDraftChange(
                                updateSceneEvent(draft, sceneIndex, eventIndex, { type }),
                              )
                            }
                          />
                          <Select
                            allowClear
                            className="sw-event-character"
                            value={event.character_id ?? undefined}
                            options={characterOptions}
                            placeholder="关联角色"
                            onChange={(character_id) =>
                              onDraftChange(
                                updateSceneEvent(draft, sceneIndex, eventIndex, {
                                  character_id: character_id ?? null,
                                }),
                              )
                            }
                          />
                        </Flex>
                        <TextArea
                          autoSize={{ minRows: 2, maxRows: 6 }}
                          value={compactString(event.content)}
                          onChange={(input) =>
                            onDraftChange(
                              updateSceneEvent(draft, sceneIndex, eventIndex, {
                                content: input.target.value,
                              }),
                            )
                          }
                        />
                      </Card>
                    ))}
                  </div>

                  {notes ? (
                    <Form layout="vertical" component="div" className="sw-visual-form">
                      <Form.Item label="改编意图">
                        <TextArea
                          autoSize={{ minRows: 2, maxRows: 4 }}
                          value={compactString(notes.intent)}
                          onChange={(event) =>
                            onDraftChange(
                              updateAdaptationNotes(draft, sceneIndex, {
                                intent: event.target.value,
                              }),
                            )
                          }
                        />
                      </Form.Item>
                      <Form.Item label="删改说明">
                        <Select
                          mode="tags"
                          value={normalizeList(notes.omitted_or_changed)}
                          tokenSeparators={['，', ',', '；', ';']}
                          onChange={(omitted_or_changed) =>
                            onDraftChange(
                              updateAdaptationNotes(draft, sceneIndex, {
                                omitted_or_changed,
                              }),
                            )
                          }
                        />
                      </Form.Item>
                    </Form>
                  ) : (
                    <Alert
                      type="warning"
                      showIcon
                      message="缺少改编说明"
                      description={
                        <Flex align="center" justify="space-between" gap={12} wrap>
                          <Paragraph style={{ margin: 0 }}>
                            这类字段缺失通常会导致本地验证失败，可先补一段改编意图。
                          </Paragraph>
                          <Button
                            size="small"
                            icon={<PlusOutlined aria-hidden />}
                            onClick={() => onDraftChange(ensureAdaptationNotes(draft, sceneIndex))}
                          >
                            补充说明
                          </Button>
                        </Flex>
                      }
                    />
                  )}
                </Space>
              ),
            }
          })}
        />
      </Card>
    </div>
  )
}
