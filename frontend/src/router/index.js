import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/authStore'

// Import views
import Login from '../views/Login.vue'
import Register from '../views/Register.vue'
import Chat from '../views/Chat.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false, title: 'Login' }
  },
  {
    path: '/register',
    name: 'Register',
    component: Register,
    meta: { requiresAuth: false, title: 'Register' }
  },
  {
    path: '/',
    name: 'Chat',
    component: Chat,
    meta: { requiresAuth: true, title: 'Q&A System' }
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guard
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  
  // Update document title
  document.title = to.meta.title ? `${to.meta.title} | LiteQA` : 'LiteQA'
  
  // Check if route requires authentication
  if (to.meta.requiresAuth) {
    // If not authenticated, check if we have a token
    if (!authStore.isAuthenticated) {
      const token = localStorage.getItem('liteqa_token')
      if (token) {
        // Try to validate token
        const isValid = await authStore.checkAuth()
        if (!isValid) {
          return next({ name: 'Login', query: { redirect: to.fullPath } })
        }
      } else {
        return next({ name: 'Login', query: { redirect: to.fullPath } })
      }
    }
  }
  
  // If already authenticated and trying to access login/register, redirect to chat
  if ((to.name === 'Login' || to.name === 'Register') && authStore.isAuthenticated) {
    return next({ name: 'Chat' })
  }
  
  next()
})

export default router
