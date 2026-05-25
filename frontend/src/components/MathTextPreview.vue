<template>
  <div class="math-preview">
    <div class="math-preview__head">
      <span>{{ title }}</span>
      <el-tag v-if="statusText" size="small" effect="plain">
        {{ statusText }}
      </el-tag>
    </div>
    <div ref="previewRef" class="math-preview__body" />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'

declare global {
  interface Window {
    MathJax?: {
      tex?: unknown
      startup?: {
        promise?: Promise<void>
      }
      typesetClear?: (elements?: HTMLElement[]) => void
      typesetPromise?: (elements?: HTMLElement[]) => Promise<void>
    }
  }
}

const props = withDefaults(
  defineProps<{
    text: string
    title?: string
  }>(),
  {
    title: '公式预览',
  },
)

const previewRef = ref<HTMLElement | null>(null)
const mathReady = ref(false)
const mathFailed = ref(false)

const statusText = computed(() => {
  if (mathReady.value) return '已渲染'
  if (mathFailed.value) return '原文预览'
  return '加载中'
})

function configureMathJax() {
  window.MathJax = {
    tex: {
      inlineMath: [
        ['$', '$'],
        ['\\(', '\\)'],
      ],
      displayMath: [
        ['$$', '$$'],
        ['\\[', '\\]'],
      ],
      processEscapes: true,
    },
  }
}

function loadMathJax(): Promise<void> {
  if (window.MathJax?.typesetPromise) {
    mathReady.value = true
    return Promise.resolve()
  }

  const existing = document.querySelector<HTMLScriptElement>(
    'script[data-edumath-mathjax="1"]',
  )
  if (existing) {
    return new Promise((resolve, reject) => {
      existing.addEventListener('load', () => resolve(), { once: true })
      existing.addEventListener('error', () => reject(new Error('MathJax load failed')), {
        once: true,
      })
    })
  }

  configureMathJax()
  return new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js'
    script.async = true
    script.dataset.edumathMathjax = '1'
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('MathJax load failed'))
    document.head.appendChild(script)
  })
}

async function renderMath() {
  const target = previewRef.value
  if (!target) return

  target.textContent = props.text || '暂无内容'
  await nextTick()

  try {
    await loadMathJax()
    await window.MathJax?.startup?.promise
    window.MathJax?.typesetClear?.([target])
    await window.MathJax?.typesetPromise?.([target])
    mathReady.value = true
    mathFailed.value = false
  } catch {
    mathReady.value = false
    mathFailed.value = true
  }
}

watch(() => props.text, renderMath)
onMounted(renderMath)
</script>
