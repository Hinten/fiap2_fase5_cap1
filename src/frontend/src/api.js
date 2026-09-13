const DEFAULT_ERROR = 'Não foi possível falar com o assistente agora. Tente novamente em instantes.'

async function readResponse(response) {
  const contentType = response.headers.get('content-type') ?? ''

  if (contentType.includes('application/json')) {
    return response.json()
  }

  const text = await response.text()
  return text ? { error: text } : {}
}

function getErrorMessage(response, payload) {
  if (typeof payload?.error?.message === 'string' && payload.error.message.trim()) {
    return payload.error.message
  }

  if (typeof payload?.error === 'string' && payload.error.trim()) {
    return payload.error
  }

  if (typeof payload?.message === 'string' && payload.message.trim()) {
    return payload.message
  }

  if (response.status === 503) {
    return 'O Watson ainda não está configurado. Confira as variáveis do arquivo .env.'
  }

  if (response.status === 502) {
    return 'O Watson está temporariamente indisponível. Tente novamente em instantes.'
  }

  return DEFAULT_ERROR
}

async function request(path, options = {}) {
  let response

  try {
    response = await fetch(path, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    })
  } catch (error) {
    if (error?.name === 'AbortError') throw error
    throw new Error(
      'Não foi possível conectar ao servidor. Verifique se o Flask está em execução.',
      { cause: error },
    )
  }

  const payload = await readResponse(response)

  if (!response.ok) {
    throw new Error(getErrorMessage(response, payload))
  }

  return payload
}

export function getHealth({ signal } = {}) {
  return request('/api/health', { method: 'GET', signal })
}

export function sendChatMessage(message, conversationId) {
  return request('/api/chat', {
    method: 'POST',
    body: JSON.stringify({
      message,
      conversationId: conversationId || null,
    }),
  })
}

export function resetConversation(conversationId) {
  return request('/api/reset', {
    method: 'POST',
    body: JSON.stringify({ conversationId: conversationId || null }),
  })
}

export { DEFAULT_ERROR }
