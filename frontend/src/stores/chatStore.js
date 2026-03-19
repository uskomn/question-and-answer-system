import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import chatApi from '../api/chat'

export const useChatStore = defineStore('chat', () => {

  // ================= State =================

  const messages = ref([])
  const isLoading = ref(false)
  const isModelReady = ref(false)
  const modelInfo = ref(null)
  const error = ref(null)

  const lastMetrics = ref({
    inferenceTime: 0,
    confidence: 0
  })

  // ================= Getters =================

  const hasMessages = computed(() => messages.value.length > 0)

  const userMessages = computed(() =>
    messages.value.filter(m => m.role === 'user')
  )

  const botMessages = computed(() =>
    messages.value.filter(m => m.role === 'bot')
  )

  // ================= Actions =================

  // 检查后端健康状态
  async function checkHealth() {
    try {
      const response = await chatApi.health()
      isModelReady.value = response.status === 'ready'
      console.log("isModelReady",isModelReady)
      return isModelReady.value
    } catch (err) {
      console.error('Health check failed:', err)
      isModelReady.value = false
      error.value = 'Failed to connect to backend'
      return false
    }
  }

  // 获取模型信息
  async function fetchModelInfo() {

    try {

      const res = await chatApi.modelInfo()

      modelInfo.value = res.data

      return res.data

    } catch (err) {

      console.error('Failed to fetch model info:', err)

      return null
    }
  }

  // 发送问题
  async function sendMessage(question, context) {

    if (!question.trim() || !context.trim()) {

      error.value = 'Question and context are required'

      return null
    }

    // 用户消息
    const userMsg = {
      id: Date.now(),
      role: 'user',
      content: question,
      timestamp: new Date().toISOString()
    }

    messages.value.push(userMsg)

    // loading 占位消息
    const loadingId = Date.now() + 1

    messages.value.push({
      id: loadingId,
      role: 'bot',
      content: '',
      isLoading: true,
      timestamp: new Date().toISOString()
    })

    isLoading.value = true
    error.value = null

    try {

      const res = await chatApi.predict(question, context)

      // 删除 loading
      const index = messages.value.findIndex(m => m.id === loadingId)

      if (index !== -1) {
        messages.value.splice(index, 1)
      }

      // 添加机器人回答
      const botMsg = {
        id: Date.now(),
        role: 'bot',
        content: res.data.answer,
        question: res.data.question,
        metrics: res.data.metrics,
        timestamp: new Date().toISOString()
      }

      messages.value.push(botMsg)

      // 更新指标
      lastMetrics.value = {
        inferenceTime: res.data.metrics?.inference_time_ms || 0,
        confidence: res.data.metrics?.confidence_score || 0
      }

      return botMsg

    } catch (err) {

      const index = messages.value.findIndex(m => m.id === loadingId)

      if (index !== -1) {
        messages.value.splice(index, 1)
      }

      const msg =
        err.response?.data?.error ||
        err.message ||
        'Failed to get response'

      const errorMsg = {
        id: Date.now(),
        role: 'bot',
        content: `Error: ${msg}`,
        isError: true,
        timestamp: new Date().toISOString()
      }

      messages.value.push(errorMsg)

      error.value = msg

      return null

    } finally {

      isLoading.value = false
    }
  }

  // 清空聊天记录
  function clearHistory() {
    messages.value = []
    error.value = null
  }

  // 删除单条消息
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