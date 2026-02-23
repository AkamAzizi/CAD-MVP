type StepperProps = {
  currentStep: 1 | 2 | 3
}

export function Stepper({ currentStep }: StepperProps) {
  return (
    <div className="stepper">
      <div className={`stepper-step ${currentStep >= 1 ? 'active' : ''} ${currentStep === 1 ? 'current' : ''}`}>
        <div className="stepper-number">1</div>
        <div className="stepper-label">Ladda upp STEP</div>
      </div>
      <div className={`stepper-connector ${currentStep >= 2 ? 'active' : ''}`}></div>
      <div className={`stepper-step ${currentStep >= 2 ? 'active' : ''} ${currentStep === 2 ? 'current' : ''}`}>
        <div className="stepper-number">2</div>
        <div className="stepper-label">Generera rapport</div>
      </div>
      <div className={`stepper-connector ${currentStep >= 3 ? 'active' : ''}`}></div>
      <div className={`stepper-step ${currentStep >= 3 ? 'active' : ''} ${currentStep === 3 ? 'current' : ''}`}>
        <div className="stepper-number">3</div>
        <div className="stepper-label">Fråga assemblyn</div>
      </div>
    </div>
  )
}
