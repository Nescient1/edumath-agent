<template>
  <div class="diag-sidebar">
    <!-- Error Type Badge -->
    <div class="diag-sidebar__error-badge">
      <div
        class="error-badge"
        :class="{
          'error-badge--danger': result.difficulty === '困难',
          'error-badge--warning': result.difficulty === '中等',
          'error-badge--info': result.difficulty === '基础',
        }"
      >
        <el-icon :size="18"><WarningFilled /></el-icon>
        <span>{{ result.error_type }}</span>
      </div>
    </div>

    <!-- Knowledge Points -->
    <div class="diag-sidebar__section">
      <h3>核心考点</h3>
      <el-collapse>
        <el-collapse-item title="知识点归纳" name="concepts">
          <ul class="sidebar-concepts">
            <li v-for="kp in result.knowledge_points" :key="kp">{{ kp }}</li>
          </ul>
          <div v-if="result.key_concepts?.length" style="margin-top: 8px">
            <p class="muted" style="font-size: 12px; margin-bottom: 6px">关键概念</p>
            <ul class="sidebar-concepts">
              <li v-for="c in result.key_concepts" :key="c">{{ c }}</li>
            </ul>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>

    <!-- Similar Questions -->
    <div class="diag-sidebar__section">
      <div class="diag-sidebar__section-head">
        <h3>相似题推荐</h3>
        <el-tag effect="plain" size="small">{{ result.similar_questions.length }} 题</el-tag>
      </div>
      <div class="sidebar-similar-list">
        <SimilarQuestionCard
          v-for="q in result.similar_questions"
          :key="q.id"
          :question="q"
          @select="$emit('select-question', q)"
        />
      </div>
    </div>

    <!-- Variant Generation -->
    <div class="diag-sidebar__section">
      <el-button
        type="primary"
        plain
        round
        :loading="variantLoading"
        class="sidebar-variant-btn"
        @click="$emit('generate-variants')"
      >
        <el-icon class="el-icon--left"><MagicStick /></el-icon>
        生成变式题
      </el-button>
    </div>

    <!-- Variant Questions -->
    <div v-if="variantQuestions.length" class="diag-sidebar__section">
      <div class="diag-sidebar__section-head">
        <h3>AI 变式题</h3>
        <el-tag type="success" effect="plain" size="small">{{ variantQuestions.length }} 题</el-tag>
      </div>
      <div class="sidebar-variant-list">
        <article
          v-for="(vq, idx) in variantQuestions"
          :key="idx"
          class="sidebar-variant-card"
          @click="$emit('select-question', adaptVariant(vq))"
        >
          <div class="sidebar-variant-card__head">
            <el-tag
              size="small"
              :type="vq.difficulty === '基础' ? 'success' : vq.difficulty === '困难' ? 'danger' : 'warning'"
              effect="plain"
            >
              {{ vq.difficulty }}
            </el-tag>
            <el-tag size="small" effect="plain">{{ vq.question_type }}</el-tag>
            <el-tag v-if="vq.source === 'generated'" size="small" type="info" effect="plain">AI</el-tag>
          </div>
          <MathTextPreview class="sidebar-variant-preview" :text="vq.question_text" title="" />
          <div class="tag-row compact" style="margin: 0">
            <KnowledgeTag
              v-for="kp in vq.knowledge_points.slice(0, 3)"
              :key="kp"
              :label="kp"
            />
          </div>
        </article>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { MagicStick, WarningFilled } from '@element-plus/icons-vue'

import type { DiagnoseResponse, SimilarQuestion } from '../../api/diagnose'
import type { GeneratedQuestion } from '../../api/recommend'
import KnowledgeTag from '../KnowledgeTag.vue'
import MathTextPreview from '../MathTextPreview.vue'
import SimilarQuestionCard from '../SimilarQuestionCard.vue'

defineProps<{
  result: DiagnoseResponse
  variantQuestions: GeneratedQuestion[]
  variantLoading: boolean
}>()

defineEmits<{
  'select-question': [question: SimilarQuestion]
  'generate-variants': []
}>()

function adaptVariant(vq: GeneratedQuestion): SimilarQuestion {
  return {
    id: 'variant',
    question_text: vq.question_text,
    knowledge_points: vq.knowledge_points,
    difficulty: vq.difficulty,
    question_type: vq.question_type,
  }
}
</script>
