<template>
  <div class="auth-container">
    <div class="auth-card">
      <!-- Logo -->
      <div class="auth-logo">
        <svg width="48" height="48" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect width="32" height="32" rx="8" fill="#4F46E5"/>
          <path d="M8 12h16M8 16h12M8 20h14" stroke="white" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <h1>LiteQA</h1>
      </div>

      <!-- Step Indicator -->
      <div class="step-indicator">
        <div class="step" :class="{ active: currentStep >= 1, completed: currentStep > 1 }">
          <span class="step-number">1</span>
          <span class="step-label">邮箱</span>
        </div>
        <div class="step-line" :class="{ active: currentStep >= 2 }"></div>
        <div class="step" :class="{ active: currentStep >= 2, completed: currentStep > 2 }">
          <span class="step-number">2</span>
          <span class="step-label">验证</span>
        </div>
        <div class="step-line" :class="{ active: currentStep >= 3 }"></div>
        <div class="step" :class="{ active: currentStep >= 3 }">
          <span class="step-number">3</span>
          <span class="step-label">账户</span>
        </div>
      </div>

      <!-- Title -->
      <h2 v-if="currentStep === 1">输入邮箱地址</h2>
      <h2 v-else-if="currentStep === 2">验证邮箱地址</h2>
      <h2 v-else>创建账户</h2>

      <p class="auth-subtitle" v-if="currentStep === 1">
        我们会给你的邮箱发送一个验证码
      </p>
      <p class="auth-subtitle" v-else-if="currentStep === 2">
        一个六位的验证码发送给了{{ email }}
      </p>
      <p class="auth-subtitle" v-else>
        选择一个用户名和密码
      </p>

      <!-- Error Message -->
      <div v-if="error" class="error-message">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="15" y1="9" x2="9" y2="15"/>
          <line x1="9" y1="9" x2="15" y2="15"/>
        </svg>
        {{ error }}
      </div>

      <!-- Success Message -->
      <div v-if="successMessage" class="success-message">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
          <polyline points="22,4 12,14.01 9,11.01"/>
        </svg>
        {{ successMessage }}
      </div>

      <!-- Step 1: Email Input -->
      <form v-if="currentStep === 1" @submit.prevent="handleSendCode" class="auth-form">
        <div class="form-group">
          <label for="email">邮箱地址</label>
          <input
            id="email"
            v-model="email"
            type="email"
            placeholder="输入你的邮箱"
            required
            :disabled="isLoading"
          />
        </div>

        <button type="submit" class="btn btn-primary btn-block" :disabled="isLoading">
          <svg v-if="!isLoading" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
            <polyline points="22,6 12,13 2,6"/>
          </svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="animate-spin">
            <circle cx="12" cy="12" r="10" stroke-dasharray="60" stroke-dashoffset="20"/>
          </svg>
          {{ isLoading ? '发送中...' : '获取验证码' }}
        </button>
      </form>

      <!-- Step 2: Verification Code -->
      <form v-else-if="currentStep === 2" @submit.prevent="handleVerifyCode" class="auth-form">
        <div class="form-group">
          <label for="code">验证码</label>
          <input
            id="code"
            v-model="verificationCode"
            type="text"
            placeholder="输入六位的验证码"
            required
            :disabled="isLoading"
            maxlength="6"
            class="code-input"
          />
          <p class="input-hint">检查你的邮件来获取验证码</p>
        </div>

        <div class="button-group">
          <button
            type="button"
            class="btn btn-secondary btn-block"
            @click="handleResendCode"
            :disabled="countdown > 0 || isLoading"
          >
            {{ countdown > 0 ? `Resend in ${countdown}s` : '重新发送' }}
          </button>

          <button type="submit" class="btn btn-primary btn-block" :disabled="isLoading || verificationCode.length !== 6">
            <svg v-if="!isLoading" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="20,6 9,17 4,12"/>
            </svg>
            <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="animate-spin">
              <circle cx="12" cy="12" r="10" stroke-dasharray="60" stroke-dashoffset="20"/>
            </svg>
            {{ isLoading ? 'Verifying...' : '验证' }}
          </button>
        </div>

        <button type="button" class="btn btn-ghost btn-block" @click="goBackToStep1">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="19" y1="12" x2="5" y2="12"/>
            <polyline points="12,19 5,12 12,5"/>
          </svg>
          换一个邮箱
        </button>
      </form>

      <!-- Step 3: Account Details -->
      <form v-else @submit.prevent="handleRegister" class="auth-form">
        <div class="form-group">
          <label for="username">用户名</label>
          <input
            id="username"
            v-model="username"
            type="text"
            placeholder="选择一个用户名"
            required
            :disabled="isLoading"
            minlength="2"
          />
        </div>

        <div class="form-group">
          <label for="password">密码</label>
          <input
            id="password"
            v-model="password"
            type="password"
            placeholder="输入密码"
            required
            :disabled="isLoading"
            minlength="3"
          />
        </div>

        <div class="form-group">
          <label for="confirmPassword">验证密码</label>
          <input
            id="confirmPassword"
            v-model="confirmPassword"
            type="password"
            placeholder="验证你的密码"
            required
            :disabled="isLoading"
            minlength="3"
          />
        </div>

        <button type="submit" class="btn btn-primary btn-block" :disabled="isLoading">
          <svg v-if="!isLoading" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="8.5" cy="7" r="4"/>
            <line x1="20" y1="8" x2="20" y2="14"/>
            <line x1="23" y1="11" x2="17" y2="11"/>
          </svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="animate-spin">
            <circle cx="12" cy="12" r="10" stroke-dasharray="60" stroke-dashoffset="20"/>
          </svg>
          {{ isLoading ? '创建账户中...' : '创建账户' }}
        </button>
      </form>

      <!-- Login Link -->
      <p class="auth-footer">
        已经有一个账户?
        <router-link to="/login">登录</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore'

const router = useRouter()
const authStore = useAuthStore()

// =========================
// Form data
// =========================
const currentStep = ref(1)
const email = ref('')
const verificationCode = ref('')
const username = ref('')
const password = ref('')
const confirmPassword = ref('')

// =========================
// State
// =========================
const error = ref('')
const successMessage = ref('')
const isLoading = computed(() => authStore.isLoading) // ✅ 用 store 的 loading
const countdown = ref(0)
let countdownInterval = null

// =========================
// Computed
// =========================
const canSendCode = computed(() => {
  return email.value.trim() && email.value.includes('@')
})

// =========================
// Step 1：发送验证码
// =========================
async function handleSendCode() {
  error.value = ''
  successMessage.value = ''

  if (!canSendCode.value) {
    error.value = 'Please enter a valid email address'
    return
  }

  try {
    // ✅ 改为调用 store
    await authStore.sendCode(email.value)

    successMessage.value = 'Verification code sent! Check your email.'
    currentStep.value = 2
    startCountdown()

  } catch (err) {
    error.value = err.message || 'Failed to send verification code'
  }
}

// =========================
// 重发验证码
// =========================
async function handleResendCode() {
  if (countdown.value > 0) return

  error.value = ''
  successMessage.value = ''

  try {
    await authStore.sendCode(email.value)
    successMessage.value = 'New verification code sent!'
    startCountdown()
  } catch (err) {
    error.value = err.message || 'Failed to resend code'
  }
}

// =========================
// Step 2：验证验证码（前端仅做格式校验）
// =========================
async function handleVerifyCode() {
  error.value = ''

  if (verificationCode.value.length !== 6) {
    error.value = 'Please enter the complete 6-digit code'
    return
  }

  // ❗你的后端是“注册时验证 code”，这里不请求接口
  successMessage.value = 'Code looks good!'
  currentStep.value = 3
  stopCountdown()
}

// =========================
// Step 3：注册
// =========================
async function handleRegister() {
  error.value = ''

  if (password.value !== confirmPassword.value) {
    error.value = 'Passwords do not match'
    return
  }


  try {
    await authStore.register(
      username.value,
      email.value,
      password.value,
      verificationCode.value
    )

    successMessage.value = 'Account created successfully! Redirecting...'

    setTimeout(() => {
      router.push('/')
    }, 1500)

  } catch (err) {
    error.value = err.message
  }
}

// =========================
// 返回修改邮箱
// =========================
function goBackToStep1() {
  currentStep.value = 1
  verificationCode.value = ''
  stopCountdown()
}

// =========================
// 倒计时
// =========================
function startCountdown() {
  countdown.value = 60
  stopCountdown()

  countdownInterval = setInterval(() => {
    if (countdown.value > 0) {
      countdown.value--
    } else {
      stopCountdown()
    }
  }, 1000)
}

function stopCountdown() {
  if (countdownInterval) {
    clearInterval(countdownInterval)
    countdownInterval = null
  }
  countdown.value = 0
}

// =========================
// 销毁清理
// =========================
onUnmounted(() => {
  stopCountdown()
})
</script>

<style scoped>
.auth-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 1rem;
}

.auth-card {
  background: white;
  border-radius: 16px;
  padding: 2.5rem;
  width: 100%;
  max-width: 420px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.auth-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.auth-logo h1 {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

/* Step Indicator */
.step-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1.5rem;
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
}

.step-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: var(--secondary);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.875rem;
  transition: all 0.3s ease;
}

.step.active .step-number {
  background-color: var(--primary);
  color: white;
}

.step.completed .step-number {
  background-color: var(--success);
  color: white;
}

.step-label {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.step.active .step-label {
  color: var(--primary);
  font-weight: 500;
}

.step-line {
  width: 40px;
  height: 2px;
  background-color: var(--border);
  margin: 0 0.5rem;
  margin-bottom: 1.25rem;
  transition: background-color 0.3s ease;
}

.step-line.active {
  background-color: var(--primary);
}

.auth-card h2 {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text-primary);
  text-align: center;
  margin: 0 0 0.5rem 0;
}

.auth-subtitle {
  text-align: center;
  color: var(--text-secondary);
  margin-bottom: 1.5rem;
  font-size: 0.875rem;
}

.error-message {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background-color: rgba(239, 68, 68, 0.1);
  border: 1px solid var(--error);
  border-radius: var(--radius-md);
  color: var(--error);
  font-size: 0.875rem;
  margin-bottom: 1rem;
}

.success-message {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background-color: rgba(16, 185, 129, 0.1);
  border: 1px solid var(--success);
  border-radius: var(--radius-md);
  color: var(--success);
  font-size: 0.875rem;
  margin-bottom: 1rem;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-group label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary);
}

.form-group input {
  padding: 0.75rem 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 1rem;
  transition: all 0.2s ease;
}

.form-group input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.form-group input:disabled {
  background-color: var(--secondary);
  cursor: not-allowed;
}

.code-input {
  text-align: center;
  font-size: 1.5rem;
  letter-spacing: 0.5rem;
  font-weight: 600;
}

.input-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin: 0;
}

.button-group {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.btn-block {
  width: 100%;
  padding: 0.875rem;
  font-size: 1rem;
  font-weight: 500;
  margin-top: 0.5rem;
}

.auth-footer {
  text-align: center;
  margin-top: 1.5rem;
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.auth-footer a {
  color: var(--primary);
  font-weight: 500;
  text-decoration: none;
}

.auth-footer a:hover {
  text-decoration: underline;
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
