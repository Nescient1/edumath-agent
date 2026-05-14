<template>
  <main class="page-shell">
    <section class="profile-layout">
      <div class="surface">
        <div class="section-head">
          <div>
            <p class="eyebrow">学习画像</p>
            <h1>薄弱点追踪</h1>
          </div>
          <el-button type="primary" :icon="DataAnalysis" @click="loadProfile">刷新</el-button>
        </div>

        <div class="filters single">
          <el-input v-model="studentId" placeholder="学生 ID" />
        </div>

        <div v-if="profile" class="profile-stats">
          <div>
            <strong>{{ profile.total_wrong_questions }}</strong>
            <span>错题记录</span>
          </div>
          <div>
            <strong>{{ profile.target_score }}</strong>
            <span>目标分</span>
          </div>
          <div>
            <strong>{{ profile.grade }}</strong>
            <span>年级</span>
          </div>
        </div>

        <p v-if="profile" class="recommendation">{{ profile.recommendation }}</p>

        <el-empty v-if="profile && profile.weak_points.length === 0" description="暂无画像数据" />

        <div v-if="profile?.weak_points.length" class="weak-list">
          <div v-for="point in profile.weak_points" :key="point.name" class="weak-item">
            <span>{{ point.name }}</span>
            <el-progress
              :percentage="Math.min(100, point.count * 20)"
              :format="() => `${point.count} 次`"
            />
          </div>
        </div>
      </div>

      <div class="surface">
        <div class="section-head">
          <div>
            <p class="eyebrow">错题记录</p>
            <h2>最近诊断</h2>
          </div>
        </div>

        <el-timeline v-if="records.length">
          <el-timeline-item
            v-for="record in records"
            :key="record.id"
            :timestamp="record.created_at"
          >
            <p class="record-title">{{ record.error_type }}</p>
            <p class="muted">{{ record.diagnosis }}</p>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无记录" />
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { DataAnalysis } from '@element-plus/icons-vue'

import {
  fetchProfile,
  fetchWrongRecords,
  type StudentProfile,
  type WrongQuestionRecord,
} from '../api/profiles'

const studentId = ref('S001')
const profile = ref<StudentProfile | null>(null)
const records = ref<WrongQuestionRecord[]>([])

async function loadProfile() {
  try {
    const [profileResponse, recordsResponse] = await Promise.all([
      fetchProfile(studentId.value.trim()),
      fetchWrongRecords(studentId.value.trim()),
    ])
    profile.value = profileResponse.data
    records.value = recordsResponse.data
  } catch {
    ElMessage.error('画像服务暂时不可用')
  }
}

onMounted(loadProfile)
</script>
