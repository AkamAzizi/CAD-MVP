import { useCallback, useEffect, useRef, useState } from 'react'
import { Card } from './components/Card'
import { SectionHeader } from './components/SectionHeader'

const API_BASE = '/api'

type SourceItem = string | { chunk_type?: string; field?: string; path?: string }

type Message = {
  role: 'user' | 'assistant'
  question?: string
  answer?: string
  facts?: string[]
  sources?: SourceItem[]
}

type ChatPanelProps = {
  assemblyId: string
}

// Example questions users can click to ask
const EXAMPLE_QUESTIONS = [
  "Hur många delar finns i assemblyn?",
  "Vilken del är störst?",
  "Vilka delar upprepas mest?",
  "Saknas material på några delar?",
  "Vad är nästa steg?",
  "Vilken vy är bäst för 2D-ritning?",
]

export function ChatPanel({ assemblyId }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedHistory, setExpandedHistory] = useState<Set<number>>(new Set())

  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Core function to send a question
  const sendQuestion = useCallback(async (question: string) => {
    const q = question.trim()
    if (!q || loading) return
    setInput('')
    setError(null)
    setMessages((prev) => [...prev, { role: 'user', question: q }])
    setLoading(true)

    try {
      const res = await fetch(`${API_BASE}/assemblies/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assembly_id: assemblyId, question: q }),
      })
      const text = await res.text()
      if (!res.ok) {
        let detail = text
        try {
          const j = JSON.parse(text)
          const d = j.detail
          detail = Array.isArray(d) ? d.map((x: { msg?: string }) => x.msg ?? JSON.stringify(x)).join(' ') : (d ?? text)
        } catch {
          // ignore parse error
        }
        setError(detail)
        setMessages((prev) => prev.slice(0, -1))
        setLoading(false)
        return
      }
      let data: { answer?: string; facts?: string[]; sources?: string[] }
      try {
        data = JSON.parse(text) as { answer?: string; facts?: string[]; sources?: string[] }
      } catch {
        setError('Kunde inte tolka svar från servern.')
        setMessages((prev) => prev.slice(0, -1))
        setLoading(false)
        return
      }
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          answer: data.answer ?? '',
          facts: data.facts ?? [],
          sources: data.sources ?? [],
        },
      ])
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg)
      setMessages((prev) => prev.slice(0, -1))
    } finally {
      setLoading(false)
    }
  }, [assemblyId, loading])

  // Send from input field
  const send = useCallback(() => {
    const q = input.trim()
    if (!q || loading) return
    sendQuestion(q)
  }, [input, loading, sendQuestion])

  // Handle clicking on an example question
  const handleExampleClick = useCallback((question: string) => {
    if (loading) return
    sendQuestion(question)
  }, [loading, sendQuestion])

  // Clear chat
  const clearChat = useCallback(() => {
    setMessages([])
    setExpandedHistory(new Set())
    setError(null)
  }, [])

  // Toggle history expansion
  const toggleHistory = useCallback((index: number) => {
    setExpandedHistory((prev) => {
      const next = new Set(prev)
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        send()
      }
    },
    [send]
  )

  // Get recent messages (last 3 Q&A pairs = 6 messages) for history
  const historyThreshold = 6
  const hasHistory = messages.length > historyThreshold
  const recentMessages = hasHistory ? messages.slice(-historyThreshold) : []
  const currentMessages = hasHistory ? messages.slice(0, -historyThreshold) : messages

  return (
    <Card>
      <SectionHeader
        title="Intelligent Q&A"
        subtitle="Spårbara AI-svar baserat på assembly-analys, BOM och strukturerad metadata"
      />
      <div className="messages">
        {messages.length === 0 && !loading && (
          <div className="empty-state-chat">
            <p>Ställ en fråga om assemblyn nedan.</p>
            <ul>
              <li>BOM-analys</li>
              <li>Rapport med insikter</li>
              <li>Q&A med part-referenser</li>
            </ul>
          </div>
        )}
        {loading && <p className="details loading-indicator">Söker…</p>}
        {currentMessages.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            {m.role === 'user' && m.question && <p>{m.question}</p>}
            {m.role === 'assistant' && (
              <div className="answer-card">
                <div className="answer-card-header">
                  <h5>AI-analys</h5>
                  <span className="traceable-badge">Spårbart svar</span>
                </div>
                <div className="answer-body">{m.answer || '(Inget svar)'}</div>
                <div className="answer-underlag">
                  <strong>Underlag</strong>
                  <ul>
                    {(m.facts?.length ?? 0) > 0 && (
                      <>
                        {m.facts!.map((f, j) => {
                          // Extract meaningful data from facts
                          const factText = f
                          if (factText.includes('unique') || factText.includes('unika')) {
                            const match = factText.match(/(\d+)/)
                            if (match) {
                              return <li key={j}>Unika delar: {match[1]}</li>
                            }
                          }
                          if (factText.includes('total') || factText.includes('totalt') || factText.includes('instances')) {
                            const match = factText.match(/(\d+)/)
                            if (match) {
                              return <li key={j}>Totalt antal instanser: {match[1]}</li>
                            }
                          }
                          return null
                        })}
                      </>
                    )}
                    <li>Datakällor: Assembly-översikt + rapportanalys</li>
                  </ul>
                </div>
              </div>
            )}
          </div>
        ))}
        {hasHistory && recentMessages.length > 0 && (
          <div className="chat-history">
            <div className="chat-history-header">
              <h4>Senaste frågor & svar</h4>
              <button
                type="button"
                className="btn-clear-chat"
                onClick={clearChat}
              >
                Rensa chat
              </button>
            </div>
            {recentMessages.map((m, i) => {
              const globalIndex = currentMessages.length + i
              const isExpanded = expandedHistory.has(globalIndex)
              const isUser = m.role === 'user'
              
              return (
                <details
                  key={globalIndex}
                  className="history-item"
                  open={isExpanded}
                  onToggle={() => toggleHistory(globalIndex)}
                >
                  <summary className={`history-summary ${isUser ? 'user' : 'assistant'}`}>
                    {isUser ? m.question : 'AI-analys'}
                  </summary>
                  {isUser ? (
                    <div className="history-content">{m.question}</div>
                  ) : (
                    <div className="answer-card">
                      <div className="answer-card-header">
                        <h5>AI-analys</h5>
                        <span className="traceable-badge">Spårbart svar</span>
                      </div>
                      <div className="answer-body">{m.answer || '(Inget svar)'}</div>
                      <div className="answer-underlag">
                        <strong>Underlag</strong>
                        <ul>
                          {(m.facts?.length ?? 0) > 0 && (
                            <>
                              {m.facts!.map((f, j) => {
                                const factText = f
                                if (factText.includes('unique') || factText.includes('unika')) {
                                  const match = factText.match(/(\d+)/)
                                  if (match) {
                                    return <li key={j}>Unika delar: {match[1]}</li>
                                  }
                                }
                                if (factText.includes('total') || factText.includes('totalt') || factText.includes('instances')) {
                                  const match = factText.match(/(\d+)/)
                                  if (match) {
                                    return <li key={j}>Totalt antal instanser: {match[1]}</li>
                                  }
                                }
                                return null
                              })}
                            </>
                          )}
                          <li>Datakällor: Assembly-översikt + rapportanalys</li>
                        </ul>
                      </div>
                    </div>
                  )}
                </details>
              )
            })}
          </div>
        )}
        {!hasHistory && messages.length > 0 && (
          <div className="chat-history-header">
            <button
              type="button"
              className="btn-clear-chat"
              onClick={clearChat}
            >
              Rensa chat
            </button>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className="example-questions-bar" aria-label="Föreslagna frågor">
        <span className="example-questions-label">Prova att fråga:</span>
        <div className="example-questions">
          {EXAMPLE_QUESTIONS.map((q, i) => (
            <button
              key={i}
              type="button"
              className="example-question"
              onClick={() => handleExampleClick(q)}
              disabled={loading}
              title={q}
            >
              {q}
            </button>
          ))}
        </div>
      </div>
      <div className="chat-input-row">
        <input
          type="text"
          placeholder="Fråga om assemblyn…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={loading}
        />
        <button type="button" className="btn btn-primary" disabled={loading || !input.trim()} onClick={send}>
          {loading ? 'Svarar…' : 'Skicka fråga'}
        </button>
      </div>
      {error && <div className="error-box">{error}</div>}
    </Card>
  )
}
