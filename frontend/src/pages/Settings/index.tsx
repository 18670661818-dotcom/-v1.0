import { useState, useEffect } from 'react'
import {
  Card,
  Form,
  Input,
  InputNumber,
  Switch,
  Button,
  Select,
  Divider,
  message,
  Typography,
  Row,
  Col,
  Space,
  Tabs,
  Alert,
  TimePicker,
} from 'antd'
import {
  SaveOutlined,
  ReloadOutlined,
  BellOutlined,
  CameraOutlined,
  SecurityScanOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons'
import request from '@/utils/request'
import dayjs from 'dayjs'

const { Title, Text } = Typography

interface SystemConfig {
  // 告警设置
  alert_cooldown: number
  alert_min_confidence: number
  enable_sound_alert: boolean
  enable_email_alert: boolean
  alert_email?: string
  // 摄像头设置
  frame_interval: number
  max_concurrent_streams: number
  auto_reconnect: boolean
  reconnect_interval: number
  // 检测设置
  detection_enabled: boolean
  detection_sensitivity: number
  // 系统设置
  data_retention_days: number
  auto_cleanup: boolean
  maintenance_start?: string
  maintenance_end?: string
}

const initialConfig: SystemConfig = {
  alert_cooldown: 30,
  alert_min_confidence: 0.6,
  enable_sound_alert: true,
  enable_email_alert: false,
  frame_interval: 2,
  max_concurrent_streams: 9,
  auto_reconnect: true,
  reconnect_interval: 10,
  detection_enabled: true,
  detection_sensitivity: 0.5,
  data_retention_days: 30,
  auto_cleanup: true,
}

export default function Settings() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [config, setConfig] = useState<SystemConfig>(initialConfig)
  const [activeTab, setActiveTab] = useState('alert')

  // 获取系统配置
  const fetchConfig = async () => {
    setLoading(true)
    try {
      const res = await request.get('/settings/config')
      setConfig(res.data || initialConfig)
      form.setFieldsValue(res.data || initialConfig)
    } catch (error) {
      console.error('获取配置失败:', error)
      form.setFieldsValue(initialConfig)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchConfig()
  }, [])

  // 保存配置
  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)
      await request.put('/settings/config', values)
      setConfig(values)
      message.success('配置保存成功')
    } catch (error) {
      console.error('保存配置失败:', error)
      message.error('保存配置失败')
    } finally {
      setSaving(false)
    }
  }

  // 重置配置
  const handleReset = () => {
    form.setFieldsValue(initialConfig)
    message.info('已重置为默认配置')
  }

  // 告警设置面板
  const AlertSettings = () => (
    <div>
      <Alert
        message="告警配置"
        description="配置告警通知规则和触发条件"
        type="info"
        showIcon
        style={{ marginBottom: 24 }}
      />

      <Row gutter={24}>
        <Col span={12}>
          <Form.Item
            name="alert_cooldown"
            label="告警冷却时间（秒）"
            tooltip="同一摄像头两次告警的最小间隔时间"
            rules={[{ required: true, message: '请输入冷却时间' }]}
          >
            <InputNumber min={5} max={300} style={{ width: '100%' }} />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item
            name="alert_min_confidence"
            label="最低置信度"
            tooltip="低于此值的检测结果将被忽略"
            rules={[{ required: true, message: '请输入最低置信度' }]}
          >
            <InputNumber
              min={0.1}
              max={1}
              step={0.1}
              style={{ width: '100%' }}
            />
          </Form.Item>
        </Col>
      </Row>

      <Row gutter={24}>
        <Col span={12}>
          <Form.Item
            name="enable_sound_alert"
            label="声音提醒"
            valuePropName="checked"
          >
            <Switch checkedChildren="开启" unCheckedChildren="关闭" />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item
            name="enable_email_alert"
            label="邮件通知"
            valuePropName="checked"
          >
            <Switch checkedChildren="开启" unCheckedChildren="关闭" />
          </Form.Item>
        </Col>
      </Row>

      <Form.Item
        noStyle
        shouldUpdate={(prev, curr) =>
          prev.enable_email_alert !== curr.enable_email_alert
        }
      >
        {({ getFieldValue }) =>
          getFieldValue('enable_email_alert') ? (
            <Form.Item
              name="alert_email"
              label="通知邮箱"
              rules={[
                { required: true, message: '请输入邮箱地址' },
                { type: 'email', message: '请输入有效的邮箱地址' },
              ]}
            >
              <Input placeholder="example@company.com" />
            </Form.Item>
          ) : null
        }
      </Form.Item>
    </div>
  )

  // 摄像头设置面板
  const CameraSettings = () => (
    <div>
      <Alert
        message="摄像头配置"
        description="配置摄像头连接和流媒体参数"
        type="info"
        showIcon
        style={{ marginBottom: 24 }}
      />

      <Row gutter={24}>
        <Col span={12}>
          <Form.Item
            name="frame_interval"
            label="采样间隔（秒）"
            tooltip="每隔多少秒采集一帧进行检测"
            rules={[{ required: true, message: '请输入采样间隔' }]}
          >
            <InputNumber min={1} max={10} style={{ width: '100%' }} />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item
            name="max_concurrent_streams"
            label="最大并发流数"
            tooltip="同时显示的最大摄像头数量"
            rules={[{ required: true, message: '请输入最大并发流数' }]}
          >
            <InputNumber min={1} max={16} style={{ width: '100%' }} />
          </Form.Item>
        </Col>
      </Row>

      <Row gutter={24}>
        <Col span={12}>
          <Form.Item
            name="auto_reconnect"
            label="自动重连"
            valuePropName="checked"
          >
            <Switch checkedChildren="开启" unCheckedChildren="关闭" />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item
            noStyle
            shouldUpdate={(prev, curr) =>
              prev.auto_reconnect !== curr.auto_reconnect
            }
          >
            {({ getFieldValue }) =>
              getFieldValue('auto_reconnect') ? (
                <Form.Item
                  name="reconnect_interval"
                  label="重连间隔（秒）"
                  rules={[{ required: true, message: '请输入重连间隔' }]}
                >
                  <InputNumber min={5} max={60} style={{ width: '100%' }} />
                </Form.Item>
              ) : null
            }
          </Form.Item>
        </Col>
      </Row>
    </div>
  )

  // 检测设置面板
  const DetectionSettings = () => (
    <div>
      <Alert
        message="检测配置"
        description="配置AI检测模型参数"
        type="info"
        showIcon
        style={{ marginBottom: 24 }}
      />

      <Row gutter={24}>
        <Col span={12}>
          <Form.Item
            name="detection_enabled"
            label="启用检测"
            valuePropName="checked"
          >
            <Switch checkedChildren="开启" unCheckedChildren="关闭" />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item
            name="detection_sensitivity"
            label="检测灵敏度"
            tooltip="灵敏度越高，检测越严格"
            rules={[{ required: true, message: '请输入灵敏度' }]}
          >
            <InputNumber
              min={0.1}
              max={1}
              step={0.1}
              style={{ width: '100%' }}
            />
          </Form.Item>
        </Col>
      </Row>
    </div>
  )

  // 系统维护面板
  const SystemSettings = () => (
    <div>
      <Alert
        message="系统维护"
        description="配置数据保留和系统维护参数"
        type="info"
        showIcon
        style={{ marginBottom: 24 }}
      />

      <Row gutter={24}>
        <Col span={12}>
          <Form.Item
            name="data_retention_days"
            label="数据保留天数"
            tooltip="超过此时间的数据将被自动清理"
            rules={[{ required: true, message: '请输入保留天数' }]}
          >
            <InputNumber min={7} max={365} style={{ width: '100%' }} />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item
            name="auto_cleanup"
            label="自动清理"
            valuePropName="checked"
          >
            <Switch checkedChildren="开启" unCheckedChildren="关闭" />
          </Form.Item>
        </Col>
      </Row>

      <Divider>维护时间窗口</Divider>

      <Row gutter={24}>
        <Col span={12}>
          <Form.Item name="maintenance_start" label="开始时间">
            <TimePicker format="HH:mm" style={{ width: '100%' }} />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="maintenance_end" label="结束时间">
            <TimePicker format="HH:mm" style={{ width: '100%' }} />
          </Form.Item>
        </Col>
      </Row>
    </div>
  )

  const tabItems = [
    {
      key: 'alert',
      label: (
        <span>
          <BellOutlined />
          告警设置
        </span>
      ),
      children: <AlertSettings />,
    },
    {
      key: 'camera',
      label: (
        <span>
          <CameraOutlined />
          摄像头设置
        </span>
      ),
      children: <CameraSettings />,
    },
    {
      key: 'detection',
      label: (
        <span>
          <SecurityScanOutlined />
          检测设置
        </span>
      ),
      children: <DetectionSettings />,
    },
    {
      key: 'system',
      label: (
        <span>
          <InfoCircleOutlined />
          系统维护
        </span>
      ),
      children: <SystemSettings />,
    },
  ]

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
        }}
      >
        <Title level={4} style={{ margin: 0 }}>
          系统设置
        </Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={handleReset}>
            重置默认
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSave}
            loading={saving}
          >
            保存配置
          </Button>
        </Space>
      </div>

      <Card>
        <Form
          form={form}
          layout="vertical"
          initialValues={config}
          disabled={loading}
        >
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={tabItems}
            tabPosition="left"
            style={{ minHeight: 400 }}
          />
        </Form>
      </Card>

      <Card style={{ marginTop: 16 }}>
        <Title level={5}>系统信息</Title>
        <Row gutter={16}>
          <Col span={8}>
            <Text type="secondary">系统版本</Text>
            <div>
              <Text strong>v2.0.0</Text>
            </div>
          </Col>
          <Col span={8}>
            <Text type="secondary">数据库</Text>
            <div>
              <Text strong>SQLite</Text>
            </div>
          </Col>
          <Col span={8}>
            <Text type="secondary">运行时间</Text>
            <div>
              <Text strong>7天 12小时</Text>
            </div>
          </Col>
        </Row>
      </Card>
    </div>
  )
}
