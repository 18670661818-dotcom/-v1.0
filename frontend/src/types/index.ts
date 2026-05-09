/**
 * 前端类型定义文件
 */

// ==================== 用户相关 ====================
export interface User {
  id: number
  username: string
  email: string
  company_name: string
  role: 'admin' | 'manager' | 'viewer'
  is_active: boolean
  last_login?: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user_info: User
}

// ==================== 摄像头相关 ====================
export interface Camera {
  id: number
  camera_id: string
  name: string
  rtsp_url: string
  location: string
  status: 'online' | 'offline' | 'error'
  enabled: boolean
  last_heartbeat?: string
  alerts_count: number
}

export interface CameraCreateParams {
  camera_id: string
  name: string
  rtsp_url: string
  location?: string
  enabled?: boolean
}

export interface CameraUpdateParams {
  name?: string
  rtsp_url?: string
  location?: string
  enabled?: boolean
}

export interface CameraStatusSummary {
  total: number
  online: number
  offline: number
  online_rate: string
}

export interface RTSPTestResult {
  success: boolean
  width?: number
  height?: number
  fps?: number
  codec?: string
  error_message?: string
  connect_time_ms?: number
}

// ==================== 告警相关 ====================
export type AlertLevel = 'critical' | 'warning' | 'info'

export interface Alert {
  id: number
  alert_id: string
  camera_id: string
  camera_name: string
  violation_type: string
  violation_name: string
  confidence: number
  level: AlertLevel
  detected_at: string
  acknowledged_at?: string
  image_url?: string
}

export interface AlertListParams {
  camera_id?: string
  violation_type?: string
  level?: AlertLevel
  start_time?: string
  end_time?: string
  acknowledged?: boolean
  page?: number
  page_size?: number
}

export interface AlertListResponse {
  total: number
  page: number
  page_size: number
  total_pages: number
  items: Alert[]
}

export interface AlertStats {
  total_today: number
  total_week: number
  by_type: Record<string, number>
  by_camera: Record<string, number>
  trend: { date: string; count: number }[]
}

// ==================== 仪表盘相关 ====================
export interface DashboardStats {
  total_cameras: number
  online_cameras: number
  total_alerts: number
  pending_alerts: number
  critical_alerts: number
  system_uptime: number
}

export interface CameraStats {
  total: number
  online: number
  offline: number
  error: number
  maintenance: number
}

export interface AlertStatsDetailed {
  total: number
  pending: number
  acknowledged: number
  resolved: number
  by_severity: Record<string, number>
}

// ==================== 通用响应 ====================
export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  message?: string
  error?: string
}

export interface PaginatedResponse<T> {
  total: number
  page: number
  page_size: number
  total_pages: number
  items: T[]
}

// ==================== 表格相关 ====================
export interface TableColumn {
  title: string
  dataIndex: string
  key: string
  width?: number
  fixed?: 'left' | 'right'
  ellipsis?: boolean
  render?: (value: any, record: any, index: number) => React.ReactNode
  sorter?: (a: any, b: any) => number
}

// ==================== 图表相关 ====================
export interface ChartData {
  name: string
  value: number
}

export interface TrendData {
  date: string
  count: number
}

export interface EChartsOption {
  tooltip?: any
  xAxis?: any
  yAxis?: any
  series?: any[]
  [key: string]: any
}
