<template>
  <el-config-provider>
    <div class="app-shell">
      <aside class="side-nav">
        <RouterLink class="brand" to="/diagnose">
          <span class="brand-mark">E</span>
          <span>EduMath Agent</span>
        </RouterLink>

        <nav>
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
          <RouterLink to="/home">
            <el-icon><Grid /></el-icon>
            <span>总览</span>
          </RouterLink>
        </nav>
      </aside>

      <RouterView />
    </div>
  </el-config-provider>
</template>

<script setup lang="ts">
import { Aim, Grid, Notebook, TrendCharts } from '@element-plus/icons-vue'
</script>
