import { useEffect, useState } from 'react'

type AgentPipelineProps = {
  isActive: boolean
  isDone: boolean
  durationMs?: number
}

type StepStatus = 'pending' | 'active' | 'done'

const STEPS = [
  'Strukturparser',
  'Assembly-extraktion',
  'BOM-generering',
  'Regelbaserad riskanalys',
  'Indexering för Q&A',
  'Rapport-syntes',
]

export function AgentPipeline({ isActive, isDone, durationMs = 12000 }: AgentPipelineProps) {
  const [currentStep, setCurrentStep] = useState(0)
  const [shouldHide, setShouldHide] = useState(false)

  useEffect(() => {
    if (!isActive) {
      setCurrentStep(0)
      setShouldHide(false)
      return
    }

    if (isDone) {
      // Mark all steps as done immediately
      setCurrentStep(STEPS.length)
      // Hide after 1.5s
      const hideTimer = setTimeout(() => {
        setShouldHide(true)
      }, 1500)
      return () => clearTimeout(hideTimer)
    }

    // Progress through steps when active but not done
    const stepInterval = durationMs / STEPS.length
    const timer = setInterval(() => {
      setCurrentStep((prev) => {
        // Stop at the last step if not done yet
        if (prev >= STEPS.length - 1) {
          return STEPS.length - 1
        }
        return prev + 1
      })
    }, stepInterval)

    return () => clearInterval(timer)
  }, [isActive, isDone, durationMs])

  if (!isActive || shouldHide) {
    return null
  }

  const getStepStatus = (index: number): StepStatus => {
    if (isDone || index < currentStep) {
      return 'done'
    }
    if (index === currentStep) {
      return 'active'
    }
    return 'pending'
  }

  return (
    <div className="agent-pipeline">
      <div className="agent-pipeline-header">
        <h4>Analysmotor</h4>
      </div>
      <div className="agent-pipeline-steps">
        {STEPS.map((step, index) => {
          const status = getStepStatus(index)
          return (
            <div key={index} className={`pipeline-step pipeline-step-${status}`}>
              <div className="pipeline-step-indicator">
                {status === 'done' && (
                  <span className="pipeline-check">✓</span>
                )}
                {status === 'active' && (
                  <span className="pipeline-spinner"></span>
                )}
                {status === 'pending' && (
                  <span className="pipeline-dot"></span>
                )}
              </div>
              <div className="pipeline-step-label">{step}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
