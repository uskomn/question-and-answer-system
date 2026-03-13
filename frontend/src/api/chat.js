import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor to add auth token
apiClient.interceptors.request.use(
  config => {
    const token = localStorage.getItem('liteqa_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// Response interceptor for error handling
apiClient.interceptors.response.use(
  response => response.data,
  error => {
    console.error('API Error:', error)
    
    // Handle 401 Unauthorized
    if (error.response?.status === 401) {
      // Clear auth data and redirect to login
      localStorage.removeItem('liteqa_token')
      localStorage.removeItem('liteqa_user')
      
      // Only redirect if not already on login page
      if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
        window.location.href = '/login'
      }
    }
    
    return Promise.reject(error)
  }
)

export default {
  // ==================== Auth Endpoints ====================
  
  // Login
  async login(email, password) {
    return apiClient.post('/auth/login', {
      email,
      password
    })
  },

  // Register
  async register(username, email, password) {
    return apiClient.post('/auth/register', {
      username,
      email,
      password
    })
  },

  // Get current user
  async getCurrentUser() {
    return apiClient.get('/auth/me')
  },

  // ==================== Model Endpoints ====================

  // Health check (public)
  async checkHealth() {
    return apiClient.get('/health')
  },

  // Get model info (protected)
  async getModelInfo() {
    return apiClient.get('/model/info')
  },

  // Single question prediction (protected)
  async predict(question, context, params = {}) {
    return apiClient.post('/predict', {
      question,
      context,
      params
    })
  },

  // Batch prediction (protected)
  async batchPredict(questions) {
    return apiClient.post('/batch-predict', {
      questions
    })
  }
}
