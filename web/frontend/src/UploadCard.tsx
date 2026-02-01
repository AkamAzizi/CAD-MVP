import { useCallback, useRef, useState } from 'react'

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
    if (ok) setFile(f)
    else if (f) setFile(null)
    else setFile(null)
  }, [])

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
    setStatusText('Uploading…')
    const form = new FormData()
    form.append('file', file)

    try {
      setStatus('processing')
      setStatusText('Processing (pipeline + snapshot)…')
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
          onError(detail)
        setStatusText('')
        return
      }
      const data = JSON.parse(text) as { assembly_id: string; snapshot_path?: string }
      setStatusText('Ready')
      onReady(data.assembly_id)
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      onError(msg)
      setStatusText('')
    }
  }, [file, onReady, onError])

  const isProcessing = status === 'uploading' || status === 'processing'

  return (
    <div className="upload-card">
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
          aria-label="Choose STEP file"
        />
        <p>Drag & drop a STEP file here, or click to choose</p>
        {file && <p className="file-name">{file.name}</p>}
      </div>
      <div className="actions">
        <button
          type="button"
          className="btn btn-primary"
          disabled={!file || isProcessing}
          onClick={process}
        >
          {isProcessing ? 'Processing…' : 'Process'}
        </button>
        {status === 'ready' && (
          <button type="button" className="btn" onClick={onReset}>
            New file
          </button>
        )}
      </div>
      {statusText && (
        <p className={`status ${status === 'ready' ? 'ready' : status === 'error' ? 'error' : ''}`}>
          {statusText}
        </p>
      )}
    </div>
  )
}
