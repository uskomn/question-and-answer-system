<template>
  <div class="message-wrapper" :class="[message.role, { loading: message.isLoading, error: message.isError }]">
    <div class="message-bubble">
      <!-- Avatar -->
      <div class="message-avatar">
        <svg v-if="message.role === 'user'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
          <circle cx="12" cy="7" r="4"/>
        </svg>
        <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
          <line x1="8" y1="21" x2="16" y2="21"/>
          <line x1="12" y1="17" x2="12" y2="21"/>
        </svg>
      </div>

      <!-- Content -->
      <div class="message-content">
        <!-- User Question (if bot message) -->
        <div v-if="message.role === 'bot' && message.question" class="message-question">
          <span class="question-label">Q:</span>
          <span class="question-text">{{ message.question }}</span>
        </div>

        <!-- Loading State -->
        <div v-if="message.isLoading" class="message-loading">
          <div class="loading-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span class="loading-text">Thinking...</span>
        </div>

        <!-- Message Text -->
        <div v-else class="message-text" :class="{ error: message.isError }">
          <p v-html="renderMarkdown(message.content)"></p>
        </div>

        <!-- Metrics (for bot messages) -->
        <div v-if="message.metrics && !message.isLoading" class="message-metrics">
          <span class="metric">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <polyline points="12,6 12,12 16,14"/>
            </svg>
            {{ message.metrics.inference_time_ms }}ms
          </span>
          <span class="metric">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
              <polyline points="22,4 12,14.01 9,11.01"/>
            </svg>
            {{ (message.metrics.confidence_score * 100).toFixed(1) }}%
          </span>
        </div>

        <!-- Timestamp -->
        <div class="message-timestamp">
          {{ formatTime(message.timestamp) }}
        </div>
      </div>

      <!-- Delete Button -->
      <button class="delete-btn" @click="$emit('delete', message.id)" title="Delete message">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { defineProps } from 'vue'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true
})

const props = defineProps({
  message: {
    type: Object,
    required: true
  }
})

defineEmits(['delete'])

function renderMarkdown(text) {
  if (!text) return ''
  return md.render(text)
}

function formatTime(timestamp) {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.message-wrapper {
  display: flex;
  animation: slideUp 0.3s ease;
}

.message-wrapper.user {
  justify-content: flex-end;
}

.message-wrapper.bot {
  justify-content: flex-start;
}

.message-wrapper.loading {
  opacity: 0.7;
}

.message-bubble {
  display: flex;
  gap: 0.75rem;
  max-width: 80%;
  position: relative;
}

.message-wrapper.user .message-bubble {
  flex-direction: row-reverse;
}

/* Avatar */
.message-avatar {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.message-wrapper.user .message-avatar {
  background-color: var(--primary);
  color: white;
}

.message-wrapper.bot .message-avatar {
  background-color: var(--secondary);
  color: var(--text-secondary);
}

.message-wrapper.error .message-avatar {
  background-color: var(--error);
  color: white;
}

/* Content */
.message-content {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 1rem;
  border-radius: var(--radius-lg);
}

.message-wrapper.user .message-content {
  background-color: var(--primary);
  color: white;
  border-bottom-right-radius: 4px;
}

.message-wrapper.bot .message-content {
  background-color: var(--background);
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
}

.message-wrapper.error .message-content {
  background-color: rgba(239, 68, 68, 0.1);
  border: 1px solid var(--error);
  color: var(--error);
}

/* Question (for bot messages) */
.message-question {
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 0.5rem;
}

.question-label {
  font-weight: 600;
  color: var(--primary);
  margin-right: 0.5rem;
}

.question-text {
  color: var(--text-secondary);
  font-size: 0.875rem;
}

/* Message Text */
.message-text {
  line-height: 1.6;
}

.message-text :deep(p) {
  margin: 0;
}

.message-text :deep(code) {
  background-color: rgba(0, 0, 0, 0.1);
  padding: 0.125rem 0.375rem;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 0.875em;
}

.message-wrapper.user .message-text :deep(code) {
  background-color: rgba(255, 255, 255, 0.2);
}

.message-text :deep(pre) {
  background-color: rgba(0, 0, 0, 0.05);
  padding: 1rem;
  border-radius: var(--radius-md);
  overflow-x: auto;
  margin: 0.5rem 0;
}

.message-text.error {
  color: var(--error);
}

/* Loading */
.message-loading {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: var(--text-muted);
}

.loading-dots {
  display: flex;
  gap: 4px;
}

.loading-dots span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--text-muted);
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) { animation-delay: -0.32s; }
.loading-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

/* Metrics */
.message-metrics {
  display: flex;
  gap: 1rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border);
  margin-top: 0.5rem;
}

.message-wrapper.user .message-metrics {
  border-top-color: rgba(255, 255, 255, 0.2);
}

.metric {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.message-wrapper.user .metric {
  color: rgba(255, 255, 255, 0.8);
}

/* Timestamp */
.message-timestamp {
  font-size: 0.7rem;
  color: var(--text-muted);
  text-align: right;
}

.message-wrapper.user .message-timestamp {
  color: rgba(255, 255, 255, 0.6);
}

/* Delete Button */
.delete-btn {
  position: absolute;
  top: 0;
  right: -28px;
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: all 0.2s ease;
}

.message-wrapper:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  background-color: var(--secondary);
  color: var(--error);
}

.message-wrapper.user .delete-btn {
  right: auto;
  left: -28px;
}

/* Animations */
@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
