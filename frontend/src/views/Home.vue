<template>
  <main class="page-shell">
    <section class="surface">
      <div class="section-head">
        <div>
          <p class="eyebrow">EduMath Agent</p>
          <h1>项目总览</h1>
        </div>
      </div>

      <div class="overview-grid">
        <RouterLink class="overview-tile" to="/diagnose">
          <el-icon><Aim /></el-icon>
          <strong>错题诊断</strong>
          <span>识别知识点、错因和讲解路径</span>
        </RouterLink>
        <RouterLink class="overview-tile" to="/questions">
          <el-icon><Notebook /></el-icon>
          <strong>专题题库</strong>
          <span>按知识点和难度筛选题目</span>
        </RouterLink>
        <RouterLink class="overview-tile" to="/profile">
          <el-icon><TrendCharts /></el-icon>
          <strong>学生画像</strong>
          <span>跟踪薄弱点和错题记录</span>
        </RouterLink>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { Aim, Notebook, TrendCharts } from '@element-plus/icons-vue'
</script>
