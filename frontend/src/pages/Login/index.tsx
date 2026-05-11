import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Form, Input, Button, Typography, message } from 'antd'
import {
  UserOutlined,
  LockOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons'
import request from '@/utils/request'
import { useAuthStore } from '@/store/authStore'

const { Title, Text } = Typography

export default function Login() {
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      const res = await request.post('/auth/login', values)
      const { access_token, user_info } = res.data
      setAuth(access_token, user_info)
      message.success('登录成功')
      navigate('/dashboard')
    } catch {
      // 错误已在拦截器处理
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        background: '#f5f7fa',
      }}
    >
      {/* 左侧装饰区域 */}
      <div
        style={{
          flex: 1,
          background: 'linear-gradient(135deg, #1677ff 0%, #4096ff 100%)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 48,
        }}
      >
        <div style={{ textAlign: 'center', color: '#fff' }}>
          <div
            style={{
              width: 80,
              height: 80,
              borderRadius: 20,
              background: 'rgba(255, 255, 255, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 24px',
            }}
          >
            <VideoCameraOutlined style={{ fontSize: 40, color: '#fff' }} />
          </div>
          <Title level={2} style={{ color: '#fff', margin: '0 0 8px' }}>
            智瞳检测系统
          </Title>
          <Text style={{ color: 'rgba(255, 255, 255, 0.85)', fontSize: 16 }}>
            企业级后厨安全管控平台
          </Text>
          <div
            style={{
              marginTop: 48,
              display: 'flex',
              gap: 48,
              color: 'rgba(255, 255, 255, 0.9)',
            }}
          >
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 32, fontWeight: 600 }}>AI</div>
              <div style={{ fontSize: 13, marginTop: 4 }}>智能检测</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 32, fontWeight: 600 }}>24/7</div>
              <div style={{ fontSize: 13, marginTop: 4 }}>实时监控</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 32, fontWeight: 600 }}>100%</div>
              <div style={{ fontSize: 13, marginTop: 4 }}>安全合规</div>
            </div>
          </div>
        </div>
      </div>

      {/* 右侧登录表单 */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 48,
        }}
      >
        <div style={{ width: '100%', maxWidth: 400 }}>
          <div style={{ marginBottom: 40 }}>
            <Title level={3} style={{ margin: '0 0 8px', color: '#1d2129' }}>
              欢迎回来
            </Title>
            <Text type="secondary">请登录您的账号以继续</Text>
          </div>

          <Form
            onFinish={onFinish}
            layout="vertical"
            size="large"
            requiredMark={false}
          >
            <Form.Item
              name="username"
              label="用户名"
              rules={[{ required: true, message: '请输入用户名' }]}
            >
              <Input
                prefix={<UserOutlined style={{ color: '#c9cdd4' }} />}
                placeholder="请输入用户名"
                style={{ borderRadius: 8 }}
              />
            </Form.Item>
            <Form.Item
              name="password"
              label="密码"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password
                prefix={<LockOutlined style={{ color: '#c9cdd4' }} />}
                placeholder="请输入密码"
                style={{ borderRadius: 8 }}
              />
            </Form.Item>
            <Form.Item style={{ marginTop: 32 }}>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                style={{
                  height: 48,
                  borderRadius: 8,
                  fontSize: 16,
                  fontWeight: 500,
                }}
              >
                登 录
              </Button>
            </Form.Item>
          </Form>

          <div
            style={{
              marginTop: 24,
              padding: '16px 20px',
              background: '#f7f8fa',
              borderRadius: 8,
              textAlign: 'center',
            }}
          >
            <Text type="secondary" style={{ fontSize: 13 }}>
              默认管理员账号
            </Text>
            <div style={{ marginTop: 8 }}>
              <Text code style={{ marginRight: 16 }}>
                admin
              </Text>
              <Text code>admin123</Text>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
