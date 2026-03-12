import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Response interceptor for error handling
apiClient.interceptors.response.use(
  response => response.data,
  error => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

export default {
  // Health check
  async checkHealth() {
    return apiClient.get('/health')
  },

  // Get model info
  async getModelInfo() {
    return apiClient.get('/model/info')
  },

  // Single question prediction
  async predict(question, context, params = {}) {
    return apiClient.post('/predict', {
      question,
      context,
      params
    })
  },

  // Batch prediction
  async batchPredict(questions) {
    return apiClient.post('/batch-predict', {
      questions
    })
  }
}
