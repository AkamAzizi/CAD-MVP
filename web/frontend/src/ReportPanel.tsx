import { useCallback, useEffect, useState } from 'react'
import { Card } from './components/Card'
import { SectionHeader } from './components/SectionHeader'
import { KpiTile } from './components/KpiTile'

const API_BASE = '/api'

type ReportPanelProps = {
  assemblyId: string
  onReportGenerated?: () => void
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

type ReportMeta = {
  assembly_id: string
  generated_at?: string
  report_pdf_path?: string
}

export function ReportPanel({ assemblyId, onReportGenerated }: ReportPanelProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [reportSummary, setReportSummary] = useState<ReportSummary | null>(null)
  const [hasReport, setHasReport] = useState(false)
  const [reportMeta, setReportMeta] = useState<ReportMeta | null>(null)

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
      .then((meta: ReportMeta | null) => {
        if (meta) {
          setReportMeta(meta)
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
        setReportMeta(null)
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
        throw new Error('PDF-generering misslyckades')
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

      // Refresh metadata
      const metaRes = await fetch(`${API_BASE}/assemblies/${assemblyId}/report`)
      if (metaRes.ok) {
        const meta = await metaRes.json()
        setReportMeta(meta)
      }

      setHasReport(true)
      setSuccessMessage('Rapport klar.')
      setTimeout(() => setSuccessMessage(null), 3000)
      onReportGenerated?.()
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [assemblyId, loading, onReportGenerated])

  const downloadPDF = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/assemblies/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assembly_id: assemblyId, format: 'pdf' }),
      })

      if (!res.ok) {
        throw new Error('Kunde inte ladda ner PDF')
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

  // Helper functions for badges
  const getComplexityBadge = (score: number): { text: string; variant: 'default' | 'success' | 'warning' | 'error' } => {
    if (score < 40) return { text: 'Låg', variant: 'success' }
    if (score < 70) return { text: 'Måttlig', variant: 'warning' }
    return { text: 'Hög', variant: 'error' }
  }

  const getHealthBadge = (score: number): { text: string; variant: 'default' | 'success' | 'warning' | 'error' } => {
    if (score < 60) return { text: 'Behöver granskas', variant: 'error' }
    if (score < 80) return { text: 'OK', variant: 'warning' }
    return { text: 'Bra', variant: 'success' }
  }

  // Executive summary - professional consulting tone
  const getExecutiveSummary = (): string => {
    if (!reportSummary) return ''
    const { total_parts, unique_parts, complexity_score_0_100 } = reportSummary.overview
    const repeated_parts = total_parts - unique_parts
    const repetition_rate = total_parts > 0 ? (repeated_parts / total_parts) * 100 : 0
    
    let complexity_description = ''
    if (complexity_score_0_100 < 40) {
      complexity_description = 'begränsad strukturell variation'
    } else if (complexity_score_0_100 < 70) {
      complexity_description = 'måttlig strukturell variation'
    } else {
      complexity_description = 'ökad strukturell variation'
    }
    
    let consolidation_opportunity = ''
    if (repetition_rate > 50) {
      consolidation_opportunity = 'potentiell optimeringsmöjlighet inom komponentkonsolidering'
    } else if (repetition_rate > 20) {
      consolidation_opportunity = 'begränsad möjlighet till komponentkonsolidering'
    } else {
      consolidation_opportunity = 'låg potential för komponentkonsolidering'
    }
    
    return `Assemblyn består av ${total_parts} komponenter varav ${unique_parts} är unika. Den uppmätta komplexitetsnivån indikerar ${complexity_description} och ${consolidation_opportunity}.`
  }

  // Map insights to professional consulting language
  const mapInsightToProfessional = (insight: { severity: 'info' | 'warn' | 'risk'; title: string }): string => {
    const title = insight.title.toLowerCase()
    
    // Map common patterns to professional language
    if (title.includes('complexity') || title.includes('komplexitet')) {
      if (title.includes('moderate') || title.includes('måttlig')) {
        return 'Strukturell komplexitet över rekommenderad nivå'
      }
      if (title.includes('high') || title.includes('hög')) {
        return 'Hög strukturell komplexitet kräver granskning'
      }
      return 'Strukturell komplexitet identifierad'
    }
    
    if (title.includes('repetition') || title.includes('repetition') || title.includes('upprepning')) {
      return 'Identifierad möjlighet till komponentkonsolidering'
    }
    
    if (title.includes('validation') || title.includes('validering') || title.includes('error')) {
      return 'Valideringsavvikelse identifierad i strukturdata'
    }
    
    if (title.includes('material') || title.includes('material')) {
      return 'Materialdata kräver komplettering'
    }
    
    if (title.includes('missing') || title.includes('saknas')) {
      return 'Ofullständig metadata identifierad'
    }
    
    // Return original if no mapping found, but clean it up
    return insight.title
  }

  // Get repetition grade badge
  const getRepetitionBadge = (): { text: string; variant: 'default' | 'success' | 'warning' | 'error' } => {
    if (!reportSummary) return { text: '—', variant: 'default' }
    const { total_parts, unique_parts } = reportSummary.overview
    const repeated_parts = total_parts - unique_parts
    const repetition_rate = total_parts > 0 ? (repeated_parts / total_parts) * 100 : 0
    
    if (repetition_rate > 50) {
      return { text: 'Hög', variant: 'success' }
    } else if (repetition_rate > 20) {
      return { text: 'Måttlig', variant: 'warning' }
    }
    return { text: 'Låg', variant: 'default' }
  }

  // Split insights by severity
  const infoInsights = reportSummary?.insights.filter(i => i.severity === 'info') || []
  const warnings = [
    ...(reportSummary?.insights.filter(i => i.severity === 'warn' || i.severity === 'risk') || []),
    ...(reportSummary?.health_check.warnings.map(w => ({ severity: 'warn' as const, title: w })) || [])
  ]

  // Open PDF in new tab
  const openPDFInNewTab = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/assemblies/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assembly_id: assemblyId, format: 'pdf' }),
      })
      if (!res.ok) {
        throw new Error('Kunde inte öppna PDF')
      }
      const blob = await res.blob()
      const url = window.URL.createObjectURL(blob)
      window.open(url, '_blank')
      // Clean up after a delay
      setTimeout(() => window.URL.revokeObjectURL(url), 100)
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg)
    }
  }, [assemblyId])

  return (
    <Card>
      <SectionHeader 
        title="Analysrapport" 
        subtitle="Strukturerad översikt, riskbedömning och valideringsstatus"
      />
      {!hasReport && !loading && (
        <div className="report-generate">
          <p>Generera en analysrapport med strukturerad översikt, BOM och riskbedömning.</p>
          <button
            type="button"
            className="btn btn-primary"
            onClick={generateReport}
            disabled={loading}
          >
            {loading ? 'Genererar…' : 'Generera rapport'}
          </button>
        </div>
      )}
      {loading && (
        <div className="report-loading">
          <p>Genererar…</p>
        </div>
      )}
      {error && (
        <div className="error-box" role="alert">
          <div>{error}</div>
          <button
            type="button"
            className="btn btn-outline"
            onClick={generateReport}
            style={{ marginTop: '0.5rem' }}
          >
            Försök igen
          </button>
        </div>
      )}
      {successMessage && (
        <div className="success-box" role="alert">
          {successMessage}
        </div>
      )}
      {hasReport && reportSummary && (
        <div className="report-summary">
          <div className="summary-section">
            <h3>Sammanfattning</h3>
            <p className="summary-subtitle">Strukturell analys baserad på STEP-struktur och metadata.</p>
            <p className="summary-paragraph">{getExecutiveSummary()}</p>
            <p className="summary-methodology">Analys baserad på: strukturell parsning, BOM-extraktion och heuristisk riskbedömning.</p>
          </div>

          <div className="status-assessment-horizontal">
            <div className="status-assessment-item">
              <span className="status-assessment-label">Komplexitet</span>
              <div className="status-assessment-value-group">
                <span className={`status-assessment-value status-assessment-${getComplexityBadge(reportSummary.overview.complexity_score_0_100).variant}`}>
                  {getComplexityBadge(reportSummary.overview.complexity_score_0_100).text}
                </span>
                <span className={`status-assessment-badge status-assessment-badge-${getComplexityBadge(reportSummary.overview.complexity_score_0_100).variant}`}></span>
              </div>
            </div>
            <div className="status-assessment-divider"></div>
            <div className="status-assessment-item">
              <span className="status-assessment-label">Repetitionsgrad</span>
              <div className="status-assessment-value-group">
                <span className={`status-assessment-value status-assessment-${getRepetitionBadge().variant}`}>
                  {getRepetitionBadge().text}
                </span>
                <span className={`status-assessment-badge status-assessment-badge-${getRepetitionBadge().variant}`}></span>
              </div>
            </div>
            <div className="status-assessment-divider"></div>
            <div className="status-assessment-item">
              <span className="status-assessment-label">Valideringsstatus</span>
              <div className="status-assessment-value-group">
                <span className={`status-assessment-value status-assessment-${getHealthBadge(reportSummary.health_check.score_0_100).variant}`}>
                  {getHealthBadge(reportSummary.health_check.score_0_100).text}
                </span>
                <span className={`status-assessment-badge status-assessment-badge-${getHealthBadge(reportSummary.health_check.score_0_100).variant}`}></span>
              </div>
            </div>
          </div>

          <div className="report-metrics">
            <KpiTile
              label="Komplexitet"
              value={`${reportSummary.overview.complexity_score_0_100}/100`}
              badge={getComplexityBadge(reportSummary.overview.complexity_score_0_100).text}
              badgeVariant={getComplexityBadge(reportSummary.overview.complexity_score_0_100).variant}
              priority="primary"
            />
            <KpiTile
              label="Totalt antal delar"
              value={reportSummary.overview.total_parts}
              priority="secondary"
            />
            <KpiTile
              label="Unika delar"
              value={reportSummary.overview.unique_parts}
              priority="secondary"
            />
            <KpiTile
              label="Hälsoscore"
              value={`${reportSummary.health_check.score_0_100}/100`}
              badge={getHealthBadge(reportSummary.health_check.score_0_100).text}
              badgeVariant={getHealthBadge(reportSummary.health_check.score_0_100).variant}
              priority="tertiary"
            />
          </div>

          <div className="report-panels">
            {infoInsights.length > 0 && (
              <div className="report-insights-panel">
                <h3>Strukturell analys</h3>
                <ul>
                  {infoInsights.map((insight, i) => (
                    <li key={i} className={`insight-${insight.severity}`}>
                      {mapInsightToProfessional(insight)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {infoInsights.length === 0 && (
              <div className="report-insights-panel">
                <h3>Strukturell analys</h3>
                <p className="empty-state">Inga strukturella avvikelser identifierade.</p>
              </div>
            )}

            {warnings.length > 0 && (
              <div className="report-warnings-panel">
                <h3>Riskindikatorer</h3>
                <ul>
                  {warnings.map((warning, i) => (
                    <li key={i}>
                      {typeof warning === 'string' 
                        ? warning.includes('validation') || warning.includes('validering')
                          ? 'Valideringsavvikelse identifierad i strukturdata'
                          : warning.includes('error') || warning.includes('fel')
                          ? 'Strukturell avvikelse kräver granskning'
                          : warning
                        : mapInsightToProfessional(warning)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {warnings.length === 0 && (
              <div className="report-warnings-panel">
                <h3>Riskindikatorer</h3>
                <p className="empty-state">Inga riskindikatorer identifierade.</p>
              </div>
            )}
          </div>

          <div className="report-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={downloadPDF}
              disabled={loading}
            >
              Ladda ner PDF
            </button>
            <button
              type="button"
              className="btn btn-outline"
              onClick={openPDFInNewTab}
              disabled={loading}
            >
              Öppna rapport i ny flik
            </button>
            <button
              type="button"
              className="btn btn-outline"
              onClick={generateReport}
              disabled={loading}
            >
              Regenerera
            </button>
          </div>
          {reportMeta?.generated_at && (
            <p className="report-meta">
              Genererad: {new Date(reportMeta.generated_at).toLocaleString('sv-SE')}
            </p>
          )}
        </div>
      )}
    </Card>
  )
}
