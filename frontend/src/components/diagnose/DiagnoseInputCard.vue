<template>
  <div class="input-card-wrapper">
    <div class="input-card">
      <div class="input-card__header">
        <h1>AI 错题诊断</h1>
        <p>上传错题图片或直接输入题目，AI 老师为你精准定位错因</p>
      </div>

      <!-- Upload Area -->
      <div class="upload-zone" :class="{ 'upload-zone--has-file': ocrFileName }">
        <div class="upload-scan-overlay"></div>
        <el-upload
          class="input-card__upload"
          drag
          :show-file-list="false"
          :auto-upload="false"
          accept=".png,.jpg,.jpeg,.bmp,.webp,image/png,image/jpeg,image/bmp,image/webp"
          :on-change="handleImageChange"
          :disabled="ocrLoading"
        >
          <div v-if="ocrLoading" class="upload-loading">
            <div class="upload-loading__spinner"></div>
            <p>正在识别图片文字...</p>
          </div>
          <div v-else-if="ocrFileName" class="upload-loaded">
            <el-icon class="upload-loaded__icon"><CircleCheckFilled /></el-icon>
            <p>{{ ocrFileName }}</p>
            <span class="upload-loaded__hint">点击重新上传</span>
          </div>
          <div v-else class="upload-empty">
            <el-icon class="upload-empty__icon"><UploadFilled /></el-icon>
            <p>拖拽错题图片到这里，或点击选择</p>
            <span>支持 PNG / JPG / WEBP</span>
          </div>
        </el-upload>
      </div>

      <!-- OCR Status -->
      <div v-if="ocrBlocks.length || pageCandidates.length > 1" class="ocr-result-bar">
        <div class="ocr-result-bar__head">
          <el-tag v-if="ocrEngine" type="success" effect="plain" size="small">
            {{ ocrEngineLabel }}
          </el-tag>
          <el-tag effect="plain" size="small">{{ ocrBlocks.length }} 行识别</el-tag>
        </div>
        <div v-if="pageCandidates.length > 1" class="candidate-list">
          <div
            v-for="c in pageCandidates"
            :key="`${c.question_no}-${c.question_text}`"
            class="candidate-chip"
            :class="{ 'candidate-chip--active': form.question_text === candidateToText(c) }"
            @click="usePageCandidate(c)"
          >
            <span>第 {{ c.question_no || '?' }} 题</span>
            <el-tag size="small" :type="c.confidence === 'high' ? 'success' : c.confidence === 'low' ? 'danger' : 'warning'" effect="plain">
              {{ confidenceLabel(c.confidence) }}
            </el-tag>
          </div>
        </div>
      </div>

      <!-- Question Preview/Edit -->
      <div class="input-card__question">
        <div class="input-card__question-head">
          <span>题目内容</span>
          <el-button
            size="small"
            text
            :icon="questionEditing ? View : EditPen"
            @click="questionEditing = !questionEditing"
          >
            {{ questionEditing ? '预览' : '编辑' }}
          </el-button>
        </div>
        <el-input
          v-if="questionEditing || !form.question_text.trim()"
          v-model="form.question_text"
          type="textarea"
          :rows="5"
          resize="none"
          placeholder="输入或粘贴题目，也可以上传图片自动识别..."
        />
        <MathTextPreview
          v-else
          class="input-card__preview"
          :text="form.question_text"
          title=""
        />
      </div>

      <!-- Student Answer -->
      <div class="input-card__answer">
        <el-input
          v-model="form.student_answer"
          type="textarea"
          :rows="3"
          resize="none"
          placeholder="你的错误答案或卡住的位置（选填，有助于更精准诊断）"
        />
      </div>

      <!-- Action Row -->
      <div class="input-card__actions">
        <el-button
          text
          size="small"
          @click="fillExample"
        >
          填入示例
        </el-button>
        <el-button
          type="primary"
          size="large"
          class="input-card__submit"
          :loading="false"
          @click="handleSubmit"
        >
          <el-icon class="el-icon--left"><MagicStick /></el-icon>
          开始诊断
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  CircleCheckFilled,
  EditPen,
  MagicStick,
  UploadFilled,
  View,
} from '@element-plus/icons-vue'
import axios from 'axios'

import { uploadOcrImage, uploadPageOcrImage, type OcrBlock, type PageQuestionCandidate } from '../../api/ocr'
import MathTextPreview from '../MathTextPreview.vue'

const emit = defineEmits<{
  submit: [payload: { question_text: string; student_answer: string }]
}>()

const form = reactive({
  question_text: '已知函数 f(x)=x^3-3x，求函数的单调区间和极值。',
  student_answer: '我只求了导数 f\'(x)=3x^2-3，不知道后面怎么做。',
})

const ocrLoading = ref(false)
const ocrFileName = ref('')
const ocrBlocks = ref<OcrBlock[]>([])
const ocrEngine = ref('')
const pageCandidates = ref<PageQuestionCandidate[]>([])
const questionEditing = ref(false)

const ocrEngineLabel = computed(() => {
  const labels: Record<string, string> = {
    vision: '视觉模型',
    pix2text: 'Pix2Text',
    paddleocr: 'PaddleOCR',
  }
  return labels[ocrEngine.value] || ocrEngine.value
})

function fillExample() {
  form.question_text = '已知函数 f(x)=ln x-x，求 f(x) 的单调区间和极值。'
  form.student_answer = '我忘了先写定义域，后面极值也不知道怎么判断。'
  questionEditing.value = false
}

function confidenceLabel(confidence: string) {
  const labels: Record<string, string> = { high: '清晰', medium: '需确认', low: '需校对' }
  return labels[confidence] || confidence || '需确认'
}

function candidateToText(candidate: PageQuestionCandidate) {
  const parts = [candidate.question_text.trim()]
  if (candidate.options.length) parts.push(candidate.options.join('\n'))
  if (candidate.answer.trim()) parts.push(`答案：${candidate.answer.trim()}`)
  if (candidate.solution.trim()) parts.push(`解析：${candidate.solution.trim()}`)
  return parts.filter(Boolean).join('\n')
}

function usePageCandidate(candidate: PageQuestionCandidate) {
  form.question_text = candidateToText(candidate)
  questionEditing.value = false
  ElMessage.success(`已选择第 ${candidate.question_no || '?'} 题`)
}

async function handleImageChange(uploadFile: { raw?: File; name?: string }) {
  const rawFile = uploadFile.raw
  if (!rawFile) return

  ocrLoading.value = true
  ocrFileName.value = uploadFile.name || rawFile.name
  ocrBlocks.value = []
  ocrEngine.value = ''
  pageCandidates.value = []

  try {
    const pageResponse = await uploadPageOcrImage(rawFile)
    pageCandidates.value = pageResponse.data.questions || []
    ocrEngine.value = pageResponse.data.engine || ''
    ocrBlocks.value = pageCandidates.value.map(c => ({
      text: candidateToText(c),
      confidence: c.confidence === 'high' ? 0.92 : c.confidence === 'low' ? 0.45 : 0.75,
    }))

    if (pageCandidates.value.length > 1) {
      form.question_text = candidateToText(pageCandidates.value[0])
      ElMessage.success(`识别到 ${pageCandidates.value.length} 道题，请选择`)
    } else if (pageCandidates.value.length === 1) {
      form.question_text = candidateToText(pageCandidates.value[0])
      ElMessage.success('图片文字已识别')
    } else {
      const response = await uploadOcrImage(rawFile)
      form.question_text =
        response.data.corrected_text ||
        response.data.vision_text ||
        response.data.pix2text_text ||
        response.data.ocr_text
      ocrBlocks.value = response.data.blocks
      ocrEngine.value = response.data.engine || ''
      ElMessage.success('图片文字已识别')
    }
    questionEditing.value = false
  } catch (err) {
    if (axios.isAxiosError(err)) {
      const detail = typeof err.response?.data === 'string'
        ? err.response?.data
        : (err.response?.data as any)?.detail
      ElMessage.error(detail || `OCR 请求失败：${err.message}`)
    } else {
      ElMessage.error('OCR 识别失败，请稍后重试')
    }
  } finally {
    ocrLoading.value = false
  }
}

function handleSubmit() {
  if (!form.question_text.trim()) {
    ElMessage.warning('请先输入题目或上传图片')
    return
  }
  emit('submit', {
    question_text: form.question_text.trim(),
    student_answer: form.student_answer.trim(),
  })
}
</script>
