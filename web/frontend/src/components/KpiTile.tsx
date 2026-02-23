type KpiTileProps = {
  label: string
  value: string | number
  badge?: string
  badgeVariant?: 'default' | 'success' | 'warning' | 'error'
  priority?: 'primary' | 'secondary' | 'tertiary'
}

export function KpiTile({ label, value, badge, badgeVariant = 'default', priority = 'secondary' }: KpiTileProps) {
  return (
    <div className={`kpi-tile kpi-tile-${priority}`}>
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{label}</div>
      {badge && (
        <div className={`kpi-badge kpi-badge-${badgeVariant}`}>{badge}</div>
      )}
    </div>
  )
}
