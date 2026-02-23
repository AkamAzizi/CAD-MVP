import { useCallback, useEffect, useState } from 'react'
import { ChatPanel } from './ChatPanel'
import { UploadCard } from './UploadCard'
import { ReportPanel } from './ReportPanel'
import { Stepper } from './components/Stepper'
import { ArchitectureModal } from './components/ArchitectureModal'

const API_BASE = '/api'

type Status = 'idle' | 'uploading' | 'processing' | 'ready' | 'error'

type Assembly = { assembly_id: string; label?: string; snapshot_path?: string }

export default function App() {
  const [status, setStatus] = useState<Status>('idle')
  const [assemblyId, setAssemblyId] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [existingAssemblies, setExistingAssemblies] = useState<Assembly[]>([])
  const [hasReport, setHasReport] = useState(false)
  const [showArchitecture, setShowArchitecture] = useState(false)

  const refreshAssemblies = useCallback(() => {
    fetch(`${API_BASE}/assemblies`)
      .then((r) => r.ok ? r.json() : { assemblies: [] })
      .then((data) => setExistingAssemblies(data.assemblies || []))
      .catch(() => setExistingAssemblies([]))
  }, [])

  useEffect(() => {
    refreshAssemblies()
  }, [refreshAssemblies])

  // Check if report exists when assembly is ready
  useEffect(() => {
    if (status === 'ready' && assemblyId) {
      fetch(`${API_BASE}/assemblies/${assemblyId}/report`)
        .then((r) => {
          if (r.ok) {
            setHasReport(true)
          } else {
            setHasReport(false)
          }
        })
        .catch(() => setHasReport(false))
    } else {
      setHasReport(false)
    }
  }, [status, assemblyId])

  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const onReady = useCallback((id: string) => {
    setAssemblyId(id)
    setStatus('ready')
    setErrorMessage(null)
    setSuccessMessage('Assembly bearbetad.')
    setTimeout(() => setSuccessMessage(null), 3000)
  }, [])

  const onError = useCallback((msg: string) => {
    setStatus('error')
    setErrorMessage(msg)
    setAssemblyId(null)
  }, [])

  const onReset = useCallback(() => {
    setStatus('idle')
    setAssemblyId(null)
    setErrorMessage(null)
    setHasReport(false)
  }, [])

  const onReportGenerated = useCallback(() => {
    setHasReport(true)
  }, [])

  // Determine current step for stepper
  const getCurrentStep = (): 1 | 2 | 3 => {
    if (status === 'idle' || status === 'uploading' || status === 'processing') {
      return 1
    }
    if (status === 'ready' && assemblyId && !hasReport) {
      return 2
    }
    if (status === 'ready' && assemblyId && hasReport) {
      return 3
    }
    return 1
  }

  return (
    <div className="app">
      <div className="hero">
        <div className="hero-header">
          <h1>AI-Driven Assembly Analysis Platform</h1>
          <p className="hero-subtitle">Automatiserad BOM, riskanalys och intelligent Q&A för komplexa CAD-assemblies.</p>
          <button
            type="button"
            className="btn-architecture-link"
            onClick={() => setShowArchitecture(true)}
          >
            Visa teknisk översikt
          </button>
        </div>
        <div className="business-value-strip">
          <h3 className="business-value-title">Affärsvärde</h3>
          <ul className="business-value-list">
            <li>Minskad manuell granskning</li>
            <li>Snabbare designiteration</li>
            <li>Spårbar beslutsgrund</li>
            <li>Strukturerad assembly-intelligens</li>
          </ul>
        </div>
      </div>
      <UploadCard
        status={status}
        setStatus={setStatus}
        onReady={onReady}
        onError={onError}
        onReset={onReset}
      />
      {existingAssemblies.length > 0 && status !== 'ready' && (
        <div className="existing-assemblies">
          <p className="existing-label">Eller välj befintlig assembly:</p>
          <div className="existing-buttons">
            {existingAssemblies.map((a) => (
              <div key={a.assembly_id} className="assembly-item">
                <button
                  type="button"
                  className="btn btn-outline"
                  title={a.assembly_id}
                  onClick={() => onReady(a.assembly_id)}
                >
                  {a.label || a.assembly_id}
                </button>
                <button
                  type="button"
                  className="btn btn-delete"
                  title={`Ta bort ${a.label || a.assembly_id}`}
                  onClick={async (e) => {
                    e.stopPropagation()
                    if (confirm(`Ta bort assembly "${a.label || a.assembly_id}"? Detta kan inte ångras.`)) {
                      try {
                        const res = await fetch(`${API_BASE}/assemblies/${a.assembly_id}`, {
                          method: 'DELETE',
                        })
                        if (res.ok) {
                          refreshAssemblies()
                          // If the deleted assembly was selected, reset
                          if (assemblyId === a.assembly_id) {
                            onReset()
                          }
                        } else {
                          const text = await res.text()
                          alert(`Kunde inte ta bort: ${text}`)
                        }
                      } catch (err) {
                        alert(`Fel vid borttagning: ${err instanceof Error ? err.message : String(err)}`)
                      }
                    }
                  }}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
      {errorMessage && (
        <div className="error-box" role="alert">
          {errorMessage}
        </div>
      )}
      {successMessage && (
        <div className="success-box" role="alert">
          {successMessage}
        </div>
      )}
      {(status === 'ready' || status === 'idle' || status === 'uploading' || status === 'processing') && (
        <div className="stepper-container">
          <Stepper currentStep={getCurrentStep()} />
        </div>
      )}
      {status === 'ready' && assemblyId && (
        <>
          <div className="assembly-id">
            <span>Assembly ID: {assemblyId}</span>
            <button
              type="button"
              className="btn-copy"
              onClick={() => {
                navigator.clipboard.writeText(assemblyId)
              }}
              title="Kopiera Assembly ID"
            >
              Kopiera
            </button>
          </div>
          <ReportPanel assemblyId={assemblyId} onReportGenerated={onReportGenerated} />
          <ChatPanel assemblyId={assemblyId} />
        </>
      )}
      {showArchitecture && (
        <ArchitectureModal onClose={() => setShowArchitecture(false)} />
      )}
    </div>
  )
}
