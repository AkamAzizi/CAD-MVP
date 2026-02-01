import { useCallback, useEffect, useState } from 'react'
import { ChatPanel } from './ChatPanel'
import { UploadCard } from './UploadCard'

const API_BASE = '/api'

type Status = 'idle' | 'uploading' | 'processing' | 'ready' | 'error'

type Assembly = { assembly_id: string; label?: string; snapshot_path?: string }

export default function App() {
  const [status, setStatus] = useState<Status>('idle')
  const [assemblyId, setAssemblyId] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [existingAssemblies, setExistingAssemblies] = useState<Assembly[]>([])

  useEffect(() => {
    fetch(`${API_BASE}/assemblies`)
      .then((r) => r.ok ? r.json() : { assemblies: [] })
      .then((data) => setExistingAssemblies(data.assemblies || []))
      .catch(() => setExistingAssemblies([]))
  }, [])

  const onReady = useCallback((id: string) => {
    setAssemblyId(id)
    setStatus('ready')
    setErrorMessage(null)
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
  }, [])

  return (
    <div className="app">
      <h1>CAD-MVP · Assembly Q&A</h1>
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
              <button
                key={a.assembly_id}
                type="button"
                className="btn btn-outline"
                title={a.assembly_id}
                onClick={() => onReady(a.assembly_id)}
              >
                {a.label || a.assembly_id}
              </button>
            ))}
          </div>
        </div>
      )}
      {errorMessage && (
        <div className="error-box" role="alert">
          {errorMessage}
        </div>
      )}
      {status === 'ready' && assemblyId && (
        <>
          <div className="assembly-id">Assembly ID: {assemblyId}</div>
          <ChatPanel assemblyId={assemblyId} />
        </>
      )}
    </div>
  )
}
