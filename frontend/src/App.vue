<template>
  <router-view />
</template>

<script setup>
import { onMounted } from 'vue'
import { useAuthStore } from './stores/authStore'

const authStore = useAuthStore()

// Initialize auth state from localStorage on app mount
onMounted(() => {
  // Just ensure auth state is initialized
  authStore.checkAuth()
})
</script>

<style>
/* Global styles are in assets/main.css */
</style>
