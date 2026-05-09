import { Card, Typography, Empty } from 'antd'
import { SettingOutlined } from '@ant-design/icons'

const { Title } = Typography

export default function Settings() {
  return (
    <div>
      <Title level={4}>系统设置</Title>
      <Card>
        <Empty
          image={<SettingOutlined style={{ fontSize: 64, color: '#ccc' }} />}
          description="系统设置功能开发中，敬请期待..."
        />
      </Card>
    </div>
  )
}
