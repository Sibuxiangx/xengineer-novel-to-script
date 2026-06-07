import { App as AntdApp, Alert, Button, Form, Input, InputNumber, Space, Tag, Typography } from 'antd'
import { ApiOutlined, LockOutlined, SaveOutlined } from '@ant-design/icons'
import { useEffect } from 'react'
import { getErrorMessage } from '../../lib/api'
import type { RuntimeConfig, RuntimeConfigUpdateRequest } from '../../types'
import { useUpdateRuntimeConfig } from './hooks'
import './RuntimeConfigForm.css'

const { Paragraph, Text, Title } = Typography

type RuntimeConfigFormValues = {
  deepseek_api_key?: string
  deepseek_base_url: string
  deepseek_model: string
  deepseek_fast_model: string
  model_context_limit: number
}

type RuntimeConfigFormProps = {
  config: RuntimeConfig | null | undefined
  compact?: boolean
  onSaved?: (config: RuntimeConfig) => void
}

function buildInitialValues(config: RuntimeConfig | null | undefined): RuntimeConfigFormValues {
  return {
    deepseek_api_key: '',
    deepseek_base_url: config?.deepseek_base_url ?? 'https://api.deepseek.com',
    deepseek_model: config?.deepseek_model ?? 'deepseek-v4-pro',
    deepseek_fast_model: config?.deepseek_fast_model ?? 'deepseek-v4-flash',
    model_context_limit: config?.model_context_limit ?? 1_000_000,
  }
}

export function RuntimeConfigForm({ config, compact = false, onSaved }: RuntimeConfigFormProps) {
  const [form] = Form.useForm<RuntimeConfigFormValues>()
  const updateConfig = useUpdateRuntimeConfig()
  const { message } = AntdApp.useApp()
  const isConfigured = Boolean(config?.deepseek_api_key_configured)

  useEffect(() => {
    form.setFieldsValue(buildInitialValues(config))
  }, [config, form])

  async function handleFinish(values: RuntimeConfigFormValues) {
    const key = values.deepseek_api_key?.trim()
    const payload: RuntimeConfigUpdateRequest = {
      deepseek_api_key: key || null,
      deepseek_base_url: values.deepseek_base_url.trim(),
      deepseek_model: values.deepseek_model.trim(),
      deepseek_fast_model: values.deepseek_fast_model.trim(),
      model_context_limit: values.model_context_limit,
    }
    try {
      const nextConfig = await updateConfig.mutateAsync(payload)
      form.setFieldValue('deepseek_api_key', '')
      void message.success('环境配置已保存')
      onSaved?.(nextConfig)
    } catch (error) {
      void message.error(getErrorMessage(error))
    }
  }

  return (
    <div className={compact ? 'sw-runtime-config-form compact' : 'sw-runtime-config-form'}>
      <div className="sw-runtime-config-head">
        <div>
          <Title level={compact ? 5 : 3}>环境配置</Title>
          <Paragraph type="secondary">
            将 DeepSeek 配置保存到本地后端的 <Text code>{config?.env_file_path ?? '.env'}</Text>，
            浏览器不会保存或回显原始密钥。
          </Paragraph>
        </div>
        <Tag
          color={isConfigured ? 'success' : 'warning'}
          icon={isConfigured ? <ApiOutlined aria-hidden /> : <LockOutlined aria-hidden />}
        >
          {isConfigured ? '已配置' : '待配置'}
        </Tag>
      </div>

      {!isConfigured ? (
        <Alert
          type="warning"
          showIcon
          message="需要先配置 DeepSeek API Key"
          description="未配置前可以打开界面，但 Agent 的真实模型调用会被保护，避免进入假成功流程。"
        />
      ) : (
        <Alert
          type="success"
          showIcon
          message={`当前 Key：${config?.deepseek_api_key_masked ?? '已保存'}`}
          description="如需轮换密钥，填写新的 API Key 后保存；留空会保留当前密钥。"
        />
      )}

      <Form
        form={form}
        layout="vertical"
        initialValues={buildInitialValues(config)}
        onFinish={(values) => void handleFinish(values)}
      >
        <Form.Item
          label="DeepSeek API Key"
          name="deepseek_api_key"
          extra={isConfigured ? '留空表示保留当前密钥。' : '用于真实模型调用，保存后写入 backend/.env。'}
          rules={[
            {
              validator: async (_, value: string | undefined) => {
                if (isConfigured || value?.trim()) return
                throw new Error('首次配置必须填写 DeepSeek API Key')
              },
            },
          ]}
        >
          <Input.Password
            autoComplete="off"
            placeholder={isConfigured ? '留空保留当前密钥' : 'sk-...'}
          />
        </Form.Item>

        <div className="sw-runtime-config-grid">
          <Form.Item
            label="API 基址"
            name="deepseek_base_url"
            rules={[{ required: true, message: '请输入 DeepSeek API 基址' }]}
          >
            <Input placeholder="https://api.deepseek.com" />
          </Form.Item>

          <Form.Item
            label="上下文窗口"
            name="model_context_limit"
            rules={[{ required: true, message: '请输入上下文窗口' }]}
          >
            <InputNumber min={1} step={10_000} className="sw-runtime-config-number" />
          </Form.Item>

          <Form.Item
            label="主模型"
            name="deepseek_model"
            rules={[{ required: true, message: '请输入主模型名称' }]}
          >
            <Input placeholder="deepseek-v4-pro" />
          </Form.Item>

          <Form.Item
            label="快速模型"
            name="deepseek_fast_model"
            rules={[{ required: true, message: '请输入快速模型名称' }]}
          >
            <Input placeholder="deepseek-v4-flash" />
          </Form.Item>
        </div>

        <Space className="sw-runtime-config-actions">
          <Button
            type="primary"
            htmlType="submit"
            icon={<SaveOutlined aria-hidden />}
            loading={updateConfig.isPending}
          >
            保存配置
          </Button>
        </Space>
      </Form>
    </div>
  )
}
