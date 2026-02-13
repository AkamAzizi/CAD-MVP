import { useCallback, useEffect, useState } from 'react'

const API_BASE = '/api'

type ReportPanelProps = {
  assemblyId: string
}

type ReportSummary = {
  overview: {
    total_parts: number
    unique_parts: number
    complexity_score_0_100: number
  }
  health_check: {
    score_0_100: number
    warnings: string[]
  }
  insights: Array<{
    severity: 'info' | 'warn' | 'risk'
    title: string
  }>
}

export function ReportPanel({ assemblyId }: ReportPanelProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reportSummary, setReportSummary] = useState<ReportSummary | null>(null)
  const [hasReport, setHasReport] = useState(false)

  // Check if report exists
  useEffect(() => {
    fetch(`${API_BASE}/assemblies/${assemblyId}/report`)
      .then((r) => {
        if (r.ok) {
          setHasReport(true)
          return r.json()
        }
        return null
      })
      .then((meta) => {
        if (meta) {
          // Try to load report summary
          fetch(`${API_BASE}/assemblies/report`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ assembly_id: assemblyId, format: 'json' }),
          })
            .then((r) => r.ok ? r.json() : null)
            .then((report) => {
              if (report) {
                setReportSummary({
                  overview: report.overview,
                  health_check: report.health_check,
                  insights: report.insights || [],
                })
              }
            })
            .catch(() => {
              // Ignore errors when loading summary
            })
        }
      })
      .catch(() => {
        // Report doesn't exist yet
        setHasReport(false)
      })
  }, [assemblyId])

  const generateReport = useCallback(async () => {
    if (loading) return
    setLoading(true)
    setError(null)

    try {
      // First generate JSON to get summary
      const jsonRes = await fetch(`${API_BASE}/assemblies/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assembly_id: assemblyId, format: 'json' }),
      })

      if (!jsonRes.ok) {
        const text = await jsonRes.text()
        let detail = text
        try {
          const j = JSON.parse(text)
          detail = j.detail || text
        } catch {
          // use raw text
        }
        throw new Error(detail)
      }

      const report = await jsonRes.json()
      setReportSummary({
        overview: report.overview,
        health_check: report.health_check,
        insights: report.insights || [],
      })

      // Now generate PDF
      const pdfRes = await fetch(`${API_BASE}/assemblies/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assembly_id: assemblyId, format: 'pdf' }),
      })

      if (!pdfRes.ok) {
        throw new Error('PDF generation failed')
      }

      // Download PDF
      const blob = await pdfRes.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${assemblyId}_report.pdf`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)

      setHasReport(true)
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [assemblyId, loading])

  const downloadPDF = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/assemblies/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assembly_id: assemblyId, format: 'pdf' }),
      })

      if (!res.ok) {
        throw new Error('Failed to download PDF')
      }

      const blob = await res.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${assemblyId}_report.pdf`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg)
    }
  }, [assemblyId])

  const healthScoreColor = reportSummary
    ? reportSummary.health_check.score_0_100 < 50
      ? '#e74c3c'
      : reportSummary.health_check.score_0_100 < 70
      ? '#f39c12'
      : '#27ae60'
    : '#95a5a6'

  return (
    <div className="report-panel">
      <h2>Engineering Report</h2>
      {!hasReport && !loading && (
        <div className="report-generate">
          <p>Generate an engineering report with insights, BOM, and health analysis.</p>
          <button
            type="button"
            className="btn btn-primary"
            onClick={generateReport}
            disabled={loading}
          >
            {loading ? 'Generating...' : 'Generate Report'}
          </button>
        </div>
      )}
      {loading && (
        <div className="report-loading">
          <p>Generating report...</p>
        </div>
      )}
      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}
      {hasReport && reportSummary && (
        <div className="report-summary">
          <div className="report-metrics">
            <div className="metric">
              <div className="metric-label">Total Parts</div>
              <div className="metric-value">{reportSummary.overview.total_parts}</div>
            </div>
            <div className="metric">
              <div className="metric-label">Unique Parts</div>
              <div className="metric-value">{reportSummary.overview.unique_parts}</div>
            </div>
            <div className="metric">
              <div className="metric-label">Complexity</div>
              <div className="metric-value">{reportSummary.overview.complexity_score_0_100}/100</div>
            </div>
            <div className="metric">
              <div className="metric-label">Health Score</div>
              <div className="metric-value" style={{ color: healthScoreColor }}>
                {reportSummary.health_check.score_0_100}/100
              </div>
            </div>
          </div>
          {reportSummary.insights.length > 0 && (
            <div className="report-insights">
              <h3>Insights ({reportSummary.insights.length})</h3>
              <ul>
                {reportSummary.insights.slice(0, 5).map((insight, i) => (
                  <li key={i} className={`insight-${insight.severity}`}>
                    <strong>{insight.severity.toUpperCase()}:</strong> {insight.title}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {reportSummary.health_check.warnings.length > 0 && (
            <div className="report-warnings">
              <h3>Warnings</h3>
              <ul>
                {reportSummary.health_check.warnings.slice(0, 5).map((warning, i) => (
                  <li key={i}>{warning}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="report-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={downloadPDF}
              disabled={loading}
            >
              Download PDF
            </button>
            <button
              type="button"
              className="btn btn-outline"
              onClick={generateReport}
              disabled={loading}
            >
              Regenerate
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
