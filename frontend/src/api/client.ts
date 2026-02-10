import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor to handle token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        try {
          const response = await axios.post('/api/auth/refresh', {
            refresh_token: refreshToken,
          })

          const { access_token, refresh_token } = response.data
          localStorage.setItem('access_token', access_token)
          localStorage.setItem('refresh_token', refresh_token)

          originalRequest.headers.Authorization = `Bearer ${access_token}`
          return api(originalRequest)
        } catch (refreshError) {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          window.location.href = '/login'
        }
      } else {
        localStorage.removeItem('access_token')
        window.location.href = '/login'
      }
    }

    return Promise.reject(error)
  }
)

export default api

// Auth API
export const authApi = {
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),
  me: () => api.get('/auth/me'),
  refresh: (refreshToken: string) =>
    api.post('/auth/refresh', { refresh_token: refreshToken }),
}

// Admin API
export const adminApi = {
  listUsers: (skip = 0, limit = 50) =>
    api.get('/admin/users', { params: { skip, limit } }),
  createUser: (data: { name: string; email: string; password: string; role: string }) =>
    api.post('/admin/users', data),
  updateUser: (id: string, data: Record<string, unknown>) =>
    api.put(`/admin/users/${id}`, data),
  deleteUser: (id: string) => api.delete(`/admin/users/${id}`),
}

// Processos API
export const processosApi = {
  list: (status?: string, skip = 0, limit = 50) =>
    api.get('/processos', { params: { status_filter: status, skip, limit } }),
  create: (data: { titulo: string; numero?: string; descricao?: string; contexto?: string }) =>
    api.post('/processos', data),
  get: (id: string) => api.get(`/processos/${id}`),
  update: (id: string, data: Record<string, unknown>) =>
    api.put(`/processos/${id}`, data),
  delete: (id: string) => api.delete(`/processos/${id}`),
  share: (id: string, userId: string, role: string) =>
    api.post(`/processos/${id}/share`, { user_id: userId, role }),
  unshare: (processoId: string, userId: string) =>
    api.delete(`/processos/${processoId}/share/${userId}`),
}

// Documents API
export const documentsApi = {
  list: (processoId: string, tipo?: string, skip = 0, limit = 50) =>
    api.get('/documents', { params: { processo_id: processoId, tipo, skip, limit } }),
  upload: (formData: FormData) =>
    api.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  get: (id: string) => api.get(`/documents/${id}`),
  update: (id: string, data: { titulo?: string; tipo?: string; data_referencia?: string }) =>
    api.patch(`/documents/${id}`, data),
  download: (id: string) => api.get(`/documents/${id}/download`),
  delete: (id: string) => api.delete(`/documents/${id}`),
  search: (processoId: string, query: string) =>
    api.get('/documents/search', { params: { processo_id: processoId, q: query } }),
}

// Chat API
export const chatApi = {
  listConversations: (processoId?: string, skip = 0, limit = 50) =>
    api.get('/chat/conversations', { params: { processo_id: processoId, skip, limit } }),
  createConversation: (processoId: string, titulo?: string) =>
    api.post('/chat/conversations', { processo_id: processoId, titulo }),
  getConversation: (id: string) => api.get(`/chat/conversations/${id}`),
  updateConversation: (id: string, titulo: string) =>
    api.patch(`/chat/conversations/${id}`, { titulo }),
  deleteConversation: (id: string) => api.delete(`/chat/conversations/${id}`),
  sendMessage: (conversationId: string, content: string) =>
    api.post('/chat/message', { conversation_id: conversationId, content }),
  getSources: (messageId: string) => api.get(`/chat/sources/${messageId}`),
}

// Transacoes API
export const transacoesApi = {
  list: (processoId: string, params?: Record<string, unknown>) =>
    api.get('/transacoes', { params: { processo_id: processoId, ...params } }),
  get: (id: string) => api.get(`/transacoes/${id}`),
  update: (id: string, data: Record<string, unknown>) =>
    api.put(`/transacoes/${id}`, data),
  confirm: (id: string) => api.post(`/transacoes/${id}/confirm`),
  summary: (processoId: string) =>
    api.get('/transacoes/summary', { params: { processo_id: processoId } }),
}

// Reports API
export const reportsApi = {
  list: (processoId: string) =>
    api.get('/reports', { params: { processo_id: processoId } }),
  generate: (data: Record<string, unknown>) => api.post('/reports/excel', data),
  download: (id: string) => api.get(`/reports/${id}/download`),
  templates: () => api.get('/reports/templates'),
}

// Telegram API
export const telegramApi = {
  status: () => api.get('/telegram/status'),
  link: (code: string) => api.post('/telegram/link', null, { params: { telegram_code: code } }),
  unlink: () => api.delete('/telegram/unlink'),
}
