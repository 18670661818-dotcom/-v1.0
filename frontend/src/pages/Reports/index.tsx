import { useState, useEffect, useCallback } from 'react'
import {
  Card,
  Row,
  Col,
  DatePicker,
  Select,
  Button,
  Table,
  Statistic,
  Typography,
  Space,
  Tabs,
  message,
  Empty,
  Tag,
} from 'antd'
import {
  DownloadOutlined,
  ReloadOutlined,
  AlertOutlined,
  CameraOutlined,
  CheckCircleOutlined,
  WarningOutlined,
  BarChartOutlined,
  PieChartOutlined,
  LineChartOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import request from '@/utils/request'
import dayjs from 'dayjs'

const { Title, Text } = Typography
const { RangePicker } = DatePicker

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
  chef_uniform: '穿工作服',
  chef_hat: '戴厨师帽',
  no_chef_uniform: '未穿工作服',
  no_chef_hat: '未戴厨师帽',
}

interface ReportData {
  total_alerts: number
  critical_alerts: number
  warning_alerts: number
  acknowledged_rate: number
  avg_response_time: number
  by_type: Record<string, number>
  by_camera: Record<string, number>
  by_hour: { hour: number; count: number }[]
  trend: { date: string; count: number }[]
  top_violations: { type: string; count: number; percentage: number }[]
  camera_stats: {
    camera_id: string
    name: string
    total: number
    critical: number
    online_rate: number
  }[]
}

const initialData: ReportData = {
  total_alerts: 0,
  critical_alerts: 0,
  warning_alerts: 0,
  acknowledged_rate: 0,
  avg_response_time: 0,
  by_type: {},
  by_camera: {},
  by_hour: [],
  trend: [],
  top_violations: [],
  camera_stats: [],
}

export default function Reports() {
  const [loading, setLoading] = useState(false)
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    dayjs().subtract(7, 'day'),
    dayjs(),
  ])
  const [selectedCamera, setSelectedCamera] = useState<string>()
  const [reportData, setReportData] = useState<ReportData>(initialData)
  const [cameras, setCameras] = useState<{ value: string; label: string }[]>([])
  const [activeTab, setActiveTab] = useState('overview')

  // 获取摄像头列表
  const fetchCameras = useCallback(async () => {
    try {
      const res = await request.get('/cameras/')
      const camList = (res.data || []).map((c: any) => ({
        value: c.camera_id,
        label: c.name,
      }))
      setCameras(camList)
    } catch (error) {
      console.error('获取摄像头列表失败:', error)
    }
  }, [])

  // 获取报表数据
  const fetchReportData = useCallback(async () => {
    setLoading(true)
    try {
      const params: any = {
        start_date: dateRange[0].format('YYYY-MM-DD'),
        end_date: dateRange[1].format('YYYY-MM-DD'),
      }
      if (selectedCamera) {
        params.camera_id = selectedCamera
      }

      const res = await request.get('/reports/summary', { params })
      setReportData(res.data || initialData)
    } catch (error) {
      console.error('获取报表数据失败:', error)
      message.error('获取报表数据失败')
    } finally {
      setLoading(false)
    }
  }, [dateRange, selectedCamera])

  useEffect(() => {
    fetchCameras()
  }, [fetchCameras])

  useEffect(() => {
    fetchReportData()
  }, [fetchReportData])

  // 导出报表
  const handleExport = async (format: 'csv' | 'excel') => {
    try {
      const params = {
        start_date: dateRange[0].format('YYYY-MM-DD'),
        end_date: dateRange[1].format('YYYY-MM-DD'),
        camera_id: selectedCamera,
        format,
      }
      const res = await request.get('/reports/export', {
        params,
        responseType: 'blob',
      })

      const blob = new Blob([res.data])
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `report_${dateRange[0].format('YYYYMMDD')}_${dateRange[1].format('YYYYMMDD')}.${format}`
      a.click()
      window.URL.revokeObjectURL(url)
      message.success('报表导出成功')
    } catch (error) {
      console.error('导出报表失败:', error)
      message.error('导出报表失败')
    }
  }

  // 趋势图配置
  const trendOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 50, right: 20, top: 30, bottom: 30 },
    xAxis: {
      type: 'category' as const,
      data: reportData.trend.map((t) => dayjs(t.date).format('MM-DD')),
      axisLabel: { fontSize: 12 },
    },
    yAxis: {
      type: 'value' as const,
      axisLabel: { fontSize: 12 },
    },
    series: [
      {
        data: reportData.trend.map((t) => t.count),
        type: 'line',
        smooth: true,
        areaStyle: { opacity: 0.15 },
        itemStyle: { color: '#1677ff' },
        lineStyle: { width: 2 },
        name: '告警数量',
      },
    ],
  }

  // 饼图配置
  const pieOption = {
    tooltip: { trigger: 'item' as const },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: { fontSize: 12 },
    },
    series: [
      {
        type: 'pie' as const,
        radius: ['40%', '70%'],
        avoidLabelOverlap: true,
        label: { show: false },
        data: Object.entries(reportData.by_type).map(([name, value]) => ({
          name: violationNames[name] || name,
          value,
        })),
      },
    ],
  }

  // 时段分布图配置
  const hourOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 50, right: 20, top: 30, bottom: 30 },
    xAxis: {
      type: 'category' as const,
      data: reportData.by_hour.map((h) => `${h.hour}:00`),
      axisLabel: { fontSize: 12 },
    },
    yAxis: {
      type: 'value' as const,
      axisLabel: { fontSize: 12 },
    },
    series: [
      {
        data: reportData.by_hour.map((h) => h.count),
        type: 'bar',
        itemStyle: {
          color: '#1677ff',
          borderRadius: [4, 4, 0, 0],
        },
        name: '告警数量',
      },
    ],
  }

  // 摄像头排行配置
  const cameraRankOption = {
    tooltip: {
      trigger: 'axis' as const,
      axisPointer: { type: 'shadow' as const },
    },
    grid: { left: 120, right: 40, top: 20, bottom: 20 },
    xAxis: {
      type: 'value' as const,
      axisLabel: { fontSize: 12 },
    },
    yAxis: {
      type: 'category' as const,
      data: reportData.camera_stats.slice(0, 10).map((c) => c.name),
      axisLabel: { fontSize: 12 },
    },
    series: [
      {
        type: 'bar' as const,
        data: reportData.camera_stats.slice(0, 10).map((c) => c.total),
        itemStyle: {
          color: '#1677ff',
          borderRadius: [0, 4, 4, 0],
        },
        name: '告警数量',
      },
    ],
  }

  // 统计卡片
  const StatCards = () => (
    <Row gutter={16}>
      <Col span={6}>
        <Card size="small">
          <Statistic
            title="总告警数"
            value={reportData.total_alerts}
            prefix={<AlertOutlined />}
            valueStyle={{ color: '#1677ff' }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small">
          <Statistic
            title="严重告警"
            value={reportData.critical_alerts}
            prefix={<WarningOutlined />}
            valueStyle={{ color: '#ff4d4f' }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small">
          <Statistic
            title="处理率"
            value={reportData.acknowledged_rate}
            suffix="%"
            prefix={<CheckCircleOutlined />}
            valueStyle={{ color: '#52c41a' }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small">
          <Statistic
            title="平均响应时间"
            value={reportData.avg_response_time}
            suffix="分钟"
            prefix={<CameraOutlined />}
          />
        </Card>
      </Col>
    </Row>
  )

  // 表格列配置
  const violationColumns = [
    {
      title: '排名',
      key: 'rank',
      width: 60,
      render: (_: any, __: any, index: number) => index + 1,
    },
    {
      title: '违规类型',
      dataIndex: 'type',
      key: 'type',
      render: (t: string) => violationNames[t] || t,
    },
    {
      title: '次数',
      dataIndex: 'count',
      key: 'count',
      width: 100,
      sorter: (a: any, b: any) => a.count - b.count,
    },
    {
      title: '占比',
      dataIndex: 'percentage',
      key: 'percentage',
      width: 100,
      render: (v: number) => `${v.toFixed(1)}%`,
    },
  ]

  const cameraColumns = [
    {
      title: '摄像头',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: '总告警',
      dataIndex: 'total',
      key: 'total',
      width: 100,
      sorter: (a: any, b: any) => a.total - b.total,
    },
    {
      title: '严重告警',
      dataIndex: 'critical',
      key: 'critical',
      width: 100,
      render: (v: number) => <Tag color={v > 0 ? 'red' : 'default'}>{v}</Tag>,
    },
    {
      title: '在线率',
      dataIndex: 'online_rate',
      key: 'online_rate',
      width: 100,
      render: (v: number) => `${v.toFixed(1)}%`,
    },
  ]

  const tabItems = [
    {
      key: 'overview',
      label: (
        <span>
          <BarChartOutlined />
          数据概览
        </span>
      ),
      children: (
        <div>
          <StatCards />
          <Row gutter={16} style={{ marginTop: 16 }}>
            <Col span={16}>
              <Card title="告警趋势" size="small">
                {reportData.trend.length > 0 ? (
                  <ReactECharts option={trendOption} style={{ height: 300 }} />
                ) : (
                  <Empty description="暂无数据" />
                )}
              </Card>
            </Col>
            <Col span={8}>
              <Card title="违规类型分布" size="small">
                {Object.keys(reportData.by_type).length > 0 ? (
                  <ReactECharts option={pieOption} style={{ height: 300 }} />
                ) : (
                  <Empty description="暂无数据" />
                )}
              </Card>
            </Col>
          </Row>
        </div>
      ),
    },
    {
      key: 'detail',
      label: (
        <span>
          <LineChartOutlined />
          详细分析
        </span>
      ),
      children: (
        <Row gutter={16}>
          <Col span={12}>
            <Card title="时段分布" size="small">
              {reportData.by_hour.length > 0 ? (
                <ReactECharts option={hourOption} style={{ height: 300 }} />
              ) : (
                <Empty description="暂无数据" />
              )}
            </Card>
          </Col>
          <Col span={12}>
            <Card title="摄像头排行" size="small">
              {reportData.camera_stats.length > 0 ? (
                <ReactECharts
                  option={cameraRankOption}
                  style={{ height: 300 }}
                />
              ) : (
                <Empty description="暂无数据" />
              )}
            </Card>
          </Col>
        </Row>
      ),
    },
    {
      key: 'ranking',
      label: (
        <span>
          <PieChartOutlined />
          排行统计
        </span>
      ),
      children: (
        <Row gutter={16}>
          <Col span={12}>
            <Card title="违规类型排行" size="small">
              <Table
                dataSource={reportData.top_violations}
                columns={violationColumns}
                rowKey="type"
                size="small"
                pagination={false}
                locale={{ emptyText: '暂无数据' }}
              />
            </Card>
          </Col>
          <Col span={12}>
            <Card title="摄像头告警排行" size="small">
              <Table
                dataSource={reportData.camera_stats}
                columns={cameraColumns}
                rowKey="camera_id"
                size="small"
                pagination={false}
                locale={{ emptyText: '暂无数据' }}
              />
            </Card>
          </Col>
        </Row>
      ),
    },
  ]

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
          数据报表
        </Title>
        <Space>
          <RangePicker
            value={dateRange}
            onChange={(dates) => {
              if (dates && dates[0] && dates[1]) {
                setDateRange([dates[0], dates[1]])
              }
            }}
            allowClear={false}
          />
          <Select
            placeholder="全部摄像头"
            allowClear
            style={{ width: 180 }}
            value={selectedCamera}
            onChange={setSelectedCamera}
            options={cameras}
          />
          <Button
            icon={<ReloadOutlined />}
            onClick={fetchReportData}
            loading={loading}
          >
            刷新
          </Button>
          <Button
            icon={<DownloadOutlined />}
            onClick={() => handleExport('excel')}
          >
            导出Excel
          </Button>
        </Space>
      </div>

      <Card>
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
      </Card>
    </div>
  )
}
