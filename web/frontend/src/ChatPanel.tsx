import { useCallback, useEffect, useRef, useState } from 'react'

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
  "How many parts are in the assembly?",
  "Which part is the largest?",
  "Which view is best for a 2D drawing?",
  "Which parts repeat the most?",
  "Are there any missing materials?",
  "What are the next steps?",
]

export function ChatPanel({ assemblyId }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
        setError('Could not parse response from server.')
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

  return (
    <div className="chat-panel">
      <h2>Assembly Q&A</h2>
      <div className="messages">
        {messages.length === 0 && !loading && (
          <p className="empty-prompt">Ask a question about this assembly below.</p>
        )}
        {loading && <p className="details loading-indicator">Searching...</p>}
        {messages.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            {m.role === 'user' && m.question && <p>{m.question}</p>}
            {m.role === 'assistant' && (
              <>
                <div className="answer">{m.answer || '(No answer)'}</div>
                {(m.facts?.length ?? 0) > 0 && (
                  <details className="details">
                    <summary>Facts ({m.facts!.length})</summary>
                    <ul>
                      {m.facts!.map((f, j) => (
                        <li key={j}>{f}</li>
                      ))}
                    </ul>
                  </details>
                )}
                {(m.sources?.length ?? 0) > 0 && (
                  <details className="details">
                    <summary>Sources ({m.sources!.length})</summary>
                    <ul>
                      {m.sources!.map((s, j) => (
                        <li key={j}>
                          {typeof s === 'string' 
                            ? s 
                            : (s.path || [s.chunk_type, s.field].filter(Boolean).join(' · ') || JSON.stringify(s))}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      <div className="example-questions-bar" aria-label="Suggested questions">
        <span className="example-questions-label">Try asking:</span>
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
          placeholder="Ask about the assembly..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={loading}
        />
        <button type="button" className="btn btn-primary" disabled={loading || !input.trim()} onClick={send}>
          {loading ? '...' : 'Send'}
        </button>
      </div>
      {error && <div className="error-box">{error}</div>}
    </div>
  )
}
