import { Card, Typography, Empty } from 'antd'
import { BarChartOutlined } from '@ant-design/icons'

const { Title } = Typography

export default function Reports() {
  return (
    <div>
      <Title level={4}>数据报表</Title>
      <Card>
        <Empty
          image={<BarChartOutlined style={{ fontSize: 64, color: '#ccc' }} />}
          description="数据报表功能开发中，敬请期待..."
        />
      </Card>
    </div>
  )
}
