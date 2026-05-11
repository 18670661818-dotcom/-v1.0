import { useEffect, useState, useCallback } from 'react'
import {
  Row,
  Col,
  Card,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import {
  CameraOutlined,
  AlertOutlined,
  CheckCircleOutlined,
  ThunderboltOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import request from '@/utils/request'
import dayjs from 'dayjs'
import type {
  Alert,
  AlertStats,
  CameraStatusSummary,
  DashboardStats,
} from '@/types'

const { Title } = Typography

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

// 初始摄像头摘要
const initialCamSummary: CameraStatusSummary = {
  total: 0,
  online: 0,
  offline: 0,
  online_rate: '0%',
}

// 初始仪表盘统计数据
const initialDashboardStats: DashboardStats = {
  total_cameras: 0,
  online_cameras: 0,
  total_alerts: 0,
  pending_alerts: 0,
  critical_alerts: 0,
  system_uptime: 0,
}

export default function Dashboard() {
  const [loading, setLoading] = useState(true)
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [stats, setStats] = useState<AlertStats>(initialStats)
  const [dashboardStats, setDashboardStats] = useState<DashboardStats>(
    initialDashboardStats,
  )
  const [camSummary, setCamSummary] =
    useState<CameraStatusSummary>(initialCamSummary)

  // 获取数据
  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [alertRes, statsRes, camSummaryRes, dashboardStatsRes] =
        await Promise.allSettled([
          request.get('/alerts/', { params: { page_size: 10 } }),
          request.get('/alerts/stats'),
          request.get('/cameras/status/summary'),
          request.get('/dashboard/stats'),
        ])

      if (alertRes.status === 'fulfilled') {
        setAlerts(alertRes.value.data?.items || [])
      } else {
        console.error('获取告警列表失败:', alertRes.reason)
      }

      if (statsRes.status === 'fulfilled') {
        setStats(statsRes.value.data || initialStats)
      } else {
        console.error('获取统计数据失败:', statsRes.reason)
      }

      if (camSummaryRes.status === 'fulfilled') {
        setCamSummary(camSummaryRes.value.data || initialCamSummary)
      } else {
        console.error('获取摄像头摘要失败:', camSummaryRes.reason)
      }

      if (dashboardStatsRes.status === 'fulfilled') {
        setDashboardStats(dashboardStatsRes.value.data || initialDashboardStats)
      } else {
        console.error('获取仪表盘统计数据失败:', dashboardStatsRes.reason)
      }
    } catch (error) {
      console.error('获取仪表盘数据失败:', error)
      message.error('获取仪表盘数据失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    // 设置定时刷新（每30秒）
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [fetchData])

  // 趋势图配置
  const trendData = stats.trend || []
  const trendOption = {
    tooltip: { trigger: 'axis' as const },
    xAxis: {
      type: 'category' as const,
      data: trendData.map((t) => t.date),
      axisLabel: { rotate: 45 },
    },
    yAxis: { type: 'value' as const },
    series: [
      {
        data: trendData.map((t) => t.count),
        type: 'line',
        smooth: true,
        areaStyle: { opacity: 0.3 },
        itemStyle: { color: '#1677ff' },
        name: '告警数量',
      },
    ],
  }

  // 饼图配置
  const pieData = stats.by_type || {}
  const pieOption = {
    tooltip: { trigger: 'item' as const },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
    },
    series: [
      {
        type: 'pie' as const,
        radius: ['40%', '70%'],
        data: Object.entries(pieData).map(([name, value]) => ({
          name: violationNames[name] || name,
          value,
        })),
      },
    ],
  }

  // 表格列配置
  const columns = [
    {
      title: '时间',
      dataIndex: 'detected_at',
      width: 160,
      render: (v: string) => (v ? dayjs(v).format('MM-DD HH:mm:ss') : '-'),
    },
    {
      title: '摄像头',
      dataIndex: 'camera_name',
      width: 140,
      ellipsis: true,
    },
    {
      title: '违规类型',
      dataIndex: 'violation_type',
      render: (v: string) => (
        <Tag color="volcano">{violationNames[v] || v}</Tag>
      ),
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      width: 80,
      render: (v: number) => (v ? (v * 100).toFixed(0) + '%' : '-'),
    },
  ]

  // 计算告警统计
  const pendingAlerts = dashboardStats.pending_alerts
  const processedAlerts =
    dashboardStats.total_alerts - dashboardStats.pending_alerts

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
        }}
      >
        <Title level={4} style={{ margin: 0 }}>
          系统仪表盘
        </Title>
        <ReloadOutlined
          onClick={fetchData}
          style={{ cursor: 'pointer', fontSize: 16 }}
          spin={loading}
        />
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="摄像头总数"
              value={camSummary.total}
              prefix={<CameraOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="在线摄像头"
              value={camSummary.online}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#3f8600' }}
              suffix={`/ ${camSummary.total}`}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="今日告警"
              value={stats.total_today}
              prefix={<AlertOutlined />}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="未处理告警"
              value={pendingAlerts}
              prefix={<AlertOutlined />}
              valueStyle={{ color: pendingAlerts > 0 ? '#faad14' : '#52c41a' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card title="近7天告警趋势">
            {trendData.length > 0 ? (
              <ReactECharts option={trendOption} style={{ height: 300 }} />
            ) : (
              <div
                style={{
                  height: 300,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#999',
                }}
              >
                暂无数据
              </div>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="违规类型分布">
            {Object.keys(pieData).length > 0 ? (
              <ReactECharts option={pieOption} style={{ height: 300 }} />
            ) : (
              <div
                style={{
                  height: 300,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#999',
                }}
              >
                暂无数据
              </div>
            )}
          </Card>
        </Col>
      </Row>

      <Card
        title="最近告警"
        style={{ marginTop: 16 }}
        extra={
          <span style={{ fontSize: 12, color: '#999' }}>
            未处理: {pendingAlerts} | 已处理: {processedAlerts}
          </span>
        }
      >
        <Table<Alert>
          columns={columns}
          dataSource={alerts}
          rowKey="id"
          size="small"
          pagination={false}
          loading={loading}
          locale={{ emptyText: '暂无告警数据' }}
        />
      </Card>
    </div>
  )
}
