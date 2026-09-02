<template>
  <div class="train-page">
    <div class="page-header">
      <h2>模型训练</h2>
      <p>选择 YOLO 模型、配置参数、启动训练</p>
    </div>

    <el-row :gutter="20">
      <!-- Left: Configuration -->
      <el-col :span="14">
        <!-- Model Selection -->
        <el-card shadow="never" :header="`选择 ${modelTypeLabel}（基线权重）`">
          <el-alert
            v-if="project.anno_type === 'polygon'"
            type="info"
            :closable="false"
            show-icon
            title="当前工程为多边形标注，已过滤为实例分割模型（YOLOv8-seg / YOLO11-seg 等）"
            style="margin-bottom: 12px;"
          />
          <div
            v-for="group in modelGroups"
            :key="group.family"
            class="model-family"
          >
            <div class="family-title">{{ group.family }}</div>
            <div class="model-grid">
              <div
                v-for="model in group.models"
                :key="model.id"
                class="model-card"
                :class="{ active: selectedModel === model.id }"
                @click="selectedModel = model.id"
              >
                <div class="model-card-top">
                  <div class="model-name">{{ model.name }}</div>
                  <div class="model-tag">
                    <el-tag v-if="model.downloaded" type="success" size="small" effect="plain">已下载</el-tag>
                    <el-tag v-else size="small" effect="plain">{{ model.size_mb }} MB</el-tag>
                  </div>
                </div>
                <div class="model-desc">{{ model.desc }}</div>
                <el-progress
                  v-if="downloadProgress[model.id] !== undefined && downloadProgress[model.id] < 100"
                  :percentage="downloadProgress[model.id]"
                  :stroke-width="4"
                  class="dl-progress"
                />
              </div>
            </div>
          </div>

          <el-divider style="margin: 14px 0;" />

          <div style="display: flex; gap: 12px; align-items: center;">
            <el-button
              type="primary"
              plain
              @click="downloadModel"
              :loading="downloading"
              :disabled="!selectedModel || downloadProgress[selectedModel] === 100"
            >
              <el-icon><Download /></el-icon>
              {{ downloadProgress[selectedModel] !== undefined && downloadProgress[selectedModel] < 100
                ? `下载中 ${downloadProgress[selectedModel]}%`
                : (isModelDownloaded(selectedModel) ? '重新下载' : '下载基线权重') }}
            </el-button>
            <span class="dl-hint" v-if="downloadProgress[selectedModel] !== undefined && downloadProgress[selectedModel] < 100">
              国内镜像源加速下载中...
            </span>
          </div>
        </el-card>

        <!-- Training Parameters -->
        <el-card shadow="never" header="训练参数" style="margin-top: 16px;">
          <el-form :model="trainConfig" label-width="120px" size="large">
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="训练轮次">
                  <el-input-number
                    v-model="trainConfig.epochs"
                    :min="1"
                    :max="1000"
                    :step="10"
                    controls-position="right"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="图片尺寸">
                  <el-select v-model="trainConfig.img_size">
                    <el-option label="320" :value="320" />
                    <el-option label="416" :value="416" />
                    <el-option label="512" :value="512" />
                    <el-option label="640 (推荐)" :value="640" />
                    <el-option label="1280" :value="1280" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="Batch Size">
                  <el-select v-model="trainConfig.batch_size">
                    <el-option label="4" :value="4" />
                    <el-option label="8" :value="8" />
                    <el-option label="16 (推荐)" :value="16" />
                    <el-option label="32" :value="32" />
                    <el-option label="64" :value="64" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
          
          <el-alert
            v-if="!hasEnoughData"
            title="数据不足"
            type="warning"
            description="请先上传图片并完成标注，至少需要 2 张已标注的图片才能开始训练"
            show-icon
            :closable="false"
            style="margin-top: 12px;"
          />

          <el-alert
            v-else-if="!selectedModelDownloaded"
            title="基线模型未下载"
            type="error"
            description="请先在上方模型列表中下载所选模型的基线权重，下载完成后即可开始训练"
            show-icon
            :closable="false"
            style="margin-top: 12px;"
          />

          <el-button
            type="success"
            size="large"
            style="width: 100%; margin-top: 20px;"
            @click="startTraining"
            :disabled="isTraining || !hasEnoughData || !selectedModelDownloaded"
            :loading="isTraining"
          >
            <template #icon>
              <VideoPlay v-if="!isTraining" />
              <Loading v-else />
            </template>
            {{ isTraining ? `训练中... ${trainingProgress}%` : (selectedModelDownloaded ? '开始训练' : '请先下载模型') }}
          </el-button>
          
          <el-progress
            v-if="isTraining"
            :percentage="trainingProgress"
            :stroke-width="8"
            status="success"
            style="margin-top: 12px;"
          />
        </el-card>
      </el-col>

      <!-- Right: Logs & History -->
      <el-col :span="10">
        <!-- Training Log -->
        <el-card shadow="never" header="训练日志">
          <div class="log-area" ref="logAreaRef">
            <pre>{{ trainingLog || '等待开始训练...' }}</pre>
          </div>
        </el-card>

        <!-- Training History -->
        <el-card shadow="never" header="历史记录" style="margin-top: 16px;">
          <el-table
            :data="trainRuns"
            stripe
            size="small"
            empty-text="暂无训练记录"
            max-height="300"
          >
            <el-table-column prop="model_name" label="模型" width="100" />
            <el-table-column prop="epochs" label="轮次" width="60" align="center" />
            <el-table-column label="mAP@50" width="90" align="center">
              <template #default="{ row }">
                <span v-if="row.final_map50" style="color: #67c23a; font-weight: 600;">
                  {{ row.final_map50?.toFixed(3) }}
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag
                  :type="getStatusType(row.status)"
                  size="small"
                >
                  {{ getStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="时间" min-width="100">
              <template #default="{ row }">
                {{ formatDate(row.completed_at || row.created_at) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { projectApi, trainApi, annotationApi } from '@/api'

const route = useRoute()
const projectId = computed(() => parseInt(route.params.id))
const logAreaRef = ref(null)

// Data
const availableModels = ref([])
const trainRuns = ref([])
const project = ref({})
const selectedModel = ref('yolov8s')
const downloading = ref(false)
const downloadProgress = ref({}) // {model_id: 0-100}
const downloadTimer = ref(null)

// 按工程标注类型过滤：rectangle→检测模型, polygon→分割模型
const modelTypeLabel = computed(() =>
  project.value.anno_type === 'polygon' ? '实例分割' : '目标检测'
)

// 按版本族分组（已按工程类型过滤）
const modelGroups = computed(() => {
  const needSeg = project.value.anno_type === 'polygon'
  const families = {}
  for (const m of availableModels.value) {
    const isSeg = m.task === 'segment'
    if (needSeg !== isSeg) continue
    if (!families[m.family]) families[m.family] = { family: m.family, models: [] }
    families[m.family].models.push(m)
  }
  return Object.values(families)
})

const isModelDownloaded = (id) => {
  const m = availableModels.value.find(x => x.id === id)
  return !!m?.downloaded
}

// 所选模型是否已下载（开始训练的前置条件）
const selectedModelDownloaded = computed(() => isModelDownloaded(selectedModel.value))

// Training state
const isTraining = ref(false)
const trainingProgress = ref(0)
const trainingLog = ref('')
const currentRunId = ref(null)
const pollTimer = ref(null)

// Config
const trainConfig = reactive({
  model_name: 'yolov8s',
  epochs: 100,
  img_size: 640,
  batch_size: 16,
})

// Computed
const hasEnoughData = computed(() => {
  // This would check actual data availability
  return true // Simplified for now
})

// Methods
const loadModels = async () => {
  try {
    availableModels.value = await trainApi.listModels()
    // 默认选中第一个可用模型（与工程类型匹配）
    if (modelGroups.value.length && modelGroups.value[0].models.length) {
      const first = modelGroups.value[0].models[0]
      selectedModel.value = first.id
      trainConfig.model_name = first.id
    }
  } catch (e) {}
}

const loadProject = async () => {
  try {
    project.value = await projectApi.get(projectId.value)
  } catch (e) {}
}

const loadTrainRuns = async () => {
  try {
    trainRuns.value = await trainApi.listRuns(projectId.value)
  } catch (e) {}
}

const getSpeedType = (id) => {
  if (id.includes('n')) return ''
  if (id.includes('s')) return ''
  if (id.includes('m')) return 'warning'
  if (id.includes('l') || id.includes('x')) return 'danger'
  return 'info'
}

const getSpeedLabel = (id) => {
  const labels = { n: '最快', s: '快速', m: '中等', l: '较慢', x: '最慢' }
  for (const [k, v] of Object.entries(labels)) {
    if (id.includes(k)) return v
  }
  return '-'
}

const getStatusType = (status) => ({
  pending: 'info',
  running: 'warning',
  completed: 'success',
  failed: 'danger',
}[status] || 'info')

const getStatusLabel = (status) => ({
  pending: '待运行',
  running: '训练中',
  completed: '已完成',
  failed: '失败',
}[status] || status)

const downloadModel = async () => {
  if (!selectedModel.value) return

  downloading.value = true
  try {
    const res = await trainApi.downloadModel(selectedModel.value)
    ElMessage.info(res.message || '开始下载')
    // 轮询下载进度
    stopDownloadPolling()
    downloadTimer.value = setInterval(async () => {
      try {
        const st = await trainApi.downloadStatus(selectedModel.value)
        if (st.progress !== undefined) {
          downloadProgress.value = { ...downloadProgress.value, [selectedModel.value]: st.progress }
        }
        if (st.status === 'done') {
          stopDownloadPolling()
          downloadProgress.value = { ...downloadProgress.value, [selectedModel.value]: 100 }
          ElMessage.success(`模型 ${selectedModel.value} 下载完成（${st.size_mb} MB）`)
          loadModels() // 刷新已下载状态
        } else if (st.status === 'error') {
          stopDownloadPolling()
          ElMessage.error(`下载失败: ${st.error || '未知错误'}`)
          delete downloadProgress.value[selectedModel.value]
        }
      } catch (e) {
        stopDownloadPolling()
      }
    }, 800)
  } catch (e) {
    // Error handled by interceptor
  } finally {
    downloading.value = false
  }
}

const stopDownloadPolling = () => {
  if (downloadTimer.value) {
    clearInterval(downloadTimer.value)
    downloadTimer.value = null
  }
}

const startTraining = async () => {
  isTraining.value = true
  trainingProgress.value = 0
  trainingLog.value = ''
  
  try {
    const config = {
      model_name: selectedModel.value,
      epochs: trainConfig.epochs,
      img_size: trainConfig.img_size,
      batch_size: trainConfig.batch_size,
    }
    
    const res = await trainApi.start(projectId.value, config)
    currentRunId.value = res.id
    
    ElMessage.info(res.message)
    
    // Start polling for progress
    startPolling()
    
  } catch (e) {
    isTraining.value = false
  }
}

const startPolling = () => {
  pollTimer.value = setInterval(async () => {
    if (!currentRunId.value) return
    
    try {
      const run = await trainApi.getRun(currentRunId.value)
      
      // Update log
      if (run.log_output && run.log_output !== trainingLog.value) {
        trainingLog.value = run.log_output
        nextTick(() => {
          if (logAreaRef.value) {
            logAreaRef.value.scrollTop = logAreaRef.value.scrollHeight
          }
        })
      }
      
      // Update progress based on metrics history
      if (run.metrics_history && run.metrics_history.length > 0) {
        const lastEpoch = run.metrics_history[run.metrics_history.length - 1]
        trainingProgress.value = Math.round((lastEpoch.epoch / trainConfig.epochs) * 100)
      }
      
      // Check completion
      if (run.status === 'completed' || run.status === 'failed') {
        stopPolling()
        isTraining.value = false
        
        if (run.status === 'completed') {
          ElMessage.success(`训练完成！mAP@50 = ${run.final_map50?.toFixed(3)}`)
        } else {
          ElMessage.error('训练失败')
        }
        
        loadTrainRuns()
      }
      
    } catch (e) {
      stopPolling()
      isTraining.value = false
    }
  }, 2000)
}

const stopPolling = () => {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

// Watch model selection
watch(selectedModel, (val) => {
  trainConfig.model_name = val
})

onMounted(() => {
  loadProject()
  loadModels()
  loadTrainRuns()
})

onUnmounted(() => {
  stopDownloadPolling()
  stopPolling()
})
</script>

<style lang="scss" scoped>
.train-page {
  .page-header {
    margin-bottom: 20px;
    
    h2 {
      font-size: 22px;
      font-weight: 600;
      color: #1a1d27;
      margin-bottom: 4px;
    }
    
    p {
      color: #666;
      font-size: 14px;
    }
  }
  
  .model-family {
    margin-bottom: 14px;

    .family-title {
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.8px;
      color: #86909c;
      margin-bottom: 8px;
    }
  }

  .model-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 8px;

    .model-card {
      padding: 10px 12px;
      border: 1.5px solid #e5e6eb;
      border-radius: 4px;
      cursor: pointer;
      transition: border-color 0.15s, background 0.15s;
      min-width: 0;

      &:hover {
        border-color: #8fabff;
      }

      &.active {
        border-color: #1f5aff;
        background-color: #f5f8ff;
      }

      .model-card-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 6px;
        margin-bottom: 5px;

        .model-name {
          font-weight: 600;
          font-size: 14px;
          color: #1f2329;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          flex: 1;
          min-width: 0;
        }

        .model-tag {
          flex: 0 0 auto;
        }
      }

      .model-desc {
        font-size: 11px;
        color: #86909c;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .dl-progress {
        margin-top: 8px;
      }
    }
  }

  .dl-hint {
    font-size: 12px;
    color: #86909c;
  }
  
  .log-area {
    background: #1a1d27;
    border-radius: 6px;
    padding: 12px;
    height: 280px;
    overflow-y: auto;
    font-family: 'SF Mono', Monaco, monospace;
    font-size: 12px;
    line-height: 1.7;
    color: #9a9db0;
    
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-all;
    }
  }
}
</style>
