<template>
  <main class="page-shell">
    <section class="surface">
      <div class="section-head">
        <div>
          <p class="eyebrow">函数与导数</p>
          <h1>题库</h1>
        </div>
        <el-button type="primary" :icon="Search" @click="loadQuestions">筛选</el-button>
      </div>

      <div class="filters">
        <el-input v-model="filters.keyword" placeholder="关键词" clearable />
        <el-input v-model="filters.knowledge_point" placeholder="知识点" clearable />
        <el-select v-model="filters.difficulty" placeholder="难度" clearable>
          <el-option label="基础" value="基础" />
          <el-option label="中等" value="中等" />
          <el-option label="困难" value="困难" />
        </el-select>
      </div>

      <el-table :data="questions" v-loading="loading" class="question-table">
        <el-table-column prop="id" label="编号" width="90" />
        <el-table-column prop="question_text" label="题目" min-width="320" />
        <el-table-column prop="difficulty" label="难度" width="100" />
        <el-table-column label="知识点" min-width="240">
          <template #default="{ row }">
            <div class="tag-row compact">
              <KnowledgeTag
                v-for="point in row.knowledge_points"
                :key="point"
                :label="point"
              />
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'

import { fetchQuestions } from '../api/questions'
import type { SimilarQuestion } from '../api/diagnose'
import KnowledgeTag from '../components/KnowledgeTag.vue'

const filters = reactive({
  keyword: '',
  knowledge_point: '',
  difficulty: '',
})
const questions = ref<SimilarQuestion[]>([])
const loading = ref(false)

async function loadQuestions() {
  loading.value = true
  try {
    const response = await fetchQuestions({
      keyword: filters.keyword || undefined,
      knowledge_point: filters.knowledge_point || undefined,
      difficulty: filters.difficulty || undefined,
    })
    questions.value = response.data
  } catch {
    ElMessage.error('题库服务暂时不可用')
  } finally {
    loading.value = false
  }
}

onMounted(loadQuestions)
</script>
