<template>
  <div class="app-container">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <div class="logo">
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect width="32" height="32" rx="8" fill="#4F46E5"/>
            <path d="M8 12h16M8 16h12M8 20h14" stroke="white" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="header-title">
          <h1>LiteQA</h1>
          <span class="subtitle">Lightweight Transformer Q&A</span>
        </div>
      </div>
      
      <div class="header-right">
        <!-- User Menu -->
        <div class="user-menu">
          <div class="user-info">
            <span class="user-avatar">
              {{ authStore.username.charAt(0).toUpperCase() }}
            </span>
            <span class="user-name">{{ authStore.username }}</span>
          </div>
          <button class="btn btn-ghost" @click="handleLogout" title="Logout">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
              <polyline points="16,17 21,12 16,7"/>
              <line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
          </button>
        </div>
      </div>
    </header>

    <!-- Metrics Bar -->
    <div class="metrics-bar" v-if="chatStore.lastMetrics.inferenceTime > 0">
      <div class="metric-item">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="12,6 12,12 16,14"/>
        </svg>
        <span class="metric-label">Inference Time:</span>
        <span class="metric-value">{{ chatStore.lastMetrics.inferenceTime.toFixed(1) }}ms</span>
      </div>
      <div class="metric-item">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
          <polyline points="22,4 12,14.01 9,11.01"/>
        </svg>
        <span class="metric-label">Confidence:</span>
        <span class="metric-value">{{ (chatStore.lastMetrics.confidence * 100).toFixed(1) }}%</span>
      </div>
    </div>

    <!-- Main Content -->
    <main class="main-content">
      <!-- Chat Area -->
      <div class="chat-container" ref="chatContainer">
        <!-- Welcome Screen -->
        <div class="welcome-screen" v-if="!chatStore.hasMessages">
          <div class="welcome-icon">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" stroke-width="1.5">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <h2>Welcome, {{ authStore.username }}!</h2>
          <p>Ask questions based on the provided context using our lightweight distilled transformer model.</p>
          <div class="example-questions">
            <p class="example-label">Try these examples:</p>
            <button class="example-btn" @click="loadExample(0)">
              "What is machine learning?"
            </button>
            <button class="example-btn" @click="loadExample(1)">
              "What are the benefits of transformers?"
            </button>
          </div>
        </div>

        <!-- Messages -->
        <div class="messages-list" v-else>
          <MessageBubble
            v-for="message in chatStore.messages"
            :key="message.id"
            :message="message"
            @delete="chatStore.removeMessage(message.id)"
          />
        </div>
      </div>

      <!-- Input Area -->
      <div class="input-area">
        <div class="input-container">
          <div class="input-row">
            <textarea
              v-model="question"
              placeholder="Enter your question..."
              @keydown.enter.exact.prevent="handleSend"
              :disabled="chatStore.isLoading || !chatStore.isModelReady"
              rows="1"
              ref="questionInput"
            ></textarea>
          </div>
          <div class="input-actions">
            <button 
              class="btn btn-secondary" 
              @click="chatStore.clearHistory"
              :disabled="!chatStore.hasMessages || chatStore.isLoading"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3,6 5,6 21,6"/>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
              Clear
            </button>
            <button 
              class="btn btn-primary" 
              @click="handleSend"
              :disabled="!canSend || chatStore.isLoading"
            >
              <svg v-if="!chatStore.isLoading" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="22" y1="2" x2="11" y2="13"/>
                <polygon points="22,2 15,22 11,13 2,9"/>
              </svg>
              <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="animate-spin">
                <circle cx="12" cy="12" r="10" stroke-dasharray="60" stroke-dashoffset="20"/>
              </svg>
              {{ chatStore.isLoading ? 'Processing...' : 'Send' }}
            </button>
          </div>
        </div>
      </div>
    </main>

    <!-- Error Toast -->
    <div class="error-toast" v-if="chatStore.error" @click="chatStore.error = null">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <line x1="15" y1="9" x2="9" y2="15"/>
        <line x1="9" y1="9" x2="15" y2="15"/>
      </svg>
      <span>{{ chatStore.error }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '../stores/chatStore'
import { useAuthStore } from '../stores/authStore'
import MessageBubble from '../components/MessageBubble.vue'

const router = useRouter()
const chatStore = useChatStore()
const authStore = useAuthStore()

// Refs
const question = ref('')
const context = ref('')
const chatContainer = ref(null)
const questionInput = ref(null)
const contextInput = ref(null)

// Example data
const examples = [
  {
    question: "What is machine learning?",
    context: "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed. It focuses on developing algorithms that can access data and use it to learn patterns and make decisions. Machine learning algorithms build models based on sample data, known as training data, in order to make predictions or decisions."
  },
  {
    question: "What are the benefits of transformers?",
    context: "Transformers have revolutionized natural language processing and other fields. Key benefits include: 1) Parallel processing - unlike RNNs, transformers can process entire sequences simultaneously. 2) Long-range dependencies - attention mechanisms allow modeling of relationships between distant elements. 3) Transfer learning - pre-trained models can be fine-tuned for various tasks. 4) Scalability - transformers handle large datasets effectively. 5) State-of-the-art performance - they achieve best results on many benchmarks."
  }
]

// Computed
const canSend = computed(() => {
  return question.value.trim() && context.value.trim() && chatStore.isModelReady
})

// Methods
async function handleSend() {
  if (!canSend.value || chatStore.isLoading) return
  
  await chatStore.sendMessage(question.value, context.value)
  
  // Clear inputs after sending
  question.value = ''
  context.value = ''
  
  // Scroll to bottom
  await nextTick()
  scrollToBottom()
}

function scrollToBottom() {
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

function loadExample(index) {
  const example = examples[index]
  question.value = example.question
  context.value = example.context
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}

// Watch for new messages
watch(() => chatStore.messages.length, () => {
  nextTick(() => {
    scrollToBottom()
  })
})

// Lifecycle
onMounted(async () => {
  await chatStore.checkHealth()
  await chatStore.fetchModelInfo()
})
</script>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: var(--surface);
}

/* Header */
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem;
  background-color: var(--background);
  border-bottom: 1px solid var(--border);
  box-shadow: var(--shadow-sm);
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.logo {
  display: flex;
  align-items: center;
}

.header-title h1 {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.subtitle {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.user-menu {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: var(--primary);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.875rem;
}

.user-name {
  font-weight: 500;
  color: var(--text-primary);
}

/* Metrics Bar */
.metrics-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2rem;
  padding: 0.75rem 1.5rem;
  background-color: var(--background);
  border-bottom: 1px solid var(--border);
}

.metric-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
}

.metric-item svg {
  color: var(--primary);
}

.metric-label {
  color: var(--text-secondary);
}

.metric-value {
  font-weight: 600;
  color: var(--text-primary);
}

/* Main Content */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

/* Welcome Screen */
.welcome-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  padding: 2rem;
}

.welcome-icon {
  margin-bottom: 1.5rem;
  opacity: 0.8;
}

.welcome-screen h2 {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 0.75rem;
}

.welcome-screen p {
  color: var(--text-secondary);
  max-width: 500px;
  margin-bottom: 2rem;
}

.example-questions {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.example-label {
  font-size: 0.875rem;
  color: var(--text-muted);
  margin-bottom: 0.5rem;
}

.example-btn {
  padding: 0.75rem 1.5rem;
  background-color: var(--background);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.example-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  background-color: rgba(79, 70, 229, 0.05);
}

/* Messages List */
.messages-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 800px;
  margin: 0 auto;
}

/* Input Area */
.input-area {
  padding: 1rem 1.5rem;
  background-color: var(--background);
  border-top: 1px solid var(--border);
}

.input-container {
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.input-row {
  display: flex;
  gap: 0.75rem;
}

.input-row textarea {
  flex: 1;
}

.input-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

/* Error Toast */
.error-toast {
  position: fixed;
  bottom: 100px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background-color: var(--error);
  color: white;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  cursor: pointer;
  animation: slideUp 0.3s ease;
  z-index: 100;
}

.error-toast svg {
  flex-shrink: 0;
}

/* Animations */
@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
