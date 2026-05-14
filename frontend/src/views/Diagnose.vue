<template>
  <main class="page-shell">
    <section class="workspace-grid">
      <section class="surface diagnose-form">
        <div class="section-head">
          <div>
            <p class="eyebrow">EduMath Agent</p>
            <h1>函数与导数错题诊断</h1>
          </div>
          <el-button
            :icon="RefreshRight"
            circle
            title="填入示例"
            @click="fillExample"
          />
        </div>

        <el-form label-position="top" @submit.prevent="submitDiagnosis">
          <el-form-item label="学生 ID">
            <el-input v-model="form.student_id" />
          </el-form-item>
          <el-form-item label="上传错题图片">
            <el-upload
              class="ocr-upload"
              drag
              :show-file-list="false"
              :auto-upload="false"
              accept=".png,.jpg,.jpeg,.bmp,.webp,image/png,image/jpeg,image/bmp,image/webp"
              :on-change="handleImageChange"
            >
              <el-icon class="upload-icon"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                拖拽图片到这里，或点击选择图片
              </div>
            </el-upload>
            <div v-if="ocrFileName || ocrBlocks.length" class="ocr-status">
              <div class="ocr-status__head">
                <span>{{ ocrFileName || '识别结果' }}</span>
                <el-tag v-if="ocrBlocks.length" effect="plain">
                  {{ ocrBlocks.length }} 行
                </el-tag>
              </div>
              <el-alert
                v-if="ocrLoading"
                title="正在识别图片文字"
                type="info"
                :closable="false"
                show-icon
              />
              <div v-else-if="ocrBlocks.length" class="ocr-block-list">
                <div v-for="block in ocrBlocks" :key="`${block.text}-${block.confidence}`" class="ocr-block-row">
                  <span>{{ block.text }}</span>
                  <el-tag size="small" effect="plain">
                    {{ Math.round(block.confidence * 100) }}%
                  </el-tag>
                </div>
              </div>
            </div>
          </el-form-item>
          <el-form-item label="错题题目">
            <el-input
              v-model="form.question_text"
              type="textarea"
              :rows="6"
              resize="none"
            />
          </el-form-item>
          <el-form-item label="错误答案或卡住的位置">
            <el-input
              v-model="form.student_answer"
              type="textarea"
              :rows="4"
              resize="none"
            />
          </el-form-item>
          <div class="actions">
            <el-button
              type="primary"
              native-type="submit"
              :loading="loading"
              :icon="Search"
            >
              开始诊断
            </el-button>
          </div>
        </el-form>
      </section>

      <DiagnosisResult v-if="result" :result="result" />

      <section v-if="result" class="surface similar-section">
        <div class="section-head">
          <div>
            <p class="eyebrow">推荐练习</p>
            <h2>相似题</h2>
          </div>
          <el-tag effect="plain">{{ result.similar_questions.length }} 题</el-tag>
        </div>
        <div class="similar-grid">
          <SimilarQuestionCard
            v-for="question in result.similar_questions"
            :key="question.id"
            :question="question"
            @select="selectPractice(question)"
          />
        </div>
      </section>

      <section v-if="practiceQuestion" class="surface practice-section">
        <div class="section-head">
          <div>
            <p class="eyebrow">学生作答</p>
            <h2>{{ practiceQuestion.id }}</h2>
          </div>
          <el-tag effect="plain">{{ practiceQuestion.difficulty }}</el-tag>
        </div>
        <p class="question-text">{{ practiceQuestion.question_text }}</p>
        <el-input
          v-model="practiceAnswer"
          type="textarea"
          :rows="5"
          resize="none"
        />
        <div class="actions">
          <el-button
            type="success"
            :icon="Check"
            :loading="grading"
            @click="submitPractice"
          >
            提交批改
          </el-button>
        </div>
        <div v-if="gradeResult" class="grade-result">
          <el-progress
            :percentage="gradeResult.score"
            :status="gradeResult.is_correct ? 'success' : 'warning'"
          />
          <p>{{ gradeResult.feedback }}</p>
          <p class="muted">参考答案：{{ gradeResult.reference_answer }}</p>
        </div>
      </section>
    </section>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Check, RefreshRight, Search, UploadFilled } from '@element-plus/icons-vue'
import axios from 'axios'

import {
  diagnoseWrongQuestion,
  gradePracticeAnswer,
  type DiagnoseResponse,
  type PracticeGradeResponse,
  type SimilarQuestion,
} from '../api/diagnose'
import { uploadOcrImage, type OcrBlock } from '../api/ocr'
import DiagnosisResult from '../components/DiagnosisResult.vue'
import SimilarQuestionCard from '../components/SimilarQuestionCard.vue'

const form = reactive({
  student_id: 'S001',
  question_text: '已知函数 f(x)=x^3-3x，求函数的单调区间和极值。',
  student_answer: '我只求了导数 f’(x)=3x^2-3，不知道后面怎么做。',
})

const loading = ref(false)
const grading = ref(false)
const ocrLoading = ref(false)
const ocrFileName = ref('')
const ocrBlocks = ref<OcrBlock[]>([])
const result = ref<DiagnoseResponse | null>(null)
const practiceQuestion = ref<SimilarQuestion | null>(null)
const practiceAnswer = ref('')
const gradeResult = ref<PracticeGradeResponse | null>(null)

function fillExample() {
  form.question_text = '已知函数 f(x)=ln x-x，求 f(x) 的单调区间和极值。'
  form.student_answer = '我忘了先写定义域，后面极值也不知道怎么判断。'
}

async function handleImageChange(uploadFile: { raw?: File; name?: string }) {
  const rawFile = uploadFile.raw
  if (!rawFile) {
    ElMessage.warning('没有读取到图片文件')
    return
  }

  ocrLoading.value = true
  ocrFileName.value = uploadFile.name || rawFile.name
  ocrBlocks.value = []

  try {
    const response = await uploadOcrImage(rawFile)
    form.question_text = response.data.ocr_text
    ocrBlocks.value = response.data.blocks
    ElMessage.success('图片文字已识别，可继续手动修改')
  } catch (err) {
    if (axios.isAxiosError(err)) {
      const detail =
        typeof err.response?.data === 'string'
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

async function submitDiagnosis() {
  if (!form.student_id.trim() || !form.question_text.trim()) {
    ElMessage.warning('学生 ID 和题目不能为空')
    return
  }

  loading.value = true
  practiceQuestion.value = null
  gradeResult.value = null
  try {
    const response = await diagnoseWrongQuestion({
      student_id: form.student_id.trim(),
      question_text: form.question_text.trim(),
      student_answer: form.student_answer.trim(),
    })
    result.value = response.data
  } catch (err) {
    if (axios.isAxiosError(err)) {
      const status = err.response?.status
      const detail =
        typeof err.response?.data === 'string'
          ? err.response?.data
          : (err.response?.data as any)?.detail
      ElMessage.error(
        status
          ? `诊断请求失败（HTTP ${status}）${detail ? `：${detail}` : ''}`
          : `无法连接诊断服务：${err.message}`,
      )
      return
    }

    ElMessage.error('诊断服务暂时不可用')
  } finally {
    loading.value = false
  }
}

function selectPractice(question: SimilarQuestion) {
  practiceQuestion.value = question
  practiceAnswer.value = ''
  gradeResult.value = null
}

async function submitPractice() {
  if (!practiceQuestion.value || !practiceAnswer.value.trim()) {
    ElMessage.warning('请先填写答案')
    return
  }

  grading.value = true
  try {
    const response = await gradePracticeAnswer({
      student_id: form.student_id.trim(),
      question_id: practiceQuestion.value.id,
      student_answer: practiceAnswer.value.trim(),
    })
    gradeResult.value = response.data
  } catch (err) {
    if (axios.isAxiosError(err)) {
      const status = err.response?.status
      ElMessage.error(
        status ? `批改请求失败（HTTP ${status}）` : `无法连接批改服务：${err.message}`,
      )
      return
    }
    ElMessage.error('批改服务暂时不可用')
  } finally {
    grading.value = false
  }
}
</script>
