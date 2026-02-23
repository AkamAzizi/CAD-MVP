import { useCallback, useRef, useState } from 'react'
import { AgentPipeline } from './components/AgentPipeline'

const API_BASE = '/api'

type Status = 'idle' | 'uploading' | 'processing' | 'ready' | 'error'

type UploadCardProps = {
  status: Status
  setStatus: (s: Status) => void
  onReady: (assemblyId: string) => void
  onError: (message: string) => void
  onReset: () => void
}

export function UploadCard({ status, setStatus, onReady, onError, onReset }: UploadCardProps) {
  const [file, setFile] = useState<File | null>(null)
  const [dragover, setDragover] = useState(false)
  const [statusText, setStatusText] = useState<string>('')
  const inputRef = useRef<HTMLInputElement>(null)

  const accept = '.step,.stp'

  const handleFile = useCallback((f: File | null) => {
    const ok = f && /\.(step|stp)$/i.test(f.name)
    if (ok) {
      setFile(f)
      // Reset error state when a valid file is selected
      if (status === 'error') {
        setStatus('idle')
        setStatusText('')
      }
    } else if (f) {
      setFile(null)
      setStatus('error')
      setStatusText('Ogiltig filtyp. Välj en .step eller .stp fil.')
    } else {
      setFile(null)
    }
  }, [status])

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragover(false)
      const f = e.dataTransfer.files[0]
      if (f) handleFile(f)
    },
    [handleFile]
  )

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragover(true)
  }, [])

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragover(false)
  }, [])

  const onChoose = useCallback(() => {
    inputRef.current?.click()
  }, [])

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0]
      handleFile(f ?? null)
      e.target.value = ''
    },
    [handleFile]
  )

  const process = useCallback(async () => {
    if (!file) return
    setStatus('uploading')
    setStatusText('Laddar upp…')
    const form = new FormData()
    form.append('file', file)

    try {
      setStatus('processing')
      setStatusText('Processar…')
      const res = await fetch(`${API_BASE}/assemblies/upload`, {
        method: 'POST',
        body: form,
      })
      const text = await res.text()
      if (!res.ok) {
        let detail = text
        try {
          const j = JSON.parse(text)
          const d = j.detail
          detail = Array.isArray(d) ? d.map((x: { msg?: string }) => x.msg ?? JSON.stringify(x)).join(' ') : (d ?? text)
        } catch {
          // use raw text
        }
        setStatus('error')
        setStatusText('')
        onError(detail)
        return
      }
      const data = JSON.parse(text) as { assembly_id: string; snapshot_path?: string }
      setStatusText('Klar')
      onReady(data.assembly_id)
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setStatus('error')
      setStatusText('')
      onError(msg)
    }
  }, [file, onReady, onError])

  const isProcessing = status === 'uploading' || status === 'processing'

  return (
    <div className="upload-card">
      {status === 'idle' && !file && (
        <div className="empty-state-upload">
          <p className="empty-state-title">Ladda upp en STEP-fil för att börja.</p>
          <ul className="empty-state-features">
            <li>BOM-analys på sekunder</li>
            <li>Rapport med insikter</li>
            <li>Q&A med part-referenser</li>
          </ul>
        </div>
      )}
      <div
        className={`upload-zone ${dragover ? 'dragover' : ''}`}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={onChoose}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          onChange={onInputChange}
          aria-label="Välj STEP-fil"
        />
        <p>Dra & släpp en STEP-fil här, eller klicka för att välja</p>
        {file && <p className="file-name">{file.name}</p>}
      </div>
      <div className="actions">
        <button
          type="button"
          className="btn btn-primary"
          disabled={!file || isProcessing}
          onClick={process}
        >
          {isProcessing ? 'Processar…' : 'Ladda upp & processa'}
        </button>
        {status === 'ready' && (
          <button type="button" className="btn btn-outline" onClick={onReset}>
            Välj ny fil
          </button>
        )}
      </div>
      {statusText && (
        <p className={`status ${status === 'ready' ? 'ready' : status === 'error' ? 'error' : ''}`}>
          {statusText}
        </p>
      )}
      {isProcessing && (
        <AgentPipeline
          isActive={isProcessing}
          isDone={status === 'ready'}
        />
      )}
      {!file && status === 'idle' && (
        <p className="upload-hint">STEP-filer kan vara stora. Bearbetning kan ta 10–60 sek.</p>
      )}
    </div>
  )
}
