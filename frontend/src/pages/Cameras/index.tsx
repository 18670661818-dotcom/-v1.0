import { useEffect, useState, useCallback } from 'react'
import {
  Card,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Switch,
  Space,
  Tag,
  message,
  Popconfirm,
  Typography,
  Tooltip,
} from 'antd'
import {
  PlusOutlined,
  ReloadOutlined,
  EditOutlined,
  DeleteOutlined,
  LinkOutlined,
  WifiOutlined,
  ExperimentOutlined,
} from '@ant-design/icons'
import request from '@/utils/request'
import dayjs from 'dayjs'
import type {
  Camera,
  CameraCreateParams,
  CameraUpdateParams,
  RTSPTestResult,
} from '@/types'

const { Title } = Typography

export default function Cameras() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingCamera, setEditingCamera] = useState<Camera | null>(null)
  const [testing, setTesting] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [form] = Form.useForm()

  // 获取摄像头列表
  const fetchCameras = useCallback(async () => {
    setLoading(true)
    try {
      const res = await request.get<Camera[]>('/cameras/')
      setCameras(res.data || [])
    } catch (error) {
      console.error('获取摄像头列表失败:', error)
      message.error('获取摄像头列表失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchCameras()
  }, [fetchCameras])

  // 添加摄像头
  const handleAdd = () => {
    setEditingCamera(null)
    form.resetFields()
    form.setFieldsValue({ enabled: true })
    setModalOpen(true)
  }

  // 编辑摄像头
  const handleEdit = (record: Camera) => {
    setEditingCamera(record)
    form.setFieldsValue(record)
    setModalOpen(true)
  }

  // 删除摄像头
  const handleDelete = async (cameraId: string) => {
    try {
      await request.delete(`/cameras/${cameraId}`)
      message.success('删除成功')
      fetchCameras()
    } catch (error) {
      console.error('删除摄像头失败:', error)
    }
  }

  // 提交表单
  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)

      if (editingCamera) {
        await request.put<Camera>(
          `/cameras/${editingCamera.camera_id}`,
          values as CameraUpdateParams,
        )
        message.success('更新成功')
      } else {
        await request.post<Camera>('/cameras/', values as CameraCreateParams)
        message.success('添加成功')
      }
      setModalOpen(false)
      fetchCameras()
    } catch (error) {
      console.error('保存摄像头失败:', error)
    } finally {
      setSubmitting(false)
    }
  }

  // 测试单个摄像头
  const handleTest = async (cameraId: string) => {
    const camera = cameras.find((c) => c.camera_id === cameraId)
    if (!camera) return

    setTesting(cameraId)
    try {
      const res = await request.post<RTSPTestResult>(
        '/rtsp-test/single',
        null,
        {
          params: {
            camera_id: cameraId,
            rtsp_url: camera.rtsp_url,
            timeout: 10,
          },
        },
      )

      const result = res.data
      if (result?.success) {
        message.success(
          `连接成功 | ${result.width}x${result.height} | ${result.fps?.toFixed(1)}fps | ${result.codec}`,
        )
      } else {
        message.error(`连接失败: ${result?.error_message || '未知错误'}`)
      }
      // 刷新列表以获取最新状态
      fetchCameras()
    } catch (error) {
      console.error('测试摄像头失败:', error)
      message.error('测试请求失败')
    } finally {
      setTesting(null)
    }
  }

  // 批量测试所有摄像头
  const handleBatchTest = async () => {
    if (cameras.length === 0) {
      message.warning('没有摄像头需要测试')
      return
    }

    setTesting('batch')
    try {
      const res = await request.post('/rtsp-test/batch', {
        timeout: 10,
        max_workers: 5,
      })

      const data = res.data
      message.success(`测试完成: ${data.success}/${data.total} 成功`)
      fetchCameras()
    } catch (error) {
      console.error('批量测试失败:', error)
      message.error('批量测试失败')
    } finally {
      setTesting(null)
    }
  }

  // 表格列配置
  const columns = [
    {
      title: '摄像头ID',
      dataIndex: 'camera_id',
      key: 'id',
      width: 120,
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 180,
      ellipsis: true,
    },
    {
      title: 'RTSP地址',
      dataIndex: 'rtsp_url',
      key: 'url',
      ellipsis: true,
      render: (url: string) => (
        <Tooltip title={url}>
          <span style={{ fontSize: 12, color: '#666' }}>{url}</span>
        </Tooltip>
      ),
    },
    {
      title: '位置',
      dataIndex: 'location',
      key: 'loc',
      width: 150,
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (s: Camera['status']) => {
        const statusMap = {
          online: { color: 'green', text: '在线' },
          offline: { color: 'red', text: '离线' },
          error: { color: 'orange', text: '异常' },
        }
        const status = statusMap[s] || statusMap.offline
        return (
          <Tag color={status.color}>
            <WifiOutlined /> {status.text}
          </Tag>
        )
      },
    },
    {
      title: '启用',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 80,
      render: (v: boolean) => (
        <Tag color={v ? 'blue' : 'default'}>{v ? '是' : '否'}</Tag>
      ),
    },
    {
      title: '上次心跳',
      dataIndex: 'last_heartbeat',
      key: 'hb',
      width: 160,
      render: (t: string | null) =>
        t ? dayjs(t).format('MM-DD HH:mm:ss') : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 240,
      fixed: 'right' as const,
      render: (_: any, record: Camera) => (
        <Space>
          <Button
            size="small"
            icon={<LinkOutlined />}
            loading={testing === record.camera_id}
            onClick={() => handleTest(record.camera_id)}
          >
            测试
          </Button>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除？"
            description="删除后不可恢复"
            onConfirm={() => handleDelete(record.camera_id)}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

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
          摄像头管理
        </Title>
        <Space>
          <Button
            icon={<ExperimentOutlined />}
            onClick={handleBatchTest}
            loading={testing === 'batch'}
          >
            批量测试
          </Button>
          <Button
            icon={<ReloadOutlined />}
            onClick={fetchCameras}
            loading={loading}
          >
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
            添加摄像头
          </Button>
        </Space>
      </div>

      <Card>
        <Table<Camera>
          columns={columns}
          dataSource={cameras}
          rowKey="camera_id"
          loading={loading}
          scroll={{ x: 1200 }}
          pagination={{
            pageSize: 20,
            showTotal: (total) => `共 ${total} 个摄像头`,
          }}
          locale={{ emptyText: '暂无摄像头数据' }}
        />
      </Card>

      <Modal
        title={editingCamera ? '编辑摄像头' : '添加摄像头'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={submitting}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="camera_id"
            label="摄像头ID"
            rules={[
              { required: true, message: '请输入摄像头ID' },
              {
                pattern: /^[a-zA-Z0-9_-]+$/,
                message: '只允许字母、数字、下划线和连字符',
              },
            ]}
          >
            <Input placeholder="如: cam_001" disabled={!!editingCamera} />
          </Form.Item>
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder="如: 食堂1号后厨-A区" />
          </Form.Item>
          <Form.Item
            name="rtsp_url"
            label="RTSP地址"
            rules={[
              { required: true, message: '请输入RTSP地址' },
              { type: 'url', message: '请输入有效的URL地址' },
            ]}
          >
            <Input placeholder="rtsp://..." />
          </Form.Item>
          <Form.Item name="location" label="位置">
            <Input placeholder="如: 第一食堂后厨" />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
