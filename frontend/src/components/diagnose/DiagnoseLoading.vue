<template>
  <div class="diag-loading">
    <div class="diag-loading__card">
      <!-- Pulsing AI Icon -->
      <div class="diag-loading__icon-ring">
        <div class="diag-loading__icon-inner">
          <el-icon :size="36"><MagicStick /></el-icon>
        </div>
        <div class="diag-loading__ring diag-loading__ring--1"></div>
        <div class="diag-loading__ring diag-loading__ring--2"></div>
        <div class="diag-loading__ring diag-loading__ring--3"></div>
      </div>

      <h2 class="diag-loading__title">AI 老师正在解构题目...</h2>
      <p class="diag-loading__subtitle">请稍候，正在为你进行深度分析</p>

      <!-- Progress Steps -->
      <div class="diag-loading__steps">
        <div
          v-for="(step, idx) in steps"
          :key="step.text"
          class="diag-step"
          :class="{ 'diag-step--active': currentStep >= idx, 'diag-step--done': currentStep > idx }"
        >
          <div class="diag-step__icon">
            <el-icon v-if="currentStep > idx"><CircleCheckFilled /></el-icon>
            <div v-else-if="currentStep === idx" class="diag-step__spinner"></div>
            <div v-else class="diag-step__dot"></div>
          </div>
          <span class="diag-step__text">{{ step.text }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { CircleCheckFilled, MagicStick } from '@element-plus/icons-vue'

const steps = [
  { text: '正在识别数学符号...' },
  { text: '正在检索向量知识库...' },
  { text: '正在剖析错因链条...' },
]

const currentStep = ref(-1)
let timer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  let idx = 0
  timer = setInterval(() => {
    if (idx < steps.length) {
      currentStep.value = idx
      idx++
    } else if (timer) {
      clearInterval(timer)
    }
  }, 1800)
  // Start first step immediately
  currentStep.value = 0
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>
