<template>
  <main class="page-shell diag-page">
    <!-- Phase: Input -->
    <Transition name="phase-fade" mode="out-in">
      <DiagnoseInputCard
        v-if="phase === 'input'"
        key="input"
        @submit="handleDiagnose"
      />

      <!-- Phase: Loading -->
      <DiagnoseLoading
        v-else-if="phase === 'loading'"
        key="loading"
      />

      <!-- Phase: Result -->
      <div v-else-if="phase === 'result'" key="result" class="diag-result-layout">
        <!-- Top Bar -->
        <div class="diag-result-topbar">
          <el-button text @click="resetToInput">
            <el-icon class="el-icon--left"><Back /></el-icon>
            新的诊断
          </el-button>
        </div>

        <!-- Two-column layout -->
        <div class="diag-result-grid">
          <div class="diag-result-grid__left">
            <DiagnoseResultPanel
              :result="result!"
              :practice-question="practiceQuestion"
              :practice-answer="practiceAnswer"
              :practice-assist-result="practiceAssistResult"
              :grading="grading"
              :practice-ocr-loading="practiceOcrLoading"
              @update:practice-answer="practiceAnswer = $event"
              @submit-practice="submitPractice"
              @request-assist="requestPracticeAssist($event)"
              @practice-image-change="handlePracticeImageChange"
            />
          </div>
          <div class="diag-result-grid__right">
            <DiagnoseSidebar
              :result="result!"
              :variant-questions="variantQuestions"
              :variant-loading="variantLoading"
              @select-question="selectPractice"
              @generate-variants="requestVariantQuestions"
            />
          </div>
        </div>
      </div>
    </Transition>
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Back } from '@element-plus/icons-vue'
import axios from 'axios'

import {
  assistPractice,
  diagnoseWrongQuestion,
  type DiagnoseResponse,
  type PracticeAssistResponse,
  type SimilarQuestion,
} from '../api/diagnose'
import { uploadOcrImage } from '../api/ocr'
import { generateVariantQuestions, type GeneratedQuestion } from '../api/recommend'

import DiagnoseInputCard from '../components/diagnose/DiagnoseInputCard.vue'
import DiagnoseLoading from '../components/diagnose/DiagnoseLoading.vue'
import DiagnoseResultPanel from '../components/diagnose/DiagnoseResultPanel.vue'
import DiagnoseSidebar from '../components/diagnose/DiagnoseSidebar.vue'

// --- State ---
const loading = ref(false)
const result = ref<DiagnoseResponse | null>(null)
const lastQuestionText = ref('')

const grading = ref(false)
const practiceQuestion = ref<SimilarQuestion | null>(null)
const practiceAnswer = ref('')
const practiceAssistResult = ref<PracticeAssistResponse | null>(null)
const practiceOcrLoading = ref(false)

const variantQuestions = ref<GeneratedQuestion[]>([])
const variantLoading = ref(false)

const phase = computed<'input' | 'loading' | 'result'>(() => {
  if (loading.value) return 'loading'
  if (result.value) return 'result'
  return 'input'
})

// --- Diagnosis ---
async function handleDiagnose(payload: { question_text: string; student_answer: string }) {
  loading.value = true
  result.value = null
  practiceQuestion.value = null
  practiceAssistResult.value = null
  variantQuestions.value = []
  lastQuestionText.value = payload.question_text

  try {
    const studentId = localStorage.getItem('edumath_student_id') || 'S001'
    const response = await diagnoseWrongQuestion({
      student_id: studentId,
      question_text: payload.question_text,
      student_answer: payload.student_answer,
    })
    result.value = response.data
  } catch (err) {
    if (axios.isAxiosError(err)) {
      const status = err.response?.status
      const detail = typeof err.response?.data === 'string'
        ? err.response?.data
        : (err.response?.data as any)?.detail
      ElMessage.error(
        status
          ? `诊断失败（HTTP ${status}）${detail ? `：${detail}` : ''}`
          : `无法连接诊断服务：${err.message}`,
      )
    } else {
      ElMessage.error('诊断服务暂时不可用')
    }
  } finally {
    loading.value = false
  }
}

function resetToInput() {
  result.value = null
  practiceQuestion.value = null
  practiceAssistResult.value = null
  variantQuestions.value = []
}

// --- Practice ---
function selectPractice(question: SimilarQuestion) {
  practiceQuestion.value = question
  practiceAnswer.value = ''
  practiceAssistResult.value = null
}

async function submitPractice() {
  if (!practiceQuestion.value || !practiceAnswer.value.trim()) {
    ElMessage.warning('请先填写答案，或写"不会/没思路"获取提示')
    return
  }
  await requestPracticeAssist('auto')
}

async function requestPracticeAssist(mode: string) {
  if (!practiceQuestion.value) {
    ElMessage.warning('请先选择一道题')
    return
  }

  grading.value = true
  try {
    const studentId = localStorage.getItem('edumath_student_id') || 'S001'
    const response = await assistPractice({
      student_id: studentId,
      question_id: practiceQuestion.value.id,
      student_input: practiceAnswer.value.trim(),
      recognized_answer: practiceAnswer.value.trim(),
      mode: mode as any,
    })
    practiceAssistResult.value = response.data
  } catch (err) {
    if (axios.isAxiosError(err)) {
      const status = err.response?.status
      ElMessage.error(status ? `批改失败（HTTP ${status}）` : `无法连接批改服务：${err.message}`)
    } else {
      ElMessage.error('批改服务暂时不可用')
    }
  } finally {
    grading.value = false
  }
}

async function handlePracticeImageChange(uploadFile: { raw?: File; name?: string }) {
  const rawFile = uploadFile.raw
  if (!rawFile) return

  practiceOcrLoading.value = true
  try {
    const response = await uploadOcrImage(rawFile)
    practiceAnswer.value =
      response.data.corrected_text ||
      response.data.vision_text ||
      response.data.pix2text_text ||
      response.data.ocr_text
    ElMessage.success('作答图片已识别')
  } catch {
    ElMessage.error('作答图片识别失败')
  } finally {
    practiceOcrLoading.value = false
  }
}

// --- Variants ---
async function requestVariantQuestions() {
  if (!result.value) return
  variantLoading.value = true
  try {
    const response = await generateVariantQuestions({
      question_text: lastQuestionText.value,
      knowledge_points: result.value.knowledge_points,
      difficulty: result.value.difficulty,
      count: 3,
    })
    variantQuestions.value = response.data.questions
    if (variantQuestions.value.length) {
      ElMessage.success(`已生成 ${variantQuestions.value.length} 道变式题`)
    } else {
      ElMessage.info('暂无变式题，请稍后重试')
    }
  } catch {
    ElMessage.error('变式题生成失败')
  } finally {
    variantLoading.value = false
  }
}
</script>
