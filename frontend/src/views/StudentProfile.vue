<template>
  <main class="page-shell">
    <section class="profile-layout-v2">
      <!-- Left Column: Profile + Charts + AI Tutor -->
      <div class="profile-left">
        <!-- Profile Card -->
        <section class="surface profile-card">
          <div class="profile-card__header">
            <div class="profile-card__avatar">{{ avatarLetter }}</div>
            <div>
              <h1>{{ profile?.name || studentId }}</h1>
              <p class="muted">{{ profile?.grade || '高三' }} · {{ profile?.current_topic || '函数与导数' }}</p>
            </div>
            <div class="profile-card__actions">
              <el-button :icon="DataAnalysis" @click="loadProfile" circle />
              <el-button
                v-if="profile"
                type="primary"
                :icon="editing ? Check : EditPen"
                :loading="saving"
                @click="editing ? saveProfile() : startEdit()"
                round
              >
                {{ editing ? '保存' : '编辑' }}
              </el-button>
            </div>
          </div>

          <!-- Stats Row -->
          <div v-if="profile" class="profile-stats-v2">
            <div class="stat-item">
              <strong>{{ profile.total_wrong_questions }}</strong>
              <span>累计错题</span>
            </div>
            <div class="stat-item">
              <strong>{{ profile.target_score }}</strong>
              <span>目标分</span>
            </div>
            <div class="stat-item">
              <strong>{{ profile.current_score ?? '--' }}</strong>
              <span>当前分</span>
            </div>
          </div>

          <!-- Edit Form -->
          <el-form v-if="profile && editing" class="profile-edit-grid" label-position="top">
            <el-form-item label="姓名">
              <el-input v-model="profileForm.name" placeholder="可选" />
            </el-form-item>
            <el-form-item label="年级">
              <el-select v-model="profileForm.grade">
                <el-option label="高一" value="高一" />
                <el-option label="高二" value="高二" />
                <el-option label="高三" value="高三" />
              </el-select>
            </el-form-item>
            <el-form-item label="目标分">
              <el-input-number v-model="profileForm.target_score" :min="0" :max="150" />
            </el-form-item>
            <el-form-item label="当前分">
              <el-input-number v-model="profileForm.current_score" :min="0" :max="150" />
            </el-form-item>
            <el-form-item label="教材版本">
              <el-input v-model="profileForm.textbook_version" placeholder="如 人教A版" />
            </el-form-item>
            <el-form-item label="当前专题">
              <el-input v-model="profileForm.current_topic" placeholder="如 函数与导数" />
            </el-form-item>
            <el-form-item class="profile-edit-wide" label="学习目标">
              <el-input v-model="profileForm.learning_goal" type="textarea" :rows="3" resize="none" />
            </el-form-item>
          </el-form>
        </section>

        <!-- Radar Chart -->
        <section v-if="profile && radarData.length >= 3" class="surface profile-radar-card">
          <div class="section-head compact-head">
            <div>
              <p class="eyebrow">掌握度分析</p>
              <h2>考点雷达图</h2>
            </div>
          </div>
          <div ref="radarChartRef" class="radar-chart"></div>
        </section>

        <!-- AI Tutor Chat Bubble -->
        <section v-if="profile" class="surface ai-tutor-card">
          <div class="ai-tutor">
            <div class="ai-tutor__avatar">
              <el-icon :size="24"><MagicStick /></el-icon>
            </div>
            <div class="ai-tutor__bubble">
              <p class="ai-tutor__text">
                <template v-if="profile.advice?.summary">
                  {{ profile.advice.summary }}
                </template>
                <template v-else-if="profile.recommendation">
                  {{ profile.recommendation }}
                </template>
                <template v-else>
                  Hi，{{ profile.name || studentId }}！点击下方按钮，我会根据你的学习数据生成个性化建议。
                </template>
              </p>

              <!-- Priority Points -->
              <div v-if="profile.advice?.priority_points.length" class="ai-tutor__points">
                <KnowledgeTag
                  v-for="point in profile.advice.priority_points"
                  :key="point"
                  :label="point"
                />
              </div>

              <!-- Mistake Advice -->
              <div v-if="profile.advice?.mistake_advice.length" class="ai-tutor__advice-list">
                <div
                  v-for="item in profile.advice.mistake_advice"
                  :key="`${item.title}-${item.action}`"
                  class="ai-tutor__advice-item"
                >
                  <strong>{{ item.title }}</strong>
                  <span>{{ item.action }}</span>
                </div>
              </div>

              <!-- Weekly Plan -->
              <ol v-if="profile.advice?.weekly_plan.length" class="ai-tutor__weekly">
                <li v-for="item in profile.advice.weekly_plan" :key="`${item.day}-${item.task}`">
                  <strong>{{ item.day }}</strong>
                  <span>{{ item.task }}</span>
                </li>
              </ol>

              <div class="ai-tutor__actions">
                <el-button
                  type="primary"
                  round
                  size="small"
                  :loading="adviceLoading"
                  @click="refreshAdvice"
                >
                  {{ profile.advice ? '刷新建议' : '生成建议' }}
                </el-button>
                <RouterLink to="/diagnose">
                  <el-button type="warning" round size="small">
                    <el-icon class="el-icon--left"><Aim /></el-icon>
                    立刻去诊断
                  </el-button>
                </RouterLink>
              </div>
            </div>
          </div>
        </section>
      </div>

      <!-- Right Column: Records + Learning Path -->
      <div class="profile-right">
        <!-- Learning Path -->
        <section v-if="profile" class="surface">
          <div class="section-head compact-head">
            <div>
              <p class="eyebrow">Learning Path</p>
              <h2>学习路径</h2>
            </div>
            <el-button size="small" :loading="learningPathLoading" @click="loadLearningPath" round>
              {{ learningPath ? '重新生成' : '生成路径' }}
            </el-button>
          </div>
          <el-empty v-if="!learningPath && !learningPathLoading" description="点击按钮生成个性化学习路径" />
          <div v-if="learningPath" class="learning-path-content">
            <div class="path-meta">
              <el-tag :type="learningPath.source === 'llm' ? 'success' : 'info'" effect="plain">
                {{ learningPath.source === 'llm' ? 'AI 规划' : '规则生成' }}
              </el-tag>
              <span>预计 {{ learningPath.estimated_days }} 天完成</span>
            </div>
            <div v-if="learningPath.priority_order.length" class="path-priority">
              <strong>优先顺序：</strong>
              <div class="tag-row compact">
                <KnowledgeTag
                  v-for="(point, idx) in learningPath.priority_order"
                  :key="point"
                  :label="`${idx + 1}. ${point}`"
                />
              </div>
            </div>
            <div class="path-timeline">
              <div v-for="[day, tasks] in tasksByDay(learningPath.daily_tasks)" :key="day" class="path-day">
                <div class="path-day__badge">Day {{ day }}</div>
                <div class="path-day__tasks">
                  <div v-for="task in tasks" :key="`${task.knowledge_point}-${task.task_type}`" class="path-task">
                    <el-tag size="small" :type="task.task_type === '测试' ? 'danger' : task.task_type === '复习' ? 'info' : 'warning'" effect="plain">
                      {{ task.task_type }}
                    </el-tag>
                    <span>{{ task.description }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="learningPath.milestones.length" class="path-milestones">
              <strong>里程碑</strong>
              <div v-for="ms in learningPath.milestones" :key="`ms-${ms.day}`" class="milestone-card">
                <div class="milestone-head">
                  <el-tag type="success" effect="plain">Day {{ ms.day }}</el-tag>
                  <span>{{ ms.description }}</span>
                </div>
                <ul v-if="ms.checkpoints.length" class="milestone-checks">
                  <li v-for="cp in ms.checkpoints" :key="cp">{{ cp }}</li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        <!-- Weak Points + Error Types -->
        <section v-if="profile" class="surface">
          <div class="section-head compact-head">
            <div>
              <p class="eyebrow">薄弱环节</p>
              <h2>知识点 & 错因</h2>
            </div>
          </div>
          <el-empty v-if="profile.weak_points.length === 0" description="暂无画像数据" />
          <div v-else class="weak-list">
            <div v-for="point in profile.weak_points" :key="point.name" class="weak-item">
              <div class="weak-item__head">
                <span>{{ point.name }}</span>
                <el-tag size="small" effect="plain">{{ masteryPercent(point.name) }}%</el-tag>
              </div>
              <el-progress
                :percentage="Math.min(100, point.count * 20)"
                :format="() => `${point.count} 次`"
                :stroke-width="8"
              />
            </div>
          </div>

          <div v-if="Object.keys(profile.error_types).length" style="margin-top: 20px">
            <h3 style="font-size: 14px; margin-bottom: 10px">错因分布</h3>
            <div class="error-type-grid">
              <div v-for="[name, count] in errorTypeEntries" :key="name">
                <span>{{ name }}</span>
                <strong>{{ count }}</strong>
              </div>
            </div>
          </div>
        </section>

        <!-- Wrong Records -->
        <section class="surface">
          <div class="section-head">
            <div>
              <p class="eyebrow">错题记录</p>
              <h2>最近诊断</h2>
            </div>
            <el-tag effect="plain">{{ records.length }} 条</el-tag>
          </div>

          <div v-if="records.length" class="record-list">
            <article v-for="record in records" :key="record.id" class="record-card">
              <div class="record-card__head">
                <div>
                  <p class="record-title">{{ record.error_type }}</p>
                  <p class="muted">{{ record.created_at }}</p>
                </div>
                <el-tag :type="record.is_mastered ? 'success' : 'warning'" effect="plain">
                  {{ record.is_mastered ? '已掌握' : record.review_status }}
                </el-tag>
              </div>
              <MathTextPreview class="record-math-preview" :text="record.question_text" title="" />
              <p class="muted">{{ record.diagnosis }}</p>
              <div class="record-card__actions">
                <el-select
                  :model-value="record.review_status"
                  size="small"
                  @change="(value: string | number | boolean) => updateRecord(record, { review_status: String(value) })"
                >
                  <el-option label="未复习" value="未复习" />
                  <el-option label="复习中" value="复习中" />
                  <el-option label="已复习" value="已复习" />
                </el-select>
                <el-switch
                  :model-value="record.is_mastered"
                  active-text="已掌握"
                  inactive-text="未掌握"
                  @change="(value: string | number | boolean) => updateRecord(record, { is_mastered: Boolean(value) })"
                />
              </div>
            </article>
          </div>
          <el-empty v-else description="暂无记录" />
          <div v-if="records.length && hasMoreRecords" class="load-more-row">
            <el-button :loading="recordsLoading" @click="loadMoreRecords" round>加载更多</el-button>
          </div>
        </section>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Aim, Check, DataAnalysis, EditPen, MagicStick } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

import {
  fetchProfile,
  fetchWrongRecords,
  refreshProfileAdvice,
  updateProfile,
  updateWrongRecord,
  type StudentProfile as StudentProfileType,
  type StudentProfileUpdate,
  type WrongQuestionRecord,
} from '../api/profiles'
import { fetchLearningPath, type LearningPath, type LearningPathTask } from '../api/learningPath'
import KnowledgeTag from '../components/KnowledgeTag.vue'
import MathTextPreview from '../components/MathTextPreview.vue'

const studentId = ref(localStorage.getItem('edumath_student_id') || 'S001')
const profile = ref<StudentProfileType | null>(null)
const records = ref<WrongQuestionRecord[]>([])
const editing = ref(false)
const saving = ref(false)
const adviceLoading = ref(false)
const recordsLoading = ref(false)
const learningPath = ref<LearningPath | null>(null)
const learningPathLoading = ref(false)
const recordsLimit = 10
const hasMoreRecords = ref(false)

const profileForm = reactive<Required<Omit<StudentProfileUpdate, 'weak_points' | 'error_types'>>>({
  name: '',
  grade: '高三',
  target_score: 120,
  current_score: null,
  textbook_version: '',
  current_topic: '函数与导数',
  learning_goal: '',
})

const avatarLetter = computed(() => {
  const name = profile.value?.name || studentId.value
  return name.charAt(0).toUpperCase()
})

const errorTypeEntries = computed(() =>
  Object.entries(profile.value?.error_types || {}).sort((a, b) => b[1] - a[1]),
)

// --- Radar Chart ---
const radarChartRef = ref<HTMLElement | null>(null)
let radarChart: echarts.ECharts | null = null

const radarData = computed(() => {
  if (!profile.value) return []
  const weakPoints = profile.value.weak_points || []
  const mastery = profile.value.mastery || {}
  return weakPoints.slice(0, 8).map(wp => {
    const m = mastery[wp.name]
    const score = typeof m === 'number' ? Math.max(0, Math.min(100, m)) : Math.max(0, 100 - wp.count * 15)
    return { name: wp.name, score }
  })
})

function renderRadar() {
  if (!radarChartRef.value || radarData.value.length < 3) return
  if (!radarChart) {
    radarChart = echarts.init(radarChartRef.value)
  }
  radarChart.setOption({
    color: ['#4f6ef7'],
    radar: {
      indicator: radarData.value.map(d => ({ name: d.name, max: 100 })),
      shape: 'polygon',
      splitNumber: 4,
      axisName: { color: '#6b7280', fontSize: 12 },
      splitLine: { lineStyle: { color: '#f0f1f3' } },
      splitArea: { show: true, areaStyle: { color: ['#fff', '#f7f9fc'] } },
      axisLine: { lineStyle: { color: '#e5e7eb' } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: radarData.value.map(d => d.score),
        name: '掌握度',
        areaStyle: { color: 'rgba(79, 110, 247, 0.15)' },
        lineStyle: { color: '#4f6ef7', width: 2 },
        itemStyle: { color: '#4f6ef7' },
      }],
    }],
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const vals = params.value as number[]
        const names = radarData.value.map(d => d.name)
        return vals.map((v, i) => `${names[i]}: ${v}%`).join('<br/>')
      }
    },
  })
}

watch(radarData, () => nextTick(renderRadar), { deep: true })

// --- Data Loading ---
function syncForm() {
  if (!profile.value) return
  profileForm.name = profile.value.name || ''
  profileForm.grade = profile.value.grade || '高三'
  profileForm.target_score = profile.value.target_score || 120
  profileForm.current_score = profile.value.current_score ?? null
  profileForm.textbook_version = profile.value.textbook_version || ''
  profileForm.current_topic = profile.value.current_topic || '函数与导数'
  profileForm.learning_goal = profile.value.learning_goal || ''
}

async function loadProfile() {
  try {
    const id = studentId.value.trim()
    const [profileResponse, recordsResponse] = await Promise.all([
      fetchProfile(id),
      fetchWrongRecords(id, { limit: recordsLimit, offset: 0 }),
    ])
    profile.value = profileResponse.data
    records.value = recordsResponse.data
    hasMoreRecords.value = recordsResponse.data.length === recordsLimit
    syncForm()
    nextTick(renderRadar)
  } catch {
    ElMessage.error('画像服务暂时不可用')
  }
}

async function loadMoreRecords() {
  recordsLoading.value = true
  try {
    const response = await fetchWrongRecords(studentId.value.trim(), {
      limit: recordsLimit,
      offset: records.value.length,
    })
    records.value = [...records.value, ...response.data]
    hasMoreRecords.value = response.data.length === recordsLimit
  } catch {
    ElMessage.error('加载更多错题失败')
  } finally {
    recordsLoading.value = false
  }
}

async function refreshAdvice() {
  if (!profile.value) return
  adviceLoading.value = true
  try {
    const response = await refreshProfileAdvice(studentId.value.trim())
    profile.value = { ...profile.value, advice: response.data, llm_advice: response.data.summary }
    ElMessage.success('学习建议已更新')
  } catch {
    ElMessage.error('生成学习建议失败')
  } finally {
    adviceLoading.value = false
  }
}

async function loadLearningPath() {
  learningPathLoading.value = true
  try {
    const response = await fetchLearningPath(studentId.value.trim())
    learningPath.value = response.data
  } catch {
    ElMessage.error('学习路径生成失败')
  } finally {
    learningPathLoading.value = false
  }
}

function tasksByDay(tasks: LearningPathTask[]): Map<number, LearningPathTask[]> {
  const map = new Map<number, LearningPathTask[]>()
  for (const task of tasks) {
    const list = map.get(task.day) || []
    list.push(task)
    map.set(task.day, list)
  }
  return map
}

function startEdit() {
  syncForm()
  editing.value = true
}

async function saveProfile() {
  saving.value = true
  try {
    const response = await updateProfile(studentId.value.trim(), { ...profileForm })
    profile.value = response.data
    editing.value = false
    ElMessage.success('画像已保存')
  } catch {
    ElMessage.error('保存画像失败')
  } finally {
    saving.value = false
  }
}

async function updateRecord(record: WrongQuestionRecord, updates: { review_status?: string; is_mastered?: boolean }) {
  try {
    const response = await updateWrongRecord(studentId.value.trim(), record.id, updates)
    const index = records.value.findIndex(item => item.id === record.id)
    if (index !== -1) records.value[index] = response.data
    await loadProfile()
  } catch {
    ElMessage.error('更新错题状态失败')
  }
}

function masteryPercent(point: string) {
  const value = profile.value?.mastery?.[point]
  if (typeof value === 'number') return Math.max(0, Math.min(100, value))
  return 0
}

onMounted(loadProfile)
</script>
