<template>
  <button class="question-card" type="button" @click="$emit('select')">
    <span class="question-card__meta">
      <el-tag size="small" type="success" effect="plain">{{ question.difficulty }}</el-tag>
      <span>{{ question.question_type }}</span>
    </span>
    <MathTextPreview
      class="question-card-preview"
      :text="question.question_text"
      title="题目"
    />
    <span class="question-card__tags">
      <KnowledgeTag
        v-for="point in question.knowledge_points.slice(0, 3)"
        :key="point"
        :label="point"
      />
    </span>
  </button>
</template>

<script setup lang="ts">
import type { SimilarQuestion } from '../api/diagnose'
import KnowledgeTag from './KnowledgeTag.vue'
import MathTextPreview from './MathTextPreview.vue'

defineProps<{ question: SimilarQuestion }>()
defineEmits<{ select: [] }>()
</script>
