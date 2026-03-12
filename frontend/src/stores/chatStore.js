import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

// Create axios instance
const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

export const useChatStore = defineStore('chat', () => {
  // State
  const messages = ref([])
  const isLoading = ref(false)
  const isModelReady = ref(false)
  const modelInfo = ref(null)
  const error = ref(null)
  const lastMetrics = ref({
    inferenceTime: 0,
    confidence: 0
  })

  // Getters
  const hasMessages = computed(() => messages.value.length > 0)
  
  const userMessages = computed(() => 
    messages.value.filter(m => m.role === 'user')
  )
  
  const botMessages = computed(() => 
    messages.value.filter(m => m.role === 'bot')
  )

  // Actions
  async function checkHealth() {
    try {
      const response = await api.get('/health')
      isModelReady.value = response.data.status === 'ready'
      return isModelReady.value
    } catch (err) {
      console.error('Health check failed:', err)
      isModelReady.value = false
      error.value = 'Failed to connect to backend'
      return false
    }
  }

  async function fetchModelInfo() {
    try {
      const response = await api.get('/model/info')
      modelInfo.value = response.data
      return response.data
    } catch (err) {
      console.error('Failed to fetch model info:', err)
      return null
    }
  }

  async function sendMessage(question, context) {
    if (!question.trim() || !context.trim()) {
      error.value = 'Question and context are required'
      return null
    }

    // Add user message
    const userMsg = {
      id: Date.now(),
      role: 'user',
      content: question,
      timestamp: new Date().toISOString()
    }
    messages.value.push(userMsg)

    // Add loading placeholder
    const loadingId = Date.now() + 1
    const loadingMsg = {
      id: loadingId,
      role: 'bot',
      content: '',
      isLoading: true,
      timestamp: new Date().toISOString()
    }
    messages.value.push(loadingMsg)

    isLoading.value = true
    error.value = null

    try {
      const response = await api.post('/predict', {
        question: question,
        context: context,
        params: {
          temperature: 0.7,
          max_answer_len: 50
        }
      })

      // Remove loading message
      const loadingIndex = messages.value.findIndex(m => m.id === loadingId)
      if (loadingIndex !== -1) {
        messages.value.splice(loadingIndex, 1)
      }

      // Add bot response
      const botMsg = {
        id: Date.now(),
        role: 'bot',
        content: response.data.answer,
        question: response.data.question,
        metrics: response.data.metrics,
        timestamp: new Date().toISOString()
      }
      messages.value.push(botMsg)

      // Update metrics
      lastMetrics.value = {
        inferenceTime: response.data.metrics.inference_time_ms,
        confidence: response.data.metrics.confidence_score
      }

      return botMsg
    } catch (err) {
      // Remove loading message
      const loadingIndex = messages.value.findIndex(m => m.id === loadingId)
      if (loadingIndex !== -1) {
        messages.value.splice(loadingIndex, 1)
      }

      // Add error message
      const errorMsg = {
        id: Date.now(),
        role: 'bot',
        content: `Error: ${err.response?.data?.error || err.message || 'Failed to get response'}`,
        isError: true,
        timestamp: new Date().toISOString()
      }
      messages.value.push(errorMsg)
      
      error.value = errorMsg.content
      return null
    } finally {
      isLoading.value = false
    }
  }

  function clearHistory() {
    messages.value = []
    error.value = null
  }

  function removeMessage(id) {
    const index = messages.value.findIndex(m => m.id === id)
    if (index !== -1) {
      messages.value.splice(index, 1)
    }
  }

  return {
    // State
    messages,
    isLoading,
    isModelReady,
    modelInfo,
    error,
    lastMetrics,
    // Getters
    hasMessages,
    userMessages,
    botMessages,
    // Actions
    checkHealth,
    fetchModelInfo,
    sendMessage,
    clearHistory,
    removeMessage
  }
})
