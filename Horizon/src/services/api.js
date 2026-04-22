export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
export const WS_BASE = API_BASE.replace(/^http/i, 'ws')
export const AUTH_SESSION_EXPIRED = 'SESSION_EXPIRED'

const clearAuthStorage = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('userEmail')
  localStorage.removeItem('userName')
}

const parseJwtPayload = (token) => {
  try {
    const [, payload] = String(token || '').split('.')
    if (!payload) return null
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/')
    const json = atob(base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '='))
    return JSON.parse(json)
  } catch {
    return null
  }
}

const getValidToken = () => {
  const token = localStorage.getItem('token')
  if (!token) return null

  const payload = parseJwtPayload(token)
  const expSeconds = Number(payload?.exp)
  if (!Number.isFinite(expSeconds) || expSeconds * 1000 <= Date.now()) {
    clearAuthStorage()
    return null
  }
  return token
}

const getAuthHeaders = () => {
  const token = getValidToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

const parseError = async (res, fallback) => {
  if (res.status === 401) {
    clearAuthStorage()
    return AUTH_SESSION_EXPIRED
  }

  try {
    const err = await res.json()
    return err.detail || fallback
  } catch {
    return fallback
  }
}

export const authAPI = {
  signup: async (username, email, password) => {
    const res = await fetch(`${API_BASE}/v1/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password }),
    })
    if (!res.ok) {
      throw new Error(await parseError(res, 'Signup failed'))
    }
    localStorage.setItem('userName', username)
    return res.json()
  },

  login: async (email, password) => {
    const res = await fetch(`${API_BASE}/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) {
      throw new Error(await parseError(res, 'Login failed'))
    }

    const data = await res.json()
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('userEmail', email)
    if (!localStorage.getItem('userName')) {
      const fallbackName = email.split('@')[0] || 'User'
      localStorage.setItem('userName', fallbackName)
    }
    return data
  },

  logout: () => {
    clearAuthStorage()
  },

  getToken: () => getValidToken(),
  getUserEmail: () => localStorage.getItem('userEmail'),
  getUserName: () => localStorage.getItem('userName'),
  isAuthenticated: () => !!getValidToken(),
}

export const chatAPI = {
  createSession: async (title = 'New Chat') => {
    const res = await fetch(`${API_BASE}/v1/chat/sessions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ title }),
    })
    if (!res.ok) {
      throw new Error(await parseError(res, 'Failed to create session'))
    }
    return res.json()
  },

  getSessions: async () => {
    const res = await fetch(`${API_BASE}/v1/chat/sessions`, {
      headers: { ...getAuthHeaders() },
    })
    if (!res.ok) {
      throw new Error(await parseError(res, 'Failed to get sessions'))
    }
    return res.json()
  },

  getSession: async (sessionId) => {
    const res = await fetch(`${API_BASE}/v1/chat/sessions/${sessionId}`, {
      headers: { ...getAuthHeaders() },
    })
    if (!res.ok) {
      throw new Error(await parseError(res, 'Failed to get session'))
    }
    return res.json()
  },

  getSessionFiles: async (sessionId) => {
    const res = await fetch(`${API_BASE}/v1/chat/sessions/${sessionId}/files`, {
      headers: { ...getAuthHeaders() },
    })
    if (!res.ok) {
      throw new Error(await parseError(res, 'Failed to get session files'))
    }
    return res.json()
  },

  deleteSession: async (sessionId) => {
    const res = await fetch(`${API_BASE}/v1/chat/sessions/${sessionId}`, {
      method: 'DELETE',
      headers: { ...getAuthHeaders() },
    })
    if (!res.ok) {
      throw new Error(await parseError(res, 'Failed to delete session'))
    }
  },

  updateSessionTitle: async (sessionId, title) => {
    const res = await fetch(`${API_BASE}/v1/chat/sessions/${sessionId}/title`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ title }),
    })
    if (!res.ok) {
      throw new Error(await parseError(res, 'Failed to update session title'))
    }
    return res.json()
  },

  optimizePrompt: async (prompt) => {
    const res = await fetch(`${API_BASE}/v1/chat/optimize-prompt`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ prompt }),
    })
    if (!res.ok) {
      throw new Error(await parseError(res, 'Failed to optimize prompt'))
    }
    return res.json()
  },

  getSavedPrompts: async () => {
    const res = await fetch(`${API_BASE}/v1/chat/saved-prompts`, {
      headers: { ...getAuthHeaders() },
    })
    if (!res.ok) {
      throw new Error(await parseError(res, 'Failed to get saved prompts'))
    }
    return res.json()
  },

  createSavedPrompt: async (name, content) => {
    const res = await fetch(`${API_BASE}/v1/chat/saved-prompts`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ name, content }),
    })
    if (!res.ok) {
      throw new Error(await parseError(res, 'Failed to create saved prompt'))
    }
    return res.json()
  },

  deleteSavedPrompt: async (promptId) => {
    const res = await fetch(`${API_BASE}/v1/chat/saved-prompts/${promptId}`, {
      method: 'DELETE',
      headers: { ...getAuthHeaders() },
    })
    if (!res.ok) {
      throw new Error(await parseError(res, 'Failed to delete saved prompt'))
    }
  },

  getMemorySettings: async () => {
    const res = await fetch(`${API_BASE}/v1/chat/memory/settings`, {
      headers: { ...getAuthHeaders() },
    })
    if (!res.ok) {
      throw new Error(await parseError(res, 'Failed to get memory settings'))
    }
    return res.json()
  },

  updateMemorySettings: async (enabled) => {
    const res = await fetch(`${API_BASE}/v1/chat/memory/settings`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ enabled }),
    })
    if (!res.ok) {
      throw new Error(await parseError(res, 'Failed to update memory settings'))
    }
    return res.json()
  },

  getMemories: async () => {
    const res = await fetch(`${API_BASE}/v1/chat/memory`, {
      headers: { ...getAuthHeaders() },
    })
    if (!res.ok) {
      throw new Error(await parseError(res, 'Failed to get memories'))
    }
    return res.json()
  },

  deleteMemory: async (memoryId) => {
    const res = await fetch(`${API_BASE}/v1/chat/memory/${encodeURIComponent(memoryId)}`, {
      method: 'DELETE',
      headers: { ...getAuthHeaders() },
    })
    if (!res.ok) {
      throw new Error(await parseError(res, 'Failed to delete memory'))
    }
  },

  clearMemories: async () => {
    const res = await fetch(`${API_BASE}/v1/chat/memory`, {
      method: 'DELETE',
      headers: { ...getAuthHeaders() },
    })
    if (!res.ok) {
      throw new Error(await parseError(res, 'Failed to clear memories'))
    }
  },
}

export const searchAPI = {
  search: async (prompt, sessionId = null, createNewSession = false, researchEnabled = false) => {
    const res = await fetch(`${API_BASE}/v1/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({
        prompt,
        session_id: sessionId,
        create_new_session: createNewSession,
        research_enabled: researchEnabled,
      }),
    })
    if (!res.ok) {
      throw new Error(await parseError(res, 'Search failed'))
    }
    return res.json()
  },
}

export const wsChatAPI = {
  createSocket: () => {
    const token = authAPI.getToken()
    if (!token) {
      throw new Error('Missing auth token')
    }

    return new WebSocket(`${WS_BASE}/ws/chat?token=${encodeURIComponent(token)}`)
  },
}

export const documentAPI = {
  upload: async (files, sessionId = null, createNewSession = false, onProgress = null) => {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    if (sessionId) formData.append('session_id', sessionId)
    formData.append('create_new_session', createNewSession ? 'true' : 'false')
    const token = authAPI.getToken()

    return await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', `${API_BASE}/upload`)

      if (token) {
        xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      }

      xhr.upload.onprogress = (event) => {
        if (!onProgress || !event.lengthComputable || event.total <= 0) return
        const percentage = Math.min(100, Math.round((event.loaded / event.total) * 100))
        onProgress(percentage)
      }

      xhr.onload = () => {
        let payload = {}
        try {
          payload = xhr.responseText ? JSON.parse(xhr.responseText) : {}
        } catch {
          payload = {}
        }

        if (xhr.status >= 200 && xhr.status < 300) {
          if (onProgress) onProgress(100)
          resolve(payload)
          return
        }

        const detail = typeof payload?.detail === 'string' ? payload.detail : null
        reject(new Error(detail || 'File upload failed'))
      }

      xhr.onerror = () => reject(new Error('File upload failed'))
      xhr.onabort = () => reject(new Error('File upload cancelled'))
      xhr.send(formData)
    })
  },

  remove: async (fileId, sessionId = null) => {
    const query = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ''
    const res = await fetch(`${API_BASE}/upload/${encodeURIComponent(fileId)}${query}`, {
      method: 'DELETE',
      headers: {
        ...getAuthHeaders(),
      },
    })

    if (!res.ok) {
      throw new Error(await parseError(res, 'Failed to remove uploaded file'))
    }
  },

  getContent: async (fileId, sessionId = null) => {
    const query = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ''
    const res = await fetch(`${API_BASE}/upload/${encodeURIComponent(fileId)}/content${query}`, {
      headers: {
        ...getAuthHeaders(),
      },
    })

    if (!res.ok) {
      throw new Error(await parseError(res, 'Failed to fetch uploaded file content'))
    }
    return res.json()
  },
}
