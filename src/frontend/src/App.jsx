import { useEffect, useMemo, useRef, useState } from 'react'
import { getHealth, resetConversation, sendChatMessage } from './api.js'

const MAX_MESSAGE_LENGTH = 500

const STARTER_SUGGESTIONS = [
  {
    label: 'Relatar um sintoma',
    message: 'Quero relatar um sintoma que estou sentindo.',
    icon: 'pulse',
  },
  {
    label: 'Preparar uma consulta',
    message: 'Como posso me preparar para uma consulta?',
    icon: 'clipboard',
  },
  {
    label: 'Conhecer os limites',
    message: 'O que este assistente pode e não pode fazer?',
    icon: 'shield',
  },
]

const WELCOME_TEXT =
  'Olá! Eu sou o CardioIA Acolhe. Posso ajudar você a organizar informações sobre sintomas e a se preparar para conversar com um profissional de saúde. Como posso acolher você hoje?'

function makeId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function makeMessage(role, text, metadata = {}) {
  return {
    id: makeId(),
    role,
    text,
    createdAt: new Date(),
    ...metadata,
  }
}

function initialMessages() {
  return [makeMessage('assistant', WELCOME_TEXT)]
}

function formatTime(date) {
  return new Intl.DateTimeFormat('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function normalizeReply(reply) {
  if (Array.isArray(reply)) {
    return reply
      .filter((item) => typeof item === 'string' && item.trim())
      .join('\n\n')
      .trim()
  }

  if (typeof reply === 'string') {
    return reply.trim()
  }

  return ''
}

function normalizeIntent(intent, fallbackConfidence) {
  if (typeof intent === 'string') {
    return { name: intent, confidence: Number(fallbackConfidence) || 0 }
  }

  if (intent && typeof intent === 'object') {
    return {
      name: intent.name ?? intent.intent ?? 'não identificada',
      confidence: Number(intent.confidence ?? fallbackConfidence) || 0,
    }
  }

  return { name: 'não identificada', confidence: Number(fallbackConfidence) || 0 }
}

function normalizeEntities(entities) {
  if (!Array.isArray(entities)) return []

  return entities.map((entity, index) => {
    if (typeof entity === 'string') {
      return { entity: 'entidade', value: entity, id: `${entity}-${index}` }
    }

    const name = entity?.entity ?? entity?.name ?? 'entidade'
    const value = entity?.value ?? entity?.text ?? '—'
    return { entity: String(name), value: String(value), id: `${name}-${value}-${index}` }
  })
}

function isWatsonConfigured(payload) {
  const explicitValue =
    payload?.watsonConfigured ??
    payload?.watson_configured ??
    payload?.configured ??
    payload?.watson?.configured

  if (typeof explicitValue === 'boolean') return explicitValue
  return payload?.status === 'ok' || payload?.status === 'healthy'
}

function Icon({ name, size = 20 }) {
  const commonProps = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': true,
  }

  const paths = {
    arrow: (
      <>
        <path d="M5 12h14" />
        <path d="m13 6 6 6-6 6" />
      </>
    ),
    bot: (
      <>
        <rect x="4" y="7" width="16" height="13" rx="4" />
        <path d="M9 12h.01M15 12h.01M9 16h6M12 7V4M10 4h4" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    chevron: <path d="m8 10 4 4 4-4" />,
    clipboard: (
      <>
        <rect x="5" y="4" width="14" height="17" rx="2" />
        <path d="M9 4.5h6V7H9zM9 12h6M9 16h4" />
      </>
    ),
    pulse: <path d="M3 12h4l2.2-5 4 11 2.1-6H21" />,
    refresh: (
      <>
        <path d="M20 7v5h-5" />
        <path d="M19 12a7 7 0 1 0-2 5" />
      </>
    ),
    send: (
      <>
        <path d="m22 2-7 20-4-9-9-4Z" />
        <path d="M22 2 11 13" />
      </>
    ),
    shield: (
      <>
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
        <path d="m9 12 2 2 4-4" />
      </>
    ),
    spark: (
      <>
        <path d="m12 3-1.1 3.1A4 4 0 0 1 8.5 8.5L5 10l3.5 1.5a4 4 0 0 1 2.4 2.4L12 17l1.1-3.1a4 4 0 0 1 2.4-2.4L19 10l-3.5-1.5a4 4 0 0 1-2.4-2.4Z" />
      </>
    ),
    user: (
      <>
        <circle cx="12" cy="8" r="4" />
        <path d="M4.5 21a7.5 7.5 0 0 1 15 0" />
      </>
    ),
    warning: (
      <>
        <path d="M10.3 3.6 2.4 17.2A2 2 0 0 0 4.1 20h15.8a2 2 0 0 0 1.7-2.8L13.7 3.6a2 2 0 0 0-3.4 0Z" />
        <path d="M12 9v4M12 17h.01" />
      </>
    ),
  }

  return <svg {...commonProps}>{paths[name]}</svg>
}

function StatusPill({ health }) {
  const copy = {
    checking: 'Verificando serviço',
    online: 'Serviço disponível',
    setup: 'Watson não configurado',
    offline: 'Servidor indisponível',
  }

  return (
    <div className={`status-pill status-pill--${health}`} role="status" aria-live="polite">
      <span className="status-pill__dot" aria-hidden="true" />
      <span>{copy[health]}</span>
    </div>
  )
}

function BrandMark({ compact = false }) {
  return (
    <div className={`brand-mark${compact ? ' brand-mark--compact' : ''}`} aria-hidden="true">
      <svg viewBox="0 0 64 64" fill="none">
        <path
          d="M32 50S12 39.1 12 24.6C12 17.8 16.8 13.5 23 13.5c4 0 7.3 2.2 9 5.3 1.7-3.1 5-5.3 9-5.3 6.2 0 11 4.3 11 11.1C52 39.1 32 50 32 50Z"
          fill="currentColor"
        />
        <path d="M17 31h8l3-7 5.2 14 3.3-7H47" stroke="white" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  )
}

function MessageBubble({ message }) {
  const isAssistant = message.role === 'assistant'

  return (
    <li className={`message-row message-row--${message.role}`}>
      <div className={`message-avatar message-avatar--${message.role}`} aria-hidden="true">
        <Icon name={isAssistant ? 'bot' : 'user'} size={18} />
      </div>
      <article
        className={`message-bubble${message.urgent ? ' message-bubble--urgent' : ''}`}
        role={message.urgent ? 'alert' : undefined}
        aria-live={message.urgent ? 'assertive' : undefined}
        aria-atomic={message.urgent ? 'true' : undefined}
      >
        <div className="message-meta">
          <span>{isAssistant ? 'CardioIA' : 'Você'}</span>
          <time dateTime={message.createdAt.toISOString()}>{formatTime(message.createdAt)}</time>
        </div>
        {message.urgent && (
          <div className="urgent-label">
            <Icon name="warning" size={16} />
            Orientação de emergência
          </div>
        )}
        <p>{message.text}</p>
      </article>
    </li>
  )
}

function TypingIndicator() {
  return (
    <li className="message-row message-row--assistant" role="status" aria-label="CardioIA está preparando uma resposta">
      <div className="message-avatar message-avatar--assistant" aria-hidden="true">
        <Icon name="bot" size={18} />
      </div>
      <div className="message-bubble message-bubble--typing">
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="sr-only">Preparando resposta…</span>
      </div>
    </li>
  )
}

function SuggestionCards({ onSelect, disabled }) {
  return (
    <div className="suggestions" aria-label="Sugestões para iniciar a conversa">
      <p className="suggestions__eyebrow">Você pode começar por aqui</p>
      <div className="suggestions__grid">
        {STARTER_SUGGESTIONS.map((suggestion) => (
          <button
            className="suggestion-card"
            disabled={disabled}
            key={suggestion.label}
            onClick={() => onSelect(suggestion.message)}
            type="button"
          >
            <span className="suggestion-card__icon">
              <Icon name={suggestion.icon} />
            </span>
            <span>{suggestion.label}</span>
            <Icon name="arrow" size={17} />
          </button>
        ))}
      </div>
    </div>
  )
}

function NlpDetails({ analysis, conversationId, expanded, onToggle }) {
  const confidence = Math.min(1, Math.max(0, analysis?.intent?.confidence ?? 0))
  const confidenceLabel = `${Math.round(confidence * 100)}%`

  return (
    <aside className={`nlp-panel${expanded ? ' nlp-panel--expanded' : ''}`} aria-label="Detalhes de processamento de linguagem">
      <button
        className="nlp-panel__header"
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        aria-controls="nlp-panel-content"
      >
        <span className="nlp-panel__title">
          <span className="nlp-panel__icon"><Icon name="spark" size={18} /></span>
          <span>
            <strong>Detalhes NLP</strong>
            <small>Como a mensagem foi entendida</small>
          </span>
        </span>
        <span className="nlp-panel__chevron"><Icon name="chevron" size={18} /></span>
      </button>

      <div className="nlp-panel__content" id="nlp-panel-content" hidden={!expanded}>
        {!analysis ? (
          <div className="nlp-empty">
            <div className="nlp-empty__graphic" aria-hidden="true">
              <Icon name="pulse" size={28} />
            </div>
            <p>Os detalhes aparecerão depois da primeira resposta.</p>
          </div>
        ) : (
          <>
            <dl className="nlp-stats">
              <div>
                <dt>Intenção detectada</dt>
                <dd><code>#{analysis.intent.name}</code></dd>
              </div>
              <div>
                <dt>Confiança</dt>
                <dd className="confidence-value">{confidenceLabel}</dd>
              </div>
            </dl>

            <div
              className="confidence-track"
              role="progressbar"
              aria-label="Confiança da intenção"
              aria-valuemin="0"
              aria-valuemax="100"
              aria-valuenow={Math.round(confidence * 100)}
            >
              <span style={{ width: confidenceLabel }} />
            </div>

            <section className="entity-section" aria-labelledby="entity-heading">
              <div className="entity-section__heading">
                <h3 id="entity-heading">Entidades</h3>
                <span>{analysis.entities.length}</span>
              </div>
              {analysis.entities.length ? (
                <ul className="entity-list">
                  {analysis.entities.map((entity) => (
                    <li key={entity.id}>
                      <span>@{entity.entity}</span>
                      <strong>{entity.value}</strong>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="entity-empty">Nenhuma entidade encontrada nesta mensagem.</p>
              )}
            </section>

            <div className={`urgency-status${analysis.urgent ? ' urgency-status--active' : ''}`}>
              <Icon name={analysis.urgent ? 'warning' : 'check'} size={17} />
              {analysis.urgent ? 'Sinal de alerta identificado' : 'Sem sinal de alerta identificado'}
            </div>
          </>
        )}

        <div className="session-info">
          <span>Sessão</span>
          <code title={conversationId || 'Aguardando primeira interação'}>
            {conversationId ? `${conversationId.slice(0, 8)}…` : 'não iniciada'}
          </code>
        </div>
      </div>
    </aside>
  )
}

export default function App() {
  const [messages, setMessages] = useState(initialMessages)
  const [conversationId, setConversationId] = useState(null)
  const [input, setInput] = useState('')
  const [health, setHealth] = useState('checking')
  const [isSending, setIsSending] = useState(false)
  const [isResetting, setIsResetting] = useState(false)
  const [error, setError] = useState(null)
  const [failedMessage, setFailedMessage] = useState(null)
  const [detailsExpanded, setDetailsExpanded] = useState(true)
  const transcriptEndRef = useRef(null)
  const inputRef = useRef(null)

  const lastAnalysis = useMemo(() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      if (messages[index].analysis) return messages[index].analysis
    }
    return null
  }, [messages])

  const hasUserMessages = messages.some((message) => message.role === 'user')
  const trimmedInput = input.trim()
  const isOverLimit = input.length > MAX_MESSAGE_LENGTH
  const canSend = Boolean(trimmedInput) && !isOverLimit && !isSending && !isResetting

  useEffect(() => {
    const controller = new AbortController()

    getHealth({ signal: controller.signal })
      .then((payload) => setHealth(isWatsonConfigured(payload) ? 'online' : 'setup'))
      .catch((requestError) => {
        if (requestError.name !== 'AbortError') setHealth('offline')
      })

    return () => controller.abort()
  }, [])

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [messages, isSending, error])

  useEffect(() => {
    const textarea = inputRef.current
    if (!textarea) return
    textarea.style.height = 'auto'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 132)}px`
  }, [input])

  async function submitMessage(rawMessage, { appendUserMessage = true } = {}) {
    const cleanMessage = rawMessage.trim()

    if (!cleanMessage || cleanMessage.length > MAX_MESSAGE_LENGTH || isSending || isResetting) return

    if (appendUserMessage) {
      setMessages((current) => [...current, makeMessage('user', cleanMessage)])
    }

    setInput('')
    setError(null)
    setFailedMessage(null)
    setIsSending(true)

    try {
      const payload = await sendChatMessage(cleanMessage, conversationId)
      const reply = normalizeReply(payload.reply ?? payload.responses ?? payload.message)

      if (!reply) {
        throw new Error('O assistente recebeu a mensagem, mas não retornou uma resposta legível.')
      }

      const analysis = {
        intent: normalizeIntent(payload.intent, payload.confidence),
        entities: normalizeEntities(payload.entities),
        urgent: Boolean(payload.urgent),
      }

      setConversationId(payload.conversationId ?? payload.conversation_id ?? conversationId)
      setMessages((current) => [
        ...current,
        makeMessage('assistant', reply, { urgent: analysis.urgent, analysis }),
      ])
      setHealth('online')
    } catch (requestError) {
      setError(requestError.message)
      setFailedMessage(cleanMessage)
      if (requestError.message.includes('configurado')) setHealth('setup')
    } finally {
      setIsSending(false)
      window.setTimeout(() => inputRef.current?.focus(), 0)
    }
  }

  function handleSubmit(event) {
    event.preventDefault()
    if (canSend) submitMessage(input)
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      if (canSend) submitMessage(input)
    }
  }

  async function handleReset() {
    if (isSending || isResetting) return

    const currentConversationId = conversationId
    setIsResetting(true)
    setError(null)
    setFailedMessage(null)

    try {
      if (currentConversationId) await resetConversation(currentConversationId)
    } catch (requestError) {
      setError(`A conversa foi limpa neste dispositivo. ${requestError.message}`)
    } finally {
      setConversationId(null)
      setMessages(initialMessages())
      setInput('')
      setIsResetting(false)
      window.setTimeout(() => inputRef.current?.focus(), 0)
    }
  }

  function handleRetry() {
    if (failedMessage) submitMessage(failedMessage, { appendUserMessage: false })
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#chat-input">Ir para o campo de mensagem</a>

      <header className="topbar">
        <div className="topbar__inner">
          <div className="brand">
            <BrandMark />
            <div>
              <span className="brand__name">CardioIA <strong>Acolhe</strong></span>
              <span className="brand__tagline">Orientação cardiológica educativa</span>
            </div>
          </div>

          <div className="topbar__actions">
            <StatusPill health={health} />
            <button
              className="new-chat-button"
              type="button"
              onClick={handleReset}
              disabled={isSending || isResetting}
              aria-label={isResetting ? 'Limpando conversa' : 'Nova conversa'}
            >
              <Icon name="refresh" size={17} />
              <span>{isResetting ? 'Limpando…' : 'Nova conversa'}</span>
            </button>
          </div>
        </div>
      </header>

      <div className="safety-strip" role="note">
        <div className="safety-strip__inner">
          <Icon name="shield" size={17} />
          <span>Este assistente não realiza diagnósticos nem substitui atendimento médico.</span>
          <span className="safety-strip__emergency">Em uma emergência, ligue <strong>192</strong>.</span>
        </div>
      </div>

      <main className="workspace">
        <section className="chat-card" aria-labelledby="conversation-heading">
          <div className="chat-card__header">
            <div>
              <p className="section-kicker">Conversa acolhedora</p>
              <h1 id="conversation-heading">Conte o que você está sentindo</h1>
            </div>
            <div className="privacy-note">
              <Icon name="shield" size={16} />
              Não informe dados pessoais
            </div>
          </div>

          <div className="transcript" role="log" aria-live="polite" aria-relevant="additions">
            <ol className="message-list">
              {messages.map((message) => <MessageBubble key={message.id} message={message} />)}
              {!hasUserMessages && (
                <li className="suggestion-row">
                  <SuggestionCards onSelect={submitMessage} disabled={isSending || isResetting} />
                </li>
              )}
              {isSending && <TypingIndicator />}
            </ol>

            {error && (
              <div className="error-card" role="alert">
                <span className="error-card__icon"><Icon name="warning" size={18} /></span>
                <div>
                  <strong>Não conseguimos concluir o envio</strong>
                  <p>{error}</p>
                </div>
                {failedMessage && (
                  <button type="button" onClick={handleRetry} disabled={isSending}>Tentar novamente</button>
                )}
              </div>
            )}

            <div ref={transcriptEndRef} />
          </div>

          <form className="composer" onSubmit={handleSubmit}>
            <label className="sr-only" htmlFor="chat-input">Digite sua mensagem</label>
            <div className={`composer__box${isOverLimit ? ' composer__box--invalid' : ''}`}>
              <textarea
                id="chat-input"
                ref={inputRef}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Descreva um sintoma ou faça uma pergunta…"
                rows="1"
                maxLength={MAX_MESSAGE_LENGTH + 50}
                aria-describedby="composer-help character-count"
                aria-invalid={isOverLimit}
                disabled={isSending || isResetting}
              />
              <button className="send-button" type="submit" disabled={!canSend} aria-label="Enviar mensagem">
                <Icon name="send" size={20} />
              </button>
            </div>
            <div className="composer__footer">
              <span id="composer-help"><kbd>Enter</kbd> envia · <kbd>Shift + Enter</kbd> quebra a linha</span>
              <span id="character-count" className={isOverLimit ? 'character-count--invalid' : ''}>
                {input.length}/{MAX_MESSAGE_LENGTH}
              </span>
            </div>
          </form>
        </section>

        <NlpDetails
          analysis={lastAnalysis}
          conversationId={conversationId}
          expanded={detailsExpanded}
          onToggle={() => setDetailsExpanded((current) => !current)}
        />
      </main>

      <footer className="page-footer">
        <BrandMark compact />
        <p>CardioIA Acolhe · Projeto acadêmico FIAP</p>
        <span>Informação para acolher, nunca para diagnosticar.</span>
      </footer>
    </div>
  )
}
