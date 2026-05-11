import { useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Button, Avatar, Dropdown, Typography } from 'antd'
import {
  DashboardOutlined,
  VideoCameraOutlined,
  AlertOutlined,
  CameraOutlined,
  BarChartOutlined,
  SettingOutlined,
  UserOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/store/authStore'

const { Sider, Content } = Layout
const { Text } = Typography

const menuItems = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/monitor', icon: <VideoCameraOutlined />, label: '实时监控' },
  { key: '/alerts', icon: <AlertOutlined />, label: '告警中心' },
  { key: '/cameras', icon: <CameraOutlined />, label: '摄像头管理' },
  { key: '/reports', icon: <BarChartOutlined />, label: '数据报表' },
  { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
]

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuthStore()

  return (
    <Layout style={{ minHeight: '100vh', background: '#f5f7fa' }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        theme="light"
        width={220}
        style={{
          borderRight: '1px solid #e8eaed',
          background: '#fff',
        }}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderBottom: '1px solid #e8eaed',
            padding: '0 16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: 'linear-gradient(135deg, #1677ff 0%, #4096ff 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <VideoCameraOutlined style={{ color: '#fff', fontSize: 16 }} />
            </div>
            {!collapsed && (
              <Text strong style={{ fontSize: 16, color: '#1d2129' }}>
                后厨智能监测
              </Text>
            )}
          </div>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ borderRight: 'none', padding: '8px 0' }}
        />
      </Sider>
      <Layout>
        <div
          style={{
            height: 56,
            background: '#fff',
            borderBottom: '1px solid #e8eaed',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 24px',
          }}
        >
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            style={{ color: '#4e5969' }}
          />
          <Dropdown
            menu={{
              items: [
                {
                  key: 'user',
                  label: (
                    <div style={{ padding: '4px 0' }}>
                      <div style={{ fontWeight: 500 }}>
                        {user?.username || '管理员'}
                      </div>
                      <div style={{ fontSize: 12, color: '#86909c' }}>
                        {user?.email || 'admin@system.com'}
                      </div>
                    </div>
                  ),
                  disabled: true,
                },
                { type: 'divider' },
                {
                  key: 'logout',
                  icon: <LogoutOutlined />,
                  label: '退出登录',
                  onClick: () => {
                    logout()
                    navigate('/login')
                  },
                },
              ],
            }}
          >
            <div
              style={{
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '4px 12px',
                borderRadius: 8,
                transition: 'background 0.2s',
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = '#f2f3f5')
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = 'transparent')
              }
            >
              <Avatar
                size={32}
                icon={<UserOutlined />}
                style={{ background: '#1677ff' }}
              />
              <Text style={{ color: '#1d2129' }}>
                {user?.username || '管理员'}
              </Text>
            </div>
          </Dropdown>
        </div>
        <Content
          style={{
            margin: 20,
            padding: 20,
            background: '#fff',
            borderRadius: 12,
            minHeight: 280,
            boxShadow: '0 1px 2px rgba(0, 0, 0, 0.04)',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
