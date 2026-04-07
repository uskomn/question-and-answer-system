import {defineStore} from 'pinia'
import {ref, computed} from 'vue'
import chatApi from '../api/chat'

export const useChatStore = defineStore('chat', () => {

    // ================= State =================
    const messages = ref([])
    const error = ref(null)
    const isLoading = ref(false)
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

    // 发送问题
    async function sendMessage({question, model}) {

        if (!question?.trim()) {
            error.value = 'Question cannot be empty'
            return null
        }

        error.value = null
        isLoading.value = true

        const now = Date.now()

        const userMsg = {
            id: now,
            role: 'user',
            content: question,
            timestamp: new Date().toISOString()
        }
        messages.value.push(userMsg)

        const loadingId = now + 1
        messages.value.push({
            id: loadingId,
            role: 'bot',
            content: '',
            isLoading: true,
            timestamp: new Date().toISOString()
        })

        try {
            const res = await chatApi.qa(question, model)

            removeMessage(loadingId)

            const botMsg = {
                id: Date.now(),
                role: 'bot',
                content: res?.answer || 'No response',
                question: res?.question,
                timestamp: new Date().toISOString()
            }

            messages.value.push(botMsg)
            return botMsg

        } catch (err) {

            removeMessage(loadingId)

            const msg =
                err?.response?.data?.error ||
                err?.message ||
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

    // 删除单条消息（复用）
    function removeMessage(id) {
        messages.value = messages.value.filter(m => m.id !== id)
    }

    // ================= 暴露 =================
    return {
        // state
        messages,
        error,
        isLoading,
        lastMetrics,

        // getters
        hasMessages,
        userMessages,
        botMessages,

        // actions
        sendMessage,
        clearHistory,
        removeMessage
    }
})