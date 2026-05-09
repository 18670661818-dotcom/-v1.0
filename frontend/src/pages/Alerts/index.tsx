import { useEffect, useState, useCallback } from 'react'
import {
  Card,
  Table,
  Tag,
  Select,
  DatePicker,
  Button,
  Space,
  message,
  Typography,
  Row,
  Col,
  Statistic,
} from 'antd'
import {
  ReloadOutlined,
  CheckOutlined,
  AlertOutlined,
  WarningOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons'
import request from '@/utils/request'
import dayjs from 'dayjs'
import type { Alert, AlertLevel, AlertStats, AlertListResponse } from '@/types'

const { Title } = Typography
const { RangePicker } = DatePicker

// 告警级别配置
const levelMap: Record<
  AlertLevel,
  { color: string; icon: React.ReactNode; text: string }
> = {
  critical: { color: 'red', icon: <AlertOutlined />, text: '严重' },
  warning: { color: 'orange', icon: <WarningOutlined />, text: '警告' },
  info: { color: 'blue', icon: <InfoCircleOutlined />, text: '提示' },
}

// 违规类型中文映射
const violationNames: Record<string, string> = {
  cockroach: '发现蟑螂',
  hairnet: '佩戴发网',
  no_gloves: '未戴手套',
  no_hat: '未戴帽子',
  rat: '发现老鼠',
  with_mask: '佩戴口罩',
  without_mask: '未佩戴口罩',
  smoke: '吸烟行为',
  phone: '玩手机',
  overflow: '溢出',
  garbage: '垃圾',
  garbage_bin: '垃圾桶',
  chef_uniform: '穿工作服',
  chef_hat: '戴厨师帽',
  no_chef_uniform: '未穿工作服',
  no_chef_hat: '未戴厨师帽',
}

// 初始统计数据
const initialStats: AlertStats = {
  total_today: 0,
  total_week: 0,
  by_type: {},
  by_camera: {},
  trend: [],
}

interface Filters {
  page_size: number
  violation_type?: string
  level?: string
  start_time?: string
  end_time?: string
}

export default function Alerts() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState<Filters>({ page_size: 20 })
  const [selectedKeys, setSelectedKeys] = useState<string[]>([])
  const [stats, setStats] = useState<AlertStats>(initialStats)
  const [acknowledging, setAcknowledging] = useState(false)

  // 获取告警列表
  const fetchAlerts = useCallback(async () => {
    setLoading(true)
    try {
      const res = await request.get<AlertListResponse>('/alerts/', {
        params: { ...filters, page },
      })
      setAlerts(res.data?.items || [])
      setTotal(res.data?.total || 0)
    } catch (error) {
      console.error('获取告警列表失败:', error)
    } finally {
      setLoading(false)
    }
  }, [filters, page])

  // 获取统计数据
  const fetchStats = useCallback(async () => {
    try {
      const res = await request.get<AlertStats>('/alerts/stats')
      setStats(res.data || initialStats)
    } catch (error) {
      console.error('获取统计数据失败:', error)
    }
  }, [])

  useEffect(() => {
    fetchAlerts()
    fetchStats()
  }, [fetchAlerts, fetchStats])

  // 确认告警
  const handleAcknowledge = async (alertIds?: string[]) => {
    const ids = alertIds || selectedKeys
    if (ids.length === 0) {
      message.warning('请选择告警')
      return
    }

    setAcknowledging(true)
    try {
      await request.post('/alerts/acknowledge', { alert_ids: ids })
      message.success(`已确认 ${ids.length} 条告警`)
      setSelectedKeys([])
      fetchAlerts()
    } catch (error) {
      console.error('确认告警失败:', error)
      message.error('确认告警失败')
    } finally {
      setAcknowledging(false)
    }
  }

  // 更新过滤条件
  const updateFilter = (key: keyof Filters, value: any) => {
    setFilters((f) => ({ ...f, [key]: value }))
    setPage(1) // 重置页码
  }

  // 表格列配置
  const columns = [
    {
      title: '时间',
      dataIndex: 'detected_at',
      key: 'time',
      width: 160,
      render: (t: string) => (t ? dayjs(t).format('YYYY-MM-DD HH:mm:ss') : '-'),
      sorter: (a: Alert, b: Alert) =>
        dayjs(a.detected_at).unix() - dayjs(b.detected_at).unix(),
    },
    {
      title: '级别',
      dataIndex: 'level',
      key: 'level',
      width: 80,
      render: (l: AlertLevel) => {
        const cfg = levelMap[l] || levelMap.info
        return (
          <Tag color={cfg.color} icon={cfg.icon}>
            {cfg.text}
          </Tag>
        )
      },
    },
    {
      title: '摄像头',
      dataIndex: 'camera_name',
      key: 'cam',
      width: 160,
      ellipsis: true,
    },
    {
      title: '违规类型',
      dataIndex: 'violation_type',
      key: 'type',
      width: 140,
      render: (t: string) => (
        <Tag color="volcano">{violationNames[t] || t}</Tag>
      ),
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      key: 'conf',
      width: 90,
      render: (v: number) => (v ? `${(v * 100).toFixed(0)}%` : '-'),
    },
    {
      title: '状态',
      dataIndex: 'acknowledged_at',
      key: 'ack',
      width: 80,
      render: (t: string | null) =>
        t ? <Tag color="green">已确认</Tag> : <Tag color="red">未处理</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: any, record: Alert) =>
        !record.acknowledged_at && (
          <Button
            size="small"
            type="link"
            icon={<CheckOutlined />}
            onClick={() => handleAcknowledge([record.alert_id])}
            loading={acknowledging}
          >
            确认
          </Button>
        ),
    },
  ]

  // 计算统计
  const pendingCount = alerts.filter((a) => !a.acknowledged_at).length
  const processedCount = alerts.filter((a) => a.acknowledged_at).length

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>
        告警中心
      </Title>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Statistic
              title="今日告警"
              value={stats.total_today}
              valueStyle={{ color: '#cf1322', textAlign: 'center' }}
              prefix={<AlertOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Statistic
              title="本周告警"
              value={stats.total_week}
              valueStyle={{ textAlign: 'center' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Statistic
              title="未处理"
              value={pendingCount}
              valueStyle={{ color: '#faad14', textAlign: 'center' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Statistic
              title="已处理"
              value={processedCount}
              valueStyle={{ color: '#52c41a', textAlign: 'center' }}
            />
          </Card>
        </Col>
      </Row>

      <Card>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginBottom: 16,
            flexWrap: 'wrap',
            gap: 8,
          }}
        >
          <Space wrap>
            <Select
              placeholder="违规类型"
              allowClear
              style={{ width: 150 }}
              onChange={(v) => updateFilter('violation_type', v)}
              options={Object.entries(violationNames).map(([k, v]) => ({
                value: k,
                label: v,
              }))}
            />
            <Select
              placeholder="级别"
              allowClear
              style={{ width: 100 }}
              onChange={(v) => updateFilter('level', v)}
              options={[
                { value: 'critical', label: '严重' },
                { value: 'warning', label: '警告' },
                { value: 'info', label: '提示' },
              ]}
            />
            <RangePicker
              onChange={(dates) => {
                updateFilter('start_time', dates?.[0]?.toISOString())
                updateFilter('end_time', dates?.[1]?.toISOString())
              }}
            />
          </Space>
          <Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={fetchAlerts}
              loading={loading}
            >
              刷新
            </Button>
            <Button
              type="primary"
              icon={<CheckOutlined />}
              onClick={() => handleAcknowledge()}
              loading={acknowledging}
              disabled={selectedKeys.length === 0}
            >
              批量确认 ({selectedKeys.length})
            </Button>
          </Space>
        </div>

        <Table<Alert>
          rowSelection={{
            selectedRowKeys: selectedKeys,
            onChange: (keys) => setSelectedKeys(keys as string[]),
          }}
          columns={columns}
          dataSource={alerts}
          rowKey="alert_id"
          loading={loading}
          pagination={{
            current: page,
            total,
            pageSize: 20,
            onChange: (p) => setPage(p),
            showTotal: (t) => `共 ${t} 条`,
            showSizeChanger: false,
          }}
          locale={{ emptyText: '暂无告警数据' }}
        />
      </Card>
    </div>
  )
}
