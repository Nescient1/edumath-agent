<template>
  <div class="result-panel">
    <!-- Header -->
    <div class="result-panel__header">
      <div>
        <p class="eyebrow">诊断结果</p>
        <h1>{{ result.error_type }}</h1>
      </div>
      <el-tag
        :type="result.difficulty === '困难' ? 'danger' : result.difficulty === '中等' ? 'warning' : 'success'"
        effect="plain"
        size="large"
      >
        {{ result.difficulty }}
      </el-tag>
    </div>

    <!-- Knowledge Points -->
    <div class="tag-row compact" style="margin-bottom: 20px">
      <KnowledgeTag v-for="kp in result.knowledge_points" :key="kp" :label="kp" />
    </div>

    <!-- Error Diagnosis -->
    <section class="result-panel__section">
      <h3>错因分析</h3>
      <MathTextPreview class="result-panel__math" :text="result.diagnosis" title="" />
    </section>

    <!-- Typewriter Explanation -->
    <section class="result-panel__section">
      <h3>个性化讲解</h3>
      <div class="typewriter-block">
        <MathTextPreview
          v-if="typewriterDone"
          class="result-panel__math"
          :text="result.explanation"
          title=""
        />
        <div v-else class="typewriter-text">
          <span>{{ displayedText }}</span><span class="typewriter-cursor">|</span>
        </div>
      </div>
    </section>

    <!-- Key Concepts -->
    <section v-if="result.key_concepts?.length" class="result-panel__section">
      <h3>核心考点</h3>
      <ul class="result-panel__concepts">
        <li v-for="concept in result.key_concepts" :key="concept">{{ concept }}</li>
      </ul>
    </section>

    <!-- Step-by-Step Explanation -->
    <section v-if="result.step_by_step_explanation?.length" class="result-panel__section">
      <h3>分步解析</h3>
      <div class="step-list">
        <div
          v-for="step in result.step_by_step_explanation"
          :key="step.step_number"
          class="step-card"
        >
          <div class="step-badge">{{ step.step_number }}</div>
          <div class="step-body">
            <strong>{{ step.title }}</strong>
            <MathTextPreview class="step-math" :text="step.content" title="" />
          </div>
        </div>
      </div>
    </section>

    <!-- General Strategy -->
    <section v-if="result.general_strategy" class="result-panel__section">
      <h3>通用策略</h3>
      <MathTextPreview class="result-panel__math" :text="result.general_strategy" title="" />
    </section>

    <!-- Common Pitfalls -->
    <section v-if="result.common_pitfalls?.length" class="result-panel__section">
      <div class="pitfalls-block">
        <h3 style="margin-bottom: 8px">常见陷阱</h3>
        <ul class="pitfalls-list">
          <li v-for="pitfall in result.common_pitfalls" :key="pitfall">{{ pitfall }}</li>
        </ul>
      </div>
    </section>

    <!-- Practice Section -->
    <section v-if="practiceQuestion" class="result-panel__practice">
      <div class="practice-header">
        <div>
          <p class="eyebrow">练习模式</p>
          <h2>{{ practiceQuestion.id === 'variant' ? '变式题练习' : '相似题练习' }}</h2>
        </div>
        <el-tag effect="plain">{{ practiceQuestion.difficulty }}</el-tag>
      </div>

      <MathTextPreview
        class="practice-q-preview"
        :text="practiceQuestion.question_text"
        title=""
      />

      <el-upload
        class="practice-upload"
        drag
        :show-file-list="false"
        :auto-upload="false"
        accept=".png,.jpg,.jpeg,.bmp,.webp,image/png,image/jpeg,image/bmp,image/webp"
        :on-change="handlePracticeImage"
      >
        <div class="practice-upload__inner">
          <el-icon><UploadFilled /></el-icon>
          <span>上传作答图片，或直接在下方输入</span>
        </div>
      </el-upload>

      <el-alert
        v-if="practiceOcrLoading"
        title="正在识别作答图片"
        type="info"
        :closable="false"
        show-icon
        style="border-radius: 12px"
      />

      <el-input
        v-model="practiceAnswer"
        type="textarea"
        :rows="4"
        resize="none"
        placeholder="写完整答案，或写：不会、没思路、只会求导、想看提示"
      />

      <div class="practice-actions">
        <el-button :loading="grading" @click="$emit('request-assist', 'hint')">提示</el-button>
        <el-button :loading="grading" @click="$emit('request-assist', 'answer')">答案</el-button>
        <el-button :loading="grading" @click="$emit('request-assist', 'solution')">解析</el-button>
        <el-button type="primary" :icon="Check" :loading="grading" @click="$emit('submit-practice')">
          提交批改
        </el-button>
      </div>

      <!-- Practice Result -->
      <div v-if="practiceAssistResult" class="practice-result">
        <el-progress
          v-if="practiceAssistResult.mode === 'grade' && practiceAssistResult.score != null"
          :percentage="practiceAssistResult.score"
          :status="practiceAssistResult.is_correct ? 'success' : 'warning'"
          :stroke-width="10"
          style="border-radius: 8px"
        />
        <MathTextPreview
          class="result-math-preview"
          :text="practiceAssistText"
          :title="practiceAssistTitle"
        />
        <MathTextPreview
          v-if="practiceAssistResult.reference_answer && practiceAssistResult.mode !== 'hint'"
          class="result-math-preview"
          :text="`参考答案：${practiceAssistResult.reference_answer}`"
          title="参考答案"
        />
        <MathTextPreview
          v-if="practiceAssistResult.solution"
          class="result-math-preview"
          :text="practiceAssistResult.solution"
          title="完整解析"
        />
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Check, UploadFilled } from '@element-plus/icons-vue'

import type { DiagnoseResponse, PracticeAssistResponse, SimilarQuestion } from '../../api/diagnose'
import KnowledgeTag from '../KnowledgeTag.vue'
import MathTextPreview from '../MathTextPreview.vue'

const props = defineProps<{
  result: DiagnoseResponse
  practiceQuestion: SimilarQuestion | null
  practiceAnswer: string
  practiceAssistResult: PracticeAssistResponse | null
  grading: boolean
  practiceOcrLoading: boolean
}>()

const emit = defineEmits<{
  'update:practiceAnswer': [value: string]
  'submit-practice': []
  'request-assist': [mode: string]
  'practice-image-change': [file: { raw?: File; name?: string }]
}>()

const practiceAnswer = computed({
  get: () => props.practiceAnswer,
  set: (v: string) => emit('update:practiceAnswer', v),
})

function handlePracticeImage(file: { raw?: File; name?: string }) {
  emit('practice-image-change', file)
}

// --- Typewriter Effect ---
const displayedChars = ref(0)
const typewriterDone = ref(false)
let typewriterTimer: ReturnType<typeof setInterval> | null = null

const displayedText = computed(() =>
  props.result.explanation.slice(0, displayedChars.value),
)

function startTypewriter() {
  displayedChars.value = 0
  typewriterDone.value = false
  const text = props.result.explanation
  const totalChars = text.length
  const speed = Math.max(10, Math.min(25, 2000 / totalChars))

  typewriterTimer = setInterval(() => {
    displayedChars.value += 1
    if (displayedChars.value >= totalChars) {
      typewriterDone.value = true
      if (typewriterTimer) clearInterval(typewriterTimer)
    }
  }, speed)
}

watch(() => props.result.explanation, () => {
  if (typewriterTimer) clearInterval(typewriterTimer)
  startTypewriter()
}, { immediate: false })

onMounted(startTypewriter)
onUnmounted(() => {
  if (typewriterTimer) clearInterval(typewriterTimer)
})

// --- Practice Assist ---
const practiceAssistTitle = computed(() => {
  const mode = props.practiceAssistResult?.mode
  if (mode === 'hint') return '解题提示'
  if (mode === 'answer') return '参考答案'
  if (mode === 'solution') return '解析说明'
  return '批改反馈'
})

const practiceAssistText = computed(() => {
  const r = props.practiceAssistResult
  if (!r) return ''
  const parts = [r.feedback || r.message]
  if (r.next_step) parts.push(`下一步：${r.next_step}`)
  if (r.score != null) parts.unshift(`本次得分：${r.score}`)
  return parts.filter(Boolean).join('\n')
})
</script>
