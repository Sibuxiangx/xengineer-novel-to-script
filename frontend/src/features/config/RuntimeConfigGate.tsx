import type { ReactNode } from 'react'
import { Alert, Button, Result, Spin, Typography } from 'antd'
import { ReloadOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import { getErrorMessage } from '../../lib/api'
import { useRuntimeConfig } from './hooks'
import { RuntimeConfigForm } from './RuntimeConfigForm'
import './RuntimeConfigGate.css'

const { Paragraph, Text, Title } = Typography

type RuntimeConfigGateProps = {
  children: ReactNode
}

export function RuntimeConfigGate({ children }: RuntimeConfigGateProps) {
  const configQuery = useRuntimeConfig()
  const config = configQuery.data

  if (configQuery.isLoading) {
    return (
      <div className="sw-env-gate-loading" role="status" aria-live="polite">
        <Spin size="large">
          <div className="sw-env-gate-loading-text">检查本地运行环境…</div>
        </Spin>
      </div>
    )
  }

  if (configQuery.isError) {
    return (
      <div className="sw-env-gate-page">
        <Result
          status="error"
          title="无法连接本地后端"
          subTitle={getErrorMessage(configQuery.error)}
          extra={[
            <Button
              key="retry"
              type="primary"
              icon={<ReloadOutlined aria-hidden />}
              onClick={() => void configQuery.refetch()}
            >
              重试
            </Button>,
          ]}
        />
      </div>
    )
  }

  if (config?.deepseek_api_key_configured) {
    return children
  }

  return (
    <main className="sw-env-gate-page" aria-label="ScriptWeaver 环境初始化">
      <section className="sw-env-gate-shell">
        <div className="sw-env-gate-intro">
          <div className="sw-env-gate-mark" aria-hidden>
            <SafetyCertificateOutlined />
          </div>
          <Text className="sw-env-gate-kicker">本地初始化</Text>
          <Title>先完成模型环境配置</Title>
          <Paragraph>
            ScriptWeaver 依赖真实 DeepSeek 调用来完成分章推导、剧情索引、剧本生成和自然语言修改。
            未配置密钥时，页面会停在这里，避免用户进入一个必然失败的工作流。
          </Paragraph>
          <Alert
            type="info"
            showIcon
            message="配置只保存在本机后端"
            description="API Key 会写入 backend/.env。前端只显示保存状态和脱敏后的 Key，不会持久化原始密钥。"
          />
        </div>

        <div className="sw-env-gate-card">
          <RuntimeConfigForm
            config={config}
            onSaved={() => void configQuery.refetch()}
          />
        </div>
      </section>
    </main>
  )
}
