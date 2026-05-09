import { useEffect, useState } from 'react'
import {
  Card,
  Row,
  Col,
  Select,
  Button,
  Space,
  Tag,
  Empty,
  Typography,
  Badge,
} from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import request from '@/utils/request'

const { Title } = Typography

type LayoutType = '4' | '9' | '16'

export default function Monitor() {
  const [cameras, setCameras] = useState<any[]>([])
  const [layout, setLayout] = useState<LayoutType>('4')
  const [selectedCam, setSelectedCam] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const cols = layout === '4' ? 2 : layout === '9' ? 3 : 4
  const limit = parseInt(layout)
  const displayCameras = cameras.slice(0, limit)

  const fetchCameras = async () => {
    setLoading(true)
    try {
      const res = await request.get('/cameras/')
      setCameras(res.data || [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCameras()
    const timer = setInterval(fetchCameras, 30000)
    return () => clearInterval(timer)
  }, [])

  // 全屏单个摄像头
  if (selectedCam) {
    const cam = cameras.find((c) => c.camera_id === selectedCam)
    return (
      <div>
        <div
          style={{
            marginBottom: 16,
            display: 'flex',
            alignItems: 'center',
            gap: 12,
          }}
        >
          <Button onClick={() => setSelectedCam(null)}>返回多画面</Button>
          <Title level={4} style={{ margin: 0 }}>
            {cam?.name || selectedCam}
          </Title>
          <Tag color={cam?.status === 'online' ? 'green' : 'red'}>
            {cam?.status === 'online' ? '在线' : '离线'}
          </Tag>
        </div>
        <Card>
          <img
            src={`/api/stream/${selectedCam}`}
            alt={cam?.name}
            style={{
              width: '100%',
              maxHeight: '70vh',
              objectFit: 'contain',
              background: '#000',
              borderRadius: 4,
            }}
            onError={(e) => {
              const target = e.target as HTMLImageElement
              target.style.display = 'none'
            }}
          />
        </Card>
      </div>
    )
  }

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: 16,
        }}
      >
        <Title level={4} style={{ margin: 0 }}>
          实时监控
        </Title>
        <Space>
          <Select
            value={layout}
            onChange={setLayout}
            style={{ width: 140 }}
            options={[
              { value: '4', label: '四宫格 (2x2)' },
              { value: '9', label: '九宫格 (3x3)' },
              { value: '16', label: '十六宫格 (4x4)' },
            ]}
          />
          <Button icon={<ReloadOutlined />} onClick={fetchCameras}>
            刷新
          </Button>
        </Space>
      </div>

      {displayCameras.length === 0 ? (
        <Card>
          <Empty description="暂无摄像头" />
        </Card>
      ) : (
        <Row gutter={[12, 12]}>
          {displayCameras.map((cam) => (
            <Col span={24 / cols} key={cam.camera_id}>
              <Badge.Ribbon
                text={cam.status === 'online' ? '在线' : '离线'}
                color={cam.status === 'online' ? 'green' : 'red'}
              >
                <Card
                  hoverable
                  size="small"
                  onClick={() => setSelectedCam(cam.camera_id)}
                  cover={
                    <img
                      src={`/api/stream/${cam.camera_id}`}
                      alt={cam.name}
                      style={{
                        width: '100%',
                        height: 240,
                        objectFit: 'cover',
                        background: '#000',
                      }}
                      onError={(e) => {
                        const target = e.target as HTMLImageElement
                        target.style.display = 'none'
                      }}
                    />
                  }
                >
                  <Card.Meta
                    title={<span style={{ fontSize: 13 }}>{cam.name}</span>}
                    description={
                      <span style={{ fontSize: 11 }}>{cam.location}</span>
                    }
                  />
                </Card>
              </Badge.Ribbon>
            </Col>
          ))}
        </Row>
      )}
    </div>
  )
}
