<template>
  <main class="page-shell">
    <section class="qb-container">
      <!-- Header -->
      <div class="qb-header">
        <div>
          <p class="eyebrow">函数与导数</p>
          <h1>专题题库</h1>
        </div>
        <el-button type="primary" :icon="Search" @click="loadQuestions" round>筛选</el-button>
      </div>

      <!-- Filters -->
      <div class="qb-filters">
        <el-input v-model="filters.keyword" placeholder="关键词搜索" clearable :prefix-icon="Search" />
        <el-input v-model="filters.knowledge_point" placeholder="知识点" clearable />
        <el-select v-model="filters.difficulty" placeholder="难度" clearable>
          <el-option label="基础" value="基础" />
          <el-option label="中等" value="中等" />
          <el-option label="困难" value="困难" />
        </el-select>
        <el-select v-model="filters.quality_label" placeholder="质量" clearable>
          <el-option label="高质量" value="high" />
          <el-option label="中等质量" value="medium" />
        </el-select>
        <el-checkbox v-model="filters.only_complete">只看完整题</el-checkbox>
      </div>

      <!-- Card Grid -->
      <div v-loading="loading" class="qb-grid">
        <article
          v-for="q in questions"
          :key="q.id"
          class="qb-card"
          @click="openDetail(q)"
        >
          <div class="qb-card__header">
            <el-tag
              size="small"
              :type="q.difficulty === '基础' ? 'success' : q.difficulty === '困难' ? 'danger' : 'warning'"
              effect="plain"
              round
            >
              {{ q.difficulty }}
            </el-tag>
            <span class="qb-card__type">{{ q.question_type }}</span>
          </div>

          <div class="qb-card__body">
            <MathTextPreview
              class="qb-card__math"
              :text="q.question_text"
              title=""
            />
          </div>

          <div class="qb-card__footer">
            <div class="qb-card__tags">
              <KnowledgeTag
                v-for="kp in q.knowledge_points.slice(0, 3)"
                :key="kp"
                :label="kp"
              />
              <span v-if="q.knowledge_points.length > 3" class="qb-card__more-tag">
                +{{ q.knowledge_points.length - 3 }}
              </span>
            </div>
            <span class="qb-card__action">查看 →</span>
          </div>
        </article>
      </div>

      <!-- Empty State -->
      <el-empty v-if="!loading && questions.length === 0" description="暂无题目，试试调整筛选条件" />

      <!-- Load More -->
      <div v-if="questions.length && hasMore" class="qb-load-more">
        <el-button :loading="loadingMore" @click="loadMoreQuestions" round>
          加载更多题目
        </el-button>
      </div>
    </section>

    <!-- Detail Dialog -->
    <el-dialog
      v-model="detailVisible"
      :title="null"
      width="680px"
      class="qb-detail-dialog"
      destroy-on-close
    >
      <div v-if="detailQuestion" class="qb-detail">
        <div class="qb-detail__header">
          <el-tag
            :type="detailQuestion.difficulty === '基础' ? 'success' : detailQuestion.difficulty === '困难' ? 'danger' : 'warning'"
            effect="plain"
          >
            {{ detailQuestion.difficulty }}
          </el-tag>
          <el-tag effect="plain">{{ detailQuestion.question_type }}</el-tag>
          <div class="qb-detail__tags">
            <KnowledgeTag
              v-for="kp in detailQuestion.knowledge_points"
              :key="kp"
              :label="kp"
            />
          </div>
        </div>

        <div class="qb-detail__section">
          <h3>题目</h3>
          <MathTextPreview class="qb-detail__math" :text="detailQuestion.question_text" title="" />
        </div>

        <div v-if="detailOptions.length" class="qb-detail__section">
          <h3>选项</h3>
          <div class="qb-detail__options">
            <div
              v-for="opt in detailOptions"
              :key="opt"
              class="qb-detail__option"
            >
              <MathTextPreview class="qb-detail__opt-text" :text="opt" title="" />
            </div>
          </div>
        </div>

        <div v-if="detailLoading" class="qb-detail__loading">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>加载详情中...</span>
        </div>

        <template v-if="detailData">
          <div v-if="detailData.answer" class="qb-detail__section">
            <h3>参考答案</h3>
            <MathTextPreview class="qb-detail__math" :text="detailData.answer" title="" />
          </div>

          <div v-if="detailData.solution" class="qb-detail__section">
            <h3>解析</h3>
            <MathTextPreview class="qb-detail__math" :text="detailData.solution" title="" />
          </div>

          <div v-if="detailData.common_mistakes?.length" class="qb-detail__section">
            <div class="pitfalls-block">
              <h3 style="margin-bottom: 8px">常见错误</h3>
              <ul class="pitfalls-list">
                <li v-for="m in detailData.common_mistakes" :key="m">{{ m }}</li>
              </ul>
            </div>
          </div>
        </template>
      </div>
    </el-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading, Search } from '@element-plus/icons-vue'

import { fetchQuestions, fetchQuestionDetail, type Question } from '../api/questions'
import type { SimilarQuestion } from '../api/diagnose'
import KnowledgeTag from '../components/KnowledgeTag.vue'
import MathTextPreview from '../components/MathTextPreview.vue'

const filters = reactive({
  keyword: '',
  knowledge_point: '',
  difficulty: '',
  quality_label: '',
  only_complete: true,
})
const questions = ref<SimilarQuestion[]>([])
const loading = ref(false)
const loadingMore = ref(false)
const pageSize = 50
const hasMore = ref(false)

const detailVisible = ref(false)
const detailQuestion = ref<SimilarQuestion | null>(null)
const detailData = ref<Question | null>(null)
const detailLoading = ref(false)

const detailOptions = computed(() => {
  return detailData.value?.options || detailQuestion.value?.options || []
})

async function loadQuestions() {
  loading.value = true
  try {
    const response = await fetchQuestions({
      keyword: filters.keyword || undefined,
      knowledge_point: filters.knowledge_point || undefined,
      difficulty: filters.difficulty || undefined,
      quality_label: filters.quality_label || undefined,
      has_answer: filters.only_complete ? true : undefined,
      has_solution: filters.only_complete ? true : undefined,
      limit: pageSize,
      offset: 0,
    })
    questions.value = response.data
    hasMore.value = response.data.length === pageSize
  } catch {
    ElMessage.error('题库服务暂时不可用')
  } finally {
    loading.value = false
  }
}

async function loadMoreQuestions() {
  loadingMore.value = true
  try {
    const response = await fetchQuestions({
      keyword: filters.keyword || undefined,
      knowledge_point: filters.knowledge_point || undefined,
      difficulty: filters.difficulty || undefined,
      quality_label: filters.quality_label || undefined,
      has_answer: filters.only_complete ? true : undefined,
      has_solution: filters.only_complete ? true : undefined,
      limit: pageSize,
      offset: questions.value.length,
    })
    questions.value = [...questions.value, ...response.data]
    hasMore.value = response.data.length === pageSize
  } catch {
    ElMessage.error('加载更多题目失败')
  } finally {
    loadingMore.value = false
  }
}

async function openDetail(q: SimilarQuestion) {
  detailQuestion.value = q
  detailData.value = null
  detailVisible.value = true
  detailLoading.value = true
  try {
    const res = await fetchQuestionDetail(q.id)
    detailData.value = res.data
  } catch {
    // show question text only
  } finally {
    detailLoading.value = false
  }
}

loadQuestions()
</script>
