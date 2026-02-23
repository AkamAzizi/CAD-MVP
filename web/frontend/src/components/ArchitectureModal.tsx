import { useEffect } from 'react'

type ArchitectureModalProps = {
  onClose: () => void
}

const ARCHITECTURE_COMPONENTS = [
  'STEP-parser',
  'Feature extraction',
  'BOM-generator',
  'Regelbaserad analys',
  'Vector-indexering',
  'RAG-frågemotor',
  'Rapport-syntes',
]

export function ArchitectureModal({ onClose }: ArchitectureModalProps) {
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [onClose])

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Teknisk arkitektur</h2>
          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            aria-label="Stäng"
          >
            ×
          </button>
        </div>
        <div className="modal-body">
          <ul className="architecture-list">
            {ARCHITECTURE_COMPONENTS.map((component, index) => (
              <li key={index}>{component}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
