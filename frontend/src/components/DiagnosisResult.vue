<template>
  <section class="surface result-section">
    <div class="section-head">
      <div>
        <p class="eyebrow">诊断结果</p>
        <h2>{{ result.error_type }}</h2>
      </div>
      <el-tag type="warning" effect="plain">{{ result.difficulty }}</el-tag>
    </div>

    <div class="tag-row">
      <KnowledgeTag
        v-for="point in result.knowledge_points"
        :key="point"
        :label="point"
      />
    </div>

    <div class="answer-mode">
      <el-tag :type="answerModeTagType" effect="plain">{{ answerModeLabel }}</el-tag>
      <span>检索质量：{{ result.retrieval_quality }}</span>
    </div>

    <div class="result-block">
      <h3>错因分析</h3>
      <p>{{ result.diagnosis }}</p>
    </div>

    <div class="result-block">
      <h3>个性化讲解</h3>
      <p>{{ result.explanation }}</p>
    </div>

    <div class="result-block">
      <h3>关键知识点</h3>
      <ul class="clean-list">
        <li v-for="concept in result.key_concepts" :key="concept">{{ concept }}</li>
      </ul>
    </div>

    <div v-if="result.source_summary?.length" class="result-block">
      <h3>参考资料来源</h3>
      <div class="source-list">
        <div v-for="source in result.source_summary" :key="`${source.source}-${source.title}`" class="source-item">
          <div>
            <strong>{{ source.title }}</strong>
            <p>{{ source.source }} · {{ source.content_type }}</p>
          </div>
          <el-tag size="small" effect="plain">{{ source.score.toFixed(3) }}</el-tag>
        </div>
      </div>
    </div>

    <el-collapse v-if="result.retrieved_context.length" class="context-collapse">
      <el-collapse-item title="检索到的讲义片段" name="context">
        <pre
          v-for="context in result.retrieved_context"
          :key="context"
          class="context-text"
        >{{ context }}</pre>
      </el-collapse-item>
    </el-collapse>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DiagnoseResponse } from '../api/diagnose'
import KnowledgeTag from './KnowledgeTag.vue'

const props = defineProps<{ result: DiagnoseResponse }>()

const answerModeText: Record<string, string> = {
  rag_strong: '已参考知识库资料',
  hybrid: '结合知识库与通用解题方法',
  llm_fallback: '知识库命中较低，使用通用数学方法',
  no_source: '当前知识库未找到对应资料',
}

const answerModeLabel = computed(
  () => answerModeText[props.result.answer_mode] || props.result.answer_mode,
)

const answerModeTagType = computed(() => {
  if (props.result.answer_mode === 'rag_strong') return 'success'
  if (props.result.answer_mode === 'hybrid') return 'warning'
  if (props.result.answer_mode === 'llm_fallback') return 'info'
  return 'danger'
})
</script>
