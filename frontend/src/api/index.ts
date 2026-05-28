const BASE_URL = ''

interface RequestOptions {
  headers?: Record<string, string>
  [key: string]: any
}

function getToken(): string | null {
  return localStorage.getItem('token')
}

export function setToken(token: string | null) {
  if (token) {
    localStorage.setItem('token', token)
  } else {
    localStorage.removeItem('token')
  }
}

function authHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { 'Authorization': `Bearer ${token}` } : {}
}

async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
  const { headers = {}, ...rest } = options
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...headers,
    },
    ...rest,
  })
  if (res.status === 204) return undefined as T
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data.detail || `Request failed (${res.status})`)
  }
  return data as T
}

export const api = {
  get<T>(path: string): Promise<T> {
    return request<T>('GET', path)
  },
  post<T>(path: string, body?: any): Promise<T> {
    return request<T>('POST', path, { body: body ? JSON.stringify(body) : undefined })
  },
  delete<T>(path: string): Promise<T> {
    return request<T>('DELETE', path)
  },
  async upload<T>(path: string, file: File): Promise<T> {
    const formData = new FormData()
    formData.append('file', file)
    const res = await fetch(`${BASE_URL}${path}`, {
      method: 'POST',
      headers: authHeaders(),
      body: formData,
    })
    if (res.status === 201) return res.json()
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || 'Upload failed')
    return data as T
  },
}

export interface UserOut {
  id: string
  username: string
  role: string
  created_at: string
}

export interface Token {
  access_token: string
  token_type: string
}

export interface DocumentOut {
  id: string
  filename: string
  file_type: string
  status: string
  chunk_count: number
  created_at: string
}

export interface ConversationOut {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface MessageOut {
  id: string
  role: string
  content: string
  sources: SourceItem[] | null
  created_at: string
}

export interface SourceItem {
  filename: string
  chunk_text: string
  score: number
}

export interface QAResponse {
  answer: string
  sources: SourceItem[]
  conversation_id: string
}

export interface QARequest {
  question: string
  conversation_id: string | null
}

// Auth
export const authApi = {
  register: (data: { username: string; password: string }) =>
    api.post<UserOut>('/api/auth/register', data),
  login: (data: { username: string; password: string }) =>
    api.post<Token>('/api/auth/login', data),
  me: () => api.get<UserOut>('/api/auth/me'),
}

// Documents
export const docApi = {
  list: () => api.get<DocumentOut[]>('/api/documents'),
  upload: (file: File) => api.upload<DocumentOut>('/api/documents/upload', file),
  delete: (id: string) => api.delete<void>(`/api/documents/${id}`),
  status: (id: string) => api.get<DocumentOut>(`/api/documents/${id}/status`),
}

// Conversations
export const convApi = {
  list: () => api.get<ConversationOut[]>('/api/conversations'),
  get: (id: string) => api.get<MessageOut[]>(`/api/conversations/${id}`),
  delete: (id: string) => api.delete<void>(`/api/conversations/${id}`),
}

export interface StreamMetadata {
  conversation_id: string
  message_id: string
  sources: SourceItem[]
  suggested_questions?: string[]
}

export interface StreamCallbacks {
  onToken: (token: string) => void
  onDone: (metadata: StreamMetadata) => void
  onError: (error: string) => void
}

// QA
export const qaApi = {
  ask: (data: QARequest) => api.post<QAResponse>('/api/qa/ask', data),
  askStream: (data: QARequest, callbacks: StreamCallbacks): AbortController => {
    const controller = new AbortController()

    fetch(`${BASE_URL}/api/qa/ask/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(),
      },
      body: JSON.stringify(data),
      signal: controller.signal,
    }).then(async (response) => {
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        callbacks.onError(errData.detail || `Request failed (${response.status})`)
        return
      }

      const reader = response.body?.getReader()
      if (!reader) {
        callbacks.onError('No response body')
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Split on newlines and process complete lines
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''  // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const payload = line.slice(6).trim()
            if (!payload) continue
            try {
              const event = JSON.parse(payload)
              const { type, data } = event
              if (type === 'token') {
                callbacks.onToken(data.token)
              } else if (type === 'metadata') {
                callbacks.onDone(data as StreamMetadata)
              } else if (type === 'error') {
                callbacks.onError(data.message)
              }
            } catch {
              // Skip malformed JSON lines
            }
          }
        }
      }
    }).catch((err: Error) => {
      if (err.name !== 'AbortError') {
        callbacks.onError(err.message || 'Network error')
      }
    })

    return controller
  },
}
