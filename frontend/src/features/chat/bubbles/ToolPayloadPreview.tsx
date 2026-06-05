import { Descriptions, Flex, List, Skeleton, Space, Tag, Typography } from 'antd'
import { useEffect, useRef } from 'react'
import type { JsonRecord, ToolCallDelta, ToolCallEvent } from '../../../types'
import { formatNumber } from '../../../lib/formatting'

const { Paragraph, Text } = Typography

type ToolPayloadPreviewProps = {
  tool: ToolCallEvent
}

const STRATEGY_LABELS: Record<string, string> = {
  line_regex: '行正则匹配',
  no_chapters: '全文单章',
}

const STATUS_LABELS: Record<string, string> = {
  accepted: '校验通过',
  rejected: '未通过，已保留草稿',
}

const SPLIT_STRATEGY_LABELS: Record<string, string> = {
  custom_rule: '按确认规则切分',
  no_chapters: '全文单章',
  heading_regex: '标题正则切分',
}

const LLM_STREAM_TOOL_NAMES = new Set([
  'propose_project_title',
  'propose_chapter_split',
  'build_book_index',
  'generate_script_yaml',
  'edit_script_yaml',
])

function asRecord(value: unknown): JsonRecord | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as JsonRecord)
    : null
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : []
}

function displayValue(value: unknown): string {
  if (typeof value === 'string') return value
  if (typeof value === 'number') return formatNumber(value)
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (value == null) return '无'
  return JSON.stringify(value)
}

function RawJsonView({
  text,
  label,
  streaming = false,
}: {
  text: string
  label: string
  streaming?: boolean
}) {
  const ref = useRef<HTMLPreElement | null>(null)
  useEffect(() => {
    if (ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight
    }
  }, [text])
  return (
    <pre
      ref={ref}
      className={`sw-json-preview ${streaming ? 'is-streaming' : ''}`}
      aria-label={label}
    >
      {text}
    </pre>
  )
}

function ContextReport({ report }: { report: JsonRecord | null }) {
  if (!report) return null
  return (
    <div className="sw-tool-context-report">
      <Text type="secondary">上下文打包</Text>
      <Flex gap={8} wrap style={{ marginTop: 6 }}>
        <Tag>
          预算 {displayValue(report.budget_tokens)}
        </Tag>
        <Tag>
          估算 {displayValue(report.estimated_tokens)}
        </Tag>
        <Tag>
          已用块 {asStringArray(report.included_block_ids).length}
        </Tag>
        <Tag>
          省略块 {asStringArray(report.omitted_block_ids).length}
        </Tag>
      </Flex>
    </div>
  )
}

function KeyValuePreview({ payload }: { payload: JsonRecord }) {
  const items = Object.entries(payload)
    .filter(([, value]) => value !== undefined)
    .slice(0, 8)
    .map(([key, value]) => ({
      key,
      label: key,
      children: <Text>{displayValue(value)}</Text>,
    }))
  return <Descriptions size="small" column={1} items={items} />
}

function ChapterSplitPreview({ payload }: { payload: JsonRecord }) {
  const rule = asRecord(payload.rule)
  const preview = asRecord(payload.preview)
  const examples = rule ? asStringArray(rule.examples) : []
  const titles = preview ? asStringArray(preview.titles).slice(0, 8) : []
  const strategy = rule && typeof rule.strategy === 'string' ? rule.strategy : ''

  return (
    <Space orientation="vertical" size={10} style={{ width: '100%' }}>
      <Flex gap={8} wrap>
        <Tag color="blue">匹配策略：{STRATEGY_LABELS[strategy] ?? (strategy || '未知')}</Tag>
        {typeof rule?.confidence === 'number' ? (
          <Tag>置信度：{Math.round(rule.confidence * 100)}%</Tag>
        ) : null}
        {typeof preview?.chapter_count === 'number' ? (
          <Tag color="green">预览章节：{preview.chapter_count}</Tag>
        ) : null}
        {typeof preview?.unmatched_candidate_count === 'number' &&
        preview.unmatched_candidate_count > 0 ? (
          <Tag color="warning">疑似漏切：{preview.unmatched_candidate_count}</Tag>
        ) : null}
      </Flex>

      {typeof rule?.heading_regex === 'string' && rule.heading_regex ? (
        <div>
          <Text type="secondary">标题匹配规则</Text>
          <Paragraph code copyable className="sw-tool-inline-code">
            {rule.heading_regex}
          </Paragraph>
        </div>
      ) : null}

      {typeof rule?.reason === 'string' ? (
        <Paragraph type="secondary" style={{ marginBottom: 0 }}>
          {rule.reason}
        </Paragraph>
      ) : null}

      {examples.length > 0 ? (
        <div>
          <Text strong>命中的标题样例</Text>
          <Flex gap={6} wrap style={{ marginTop: 6 }}>
            {examples.map((example) => (
              <Tag key={example}>{example}</Tag>
            ))}
          </Flex>
        </div>
      ) : null}

      {titles.length > 0 ? (
        <List
          size="small"
          header={<Text strong>章节预览</Text>}
          dataSource={titles}
          renderItem={(title, index) => (
            <List.Item>
              <Text type="secondary">#{index + 1}</Text>
              <Text>{title}</Text>
            </List.Item>
          )}
        />
      ) : null}
    </Space>
  )
}

function deltaItems(
  deltas: ToolCallDelta[],
  kind: string,
): JsonRecord[] {
  return deltas
    .filter((delta) => delta.delta.kind === kind)
    .map((delta) => asRecord(delta.delta.item))
    .filter((item): item is JsonRecord => Boolean(item))
}

function latestMetrics(deltas: ToolCallDelta[]): JsonRecord | null {
  for (let index = deltas.length - 1; index >= 0; index -= 1) {
    const delta = deltas[index].delta
    if (delta.kind === 'metrics') return delta
  }
  return null
}

function llmStreamText(deltas: ToolCallDelta[]): string {
  return deltas
    .filter((delta) => delta.delta.kind === 'llm_stream')
    .map((delta) => delta.delta.content)
    .filter((content): content is string => typeof content === 'string')
    .join('')
}

function latestLlmPhase(deltas: ToolCallDelta[]): string {
  for (let index = deltas.length - 1; index >= 0; index -= 1) {
    const delta = deltas[index].delta
    if (delta.kind !== 'llm_stream') continue
    const phase = delta.phase ?? delta.tool_phase ?? delta.task
    if (typeof phase === 'string' && phase) return phase
  }
  return '模型输出'
}

function LlmStreamingPreview({ tool }: { tool: ToolCallEvent }) {
  const text = llmStreamText(tool.deltas ?? [])
  if (!text) {
    return (
      <Space orientation="vertical" size={8} style={{ width: '100%' }}>
        <Text type="secondary">等待模型开始输出…</Text>
        <Skeleton active paragraph={{ rows: 3 }} title={false} />
      </Space>
    )
  }

  return (
    <Space orientation="vertical" size={8} style={{ width: '100%' }}>
      <Flex gap={8} align="center" wrap>
        <Tag color="processing">LLM 流式输出</Tag>
        <Text type="secondary">{latestLlmPhase(tool.deltas ?? [])}</Text>
      </Flex>
      <RawJsonView text={text} label={`${tool.name} 模型流式输出`} streaming />
    </Space>
  )
}

function StreamingMetricTags({
  tool,
  payload,
}: {
  tool: ToolCallEvent
  payload: JsonRecord
}) {
  const metrics = latestMetrics(tool.deltas ?? [])
  const isRunning = tool.status === 'running'
  const chapterCount = payload.chapter_count ?? metrics?.chapter_count
  const characterCount = payload.character_count ?? metrics?.character_count
  const locationCount = payload.location_count ?? metrics?.location_count

  if (isRunning && chapterCount == null && characterCount == null && locationCount == null) {
    return (
      <Flex gap={8} wrap aria-label="正在抽取剧情索引指标">
        <Skeleton.Button active size="small" style={{ width: 82 }} />
        <Skeleton.Button active size="small" style={{ width: 82 }} />
        <Skeleton.Button active size="small" style={{ width: 82 }} />
      </Flex>
    )
  }

  return (
    <Flex gap={8} wrap>
      <Tag color="green">章节 {displayValue(chapterCount)}</Tag>
      <Tag>人物 {displayValue(characterCount)}</Tag>
      <Tag>地点 {displayValue(locationCount)}</Tag>
    </Flex>
  )
}

function StreamingEntityTags({
  tool,
  kind,
  label,
  color,
}: {
  tool: ToolCallEvent
  kind: 'character' | 'location'
  label: string
  color: string
}) {
  const items = deltaItems(tool.deltas ?? [], kind)
  if (items.length === 0 && tool.status === 'running') {
    return (
      <Space orientation="vertical" size={6} style={{ width: '100%' }}>
        <Text type="secondary">{label}</Text>
        <Flex gap={8} wrap>
          <Skeleton.Button active size="small" style={{ width: 96 }} />
          <Skeleton.Button active size="small" style={{ width: 112 }} />
          <Skeleton.Button active size="small" style={{ width: 88 }} />
        </Flex>
      </Space>
    )
  }
  if (items.length === 0) return null

  return (
    <Space orientation="vertical" size={6} style={{ width: '100%' }}>
      <Text type="secondary">{label}</Text>
      <Flex gap={8} wrap>
        {items.map((item, index) => (
          <Tag
            key={`${kind}-${displayValue(item.id)}-${index}`}
            color={color}
            className="sw-tool-stream-tag"
          >
            {displayValue(item.label)}
          </Tag>
        ))}
      </Flex>
    </Space>
  )
}

function ScriptResultPreview({ tool, payload }: { tool: ToolCallEvent; payload: JsonRecord }) {
  const latestValidation = [...(tool.deltas ?? [])]
    .reverse()
    .find((delta) => delta.delta.kind === 'validation')?.delta
  const status =
    typeof payload.validation_status === 'string'
      ? payload.validation_status
      : typeof latestValidation?.validation_status === 'string'
        ? latestValidation.validation_status
        : ''
  const accepted =
    typeof payload.accepted === 'boolean'
      ? payload.accepted
      : typeof latestValidation?.accepted === 'boolean'
        ? latestValidation.accepted
        : status === 'accepted'
  const versionId =
    typeof payload.accepted_version_id === 'string'
      ? payload.accepted_version_id
      : typeof payload.rejected_version_id === 'string'
        ? payload.rejected_version_id
        : null

  return (
    <Space orientation="vertical" size={10} style={{ width: '100%' }}>
      <Flex gap={8} wrap>
        <Tag color={accepted ? 'success' : 'warning'}>
          {STATUS_LABELS[status] ?? (accepted ? '校验通过' : '待修复')}
        </Tag>
        {typeof payload.repair_attempt_count === 'number' ? (
          <Tag>自动修复：{payload.repair_attempt_count} 次</Tag>
        ) : typeof latestValidation?.repair_attempt_count === 'number' ? (
          <Tag>自动修复：{latestValidation.repair_attempt_count} 次</Tag>
        ) : null}
        {typeof payload.operation_count === 'number' ? (
          <Tag>编辑操作：{payload.operation_count} 个</Tag>
        ) : null}
        {typeof payload.severity === 'string' ? (
          <Tag>严重度：{payload.severity}</Tag>
        ) : null}
      </Flex>
      {versionId ? (
        <Text type="secondary">
          版本：<Text code>{versionId}</Text>
        </Text>
      ) : null}
      <ContextReport report={asRecord(payload.context_report)} />
    </Space>
  )
}

function ToolFriendlyPreview({ tool, payload }: { tool: ToolCallEvent; payload: JsonRecord }) {
  if (tool.name === 'propose_project_title') {
    return (
      <Space orientation="vertical" size={6}>
        <Text strong>{displayValue(payload.title)}</Text>
        {typeof payload.reason === 'string' ? (
          <Text type="secondary">{payload.reason}</Text>
        ) : null}
      </Space>
    )
  }

  if (tool.name === 'create_project') {
    return (
      <Descriptions
        size="small"
        column={1}
        items={[
          { key: 'title', label: '项目名', children: displayValue(payload.title) },
          { key: 'project_id', label: '项目 ID', children: <Text code>{displayValue(payload.project_id)}</Text> },
        ]}
      />
    )
  }

  if (tool.name === 'propose_chapter_split') {
    return <ChapterSplitPreview payload={payload} />
  }

  if (tool.name === 'request_chapter_split_confirmation') {
    return (
      <Space orientation="vertical" size={6}>
        <Tag color="warning">等待用户确认</Tag>
        <Text>预览章节：{displayValue(payload.chapter_count)}</Text>
        {typeof payload.prompt === 'string' ? (
          <Text type="secondary">{payload.prompt}</Text>
        ) : null}
      </Space>
    )
  }

  if (tool.name === 'confirm_chapter_split') {
    const splitStrategy =
      typeof payload.split_strategy === 'string' ? payload.split_strategy : ''
    return (
      <Flex gap={8} wrap>
        <Tag color="green">已导入 {displayValue(payload.chapter_count)} 章</Tag>
        <Tag>{SPLIT_STRATEGY_LABELS[splitStrategy] ?? (splitStrategy || '切分完成')}</Tag>
      </Flex>
    )
  }

  if (tool.name === 'build_book_index') {
    return (
      <Space orientation="vertical" size={10} style={{ width: '100%' }}>
        <StreamingMetricTags tool={tool} payload={payload} />
        <StreamingEntityTags tool={tool} kind="character" label="人物" color="blue" />
        <StreamingEntityTags tool={tool} kind="location" label="地点" color="green" />
        <ContextReport report={asRecord(payload.context_report)} />
      </Space>
    )
  }

  if (tool.name === 'generate_script_yaml' || tool.name === 'edit_script_yaml') {
    return <ScriptResultPreview tool={tool} payload={payload} />
  }

  return <KeyValuePreview payload={payload} />
}

export function ToolPayloadPreview({ tool }: ToolPayloadPreviewProps) {
  const payload = tool.output ?? tool.input
  const streamText = llmStreamText(tool.deltas ?? [])
  const shouldShowLiveStream =
    tool.status === 'running' &&
    (Boolean(streamText) || LLM_STREAM_TOOL_NAMES.has(tool.name))

  if (tool.error_message) {
    return <RawJsonView text={tool.error_message} label={`${tool.name} 错误`} />
  }

  if (!payload && shouldShowLiveStream) {
    return <LlmStreamingPreview tool={tool} />
  }

  if (!payload) {
    return <Text type="secondary">等待工具返回</Text>
  }

  return shouldShowLiveStream ? (
    <LlmStreamingPreview tool={tool} />
  ) : (
    <ToolFriendlyPreview tool={tool} payload={payload} />
  )
}
