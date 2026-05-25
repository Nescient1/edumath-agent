<template>
  <el-config-provider>
    <div v-if="isAuthPage" class="auth-page-wrapper">
      <RouterView />
    </div>
    <div v-else class="app-shell">
      <aside class="side-nav">
        <RouterLink class="brand" to="/home">
          <span class="brand-mark">E</span>
          <span>EduMath</span>
        </RouterLink>

        <nav>
          <RouterLink to="/home">
            <el-icon><Grid /></el-icon>
            <span>首页</span>
          </RouterLink>
          <RouterLink to="/diagnose">
            <el-icon><Aim /></el-icon>
            <span>诊断</span>
          </RouterLink>
          <RouterLink to="/questions">
            <el-icon><Notebook /></el-icon>
            <span>题库</span>
          </RouterLink>
          <RouterLink to="/profile">
            <el-icon><TrendCharts /></el-icon>
            <span>画像</span>
          </RouterLink>
        </nav>

        <div class="side-nav__footer">
          <div class="side-nav__user">
            <div class="user-avatar">{{ avatarLetter }}</div>
            <div class="user-info">
              <span class="user-name">{{ userName }}</span>
              <span class="user-id">{{ studentId }}</span>
            </div>
          </div>
          <el-button text size="small" @click="logout">
            <el-icon><SwitchButton /></el-icon>
          </el-button>
        </div>
      </aside>

      <RouterView />
    </div>
  </el-config-provider>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Aim, Grid, Notebook, SwitchButton, TrendCharts } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const isAuthPage = computed(() => route.path === '/login')

const studentId = computed(() => localStorage.getItem('edumath_student_id') || 'S001')
const userName = computed(() => localStorage.getItem('edumath_user_name') || '同学')
const avatarLetter = computed(() => userName.value.charAt(0).toUpperCase())

function logout() {
  localStorage.removeItem('edumath_student_id')
  localStorage.removeItem('edumath_user_name')
  router.push('/login')
}
</script>
