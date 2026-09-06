<template>
  <div class="train-page">
    <div class="page-header">
      <div class="ph-left">
        <h2>模型训练</h2>
        <p>选择 YOLO 模型、配置参数、启动训练</p>
      </div>
      <div class="ph-right">
        <div class="notify-toggle">
          <span class="nt-label">训练完成提醒</span>
          <el-switch v-model="notifyEnabled" size="small" />
          <el-tooltip
            content="训练结束或失败时：浏览器标签标题闪烁（后台时）+ 提示音 + 右上角通知；离开本页也生效"
            placement="bottom-end"
          >
            <span class="nt-hint">声音 / 标题闪烁</span>
          </el-tooltip>
        </div>
      </div>
    </div>

    <el-row :gutter="20">
      <!-- Left: Configuration -->
      <el-col :span="14">
        <!-- Model Selection -->
        <el-card shadow="never" header="选择模型">
          <el-alert
            v-if="project.anno_type === 'polygon'"
            type="info"
            :closable="false"
            show-icon
            title="当前工程为多边形标注，已过滤为实例分割模型（YOLOv8-seg / YOLO11-seg 等）"
            style="margin-bottom: 12px;"
          />

          <!-- 起始权重来源：官方基线 / 迁移学习 -->
          <div class="pretrain-row">
            <div class="family-title" style="margin-bottom: 0;">
              起始权重
            </div>
            <el-radio-group v-model="pretrainSource" size="small" :disabled="isTraining">
              <el-radio-button value="base">官方预训练基线</el-radio-button>
              <el-radio-button value="run" :disabled="!transferRuns.length">
                迁移学习<span v-if="transferRuns.length" class="radio-count">{{ transferRuns.length }}</span>
              </el-radio-button>
            </el-radio-group>
            <el-tooltip
              placement="top-start"
              :show-after="150"
            >
              <template #content>
                <div class="tt-line"><b>官方预训练基线</b>：COCO 80 类权重，需先下载（约 6~130MB）</div>
                <div class="tt-line"><b>迁移学习</b>：复用任意工程已训练 best.pt 作为起始权重继续微调，
                  不再需要下载基线；任务类型自动按工程标注类型校验</div>
              </template>
              <el-icon class="pretrain-help"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>

          <!-- 模式 A：官方基线模型选择 -->
          <template v-if="pretrainSource === 'base'">
            <div class="model-family" v-for="group in modelGroups" :key="group.family">
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
                    <el-tooltip :content="model.name" placement="top">
                      <div class="model-name">{{ model.name }}</div>
                    </el-tooltip>
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
          </template>

          <!-- 模式 B：迁移学习来源 run -->
          <template v-else>
            <div class="family-title">可用训练成果（best.pt 均存在）</div>
            <div class="run-list">
              <div
                v-for="r in transferRuns"
                :key="r.id"
                class="run-item"
                :class="{ active: selectedTransferRun === r.id }"
                @click="selectTransferRun(r)"
              >
                <div class="run-item-top">
                  <span class="run-name">{{ r.model_name }}</span>
                  <span class="run-proj">
                    <el-tag
                      v-if="r.project_id === projectId"
                      size="small" type="info" effect="plain"
                    >本工程</el-tag>
                    <template v-else>工程「{{ r.project_name }}」</template>
                  </span>
                </div>
                <div class="run-item-sub">
                  <span class="mono">run {{ r.id }}</span>
                  <span v-if="r.final_map50" class="mono">mAP@50 {{ r.final_map50.toFixed(3) }}</span>
                  <span>{{ r.epochs }} 轮</span>
                  <span>{{ r.model_name }}</span>
                  <span class="mono">{{ r.weights_size_mb }} MB</span>
                </div>
              </div>
            </div>
            <div v-if="!transferRuns.length" class="run-empty">
              暂无可迁移的训练成果：需要至少一个「已完成」且保留 best.pt 权重文件的 run
            </div>
            <div class="transfer-note">
              迁移后将以所选权重为起点在<b>当前工程数据集</b>上继续训练；
              起始权重与当前工程类别数量不同时，输出层会自动重建
            </div>
          </template>
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
            v-else-if="pretrainSource === 'base' && !selectedModelDownloaded"
            title="基线模型未下载"
            type="error"
            description="请先在上方模型列表中下载所选模型的基线权重，下载完成后即可开始训练"
            show-icon
            :closable="false"
            style="margin-top: 12px;"
          />

          <el-alert
            v-else-if="pretrainSource === 'run' && !selectedTransferRun"
            title="未选择迁移来源"
            type="error"
            description="请在上方列表中选择一个训练成果作为起始权重"
            show-icon
            :closable="false"
            style="margin-top: 12px;"
          />

          <el-button
            type="success"
            size="large"
            style="width: 100%; margin-top: 20px;"
            @click="startTraining"
            :disabled="isTraining || !hasEnoughData || !canStart"
            :loading="isTraining"
          >
            <template #icon>
              <VideoPlay v-if="!isTraining" />
              <Loading v-else />
            </template>
            {{ isTraining ? `训练中... ${trainingProgress}%` : (canStart ? (pretrainSource === 'run' ? '开始迁移训练' : '开始训练') : '请选择有效配置') }}
          </el-button>

          <div v-if="!isTraining && canStart && pretrainSource === 'run'" class="start-note">
            <el-icon><Connection /></el-icon>
            起始权重：{{ selectedTransferRunDesc }}
          </div>
          
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

// 迁移学习（起始权重来源）
const pretrainSource = ref('base') // 'base' | 'run'
const transferRuns = ref([])       // 可用训练成果（任务类型已与工程匹配 + 权重文件存在）
const selectedTransferRun = ref(null)
const selectedTransferRunDesc = ref('')

// 训练完成提醒（全局生效：标题闪烁 + 提示音，见 Layout）
const notifyEnabled = ref(localStorage.getItem('yolo_notify_enabled') !== '0')
watch(notifyEnabled, (v) => localStorage.setItem('yolo_notify_enabled', v ? '1' : '0'))

// 按工程标注类型过滤：rectangle→检测模型, polygon→分割模型
// （说明文字已内联在模型卡片的 alert 中）

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

// 当前模式是否满足启动条件
const canStart = computed(() => {
  if (pretrainSource.value === 'run') return !!selectedTransferRun.value
  return selectedModelDownloaded.value
})

// Methods
const loadTransferSources = async () => {
  try {
    const res = await trainApi.transferSources(projectId.value)
    transferRuns.value = res.runs || []
    // 默认选中第一个可用 run（若有）；清空来源时同步 model_name 给架构展示
    const first = transferRuns.value[0]
    if (first && pretrainSource.value === 'run') {
      selectTransferRun(first)
    } else if (pretrainSource.value === 'run') {
      selectedTransferRun.value = null
      trainConfig.model_name = selectedModel.value
    }
  } catch (e) {}
}

const selectTransferRun = (r) => {
  selectedTransferRun.value = r.id
  selectedTransferRunDesc.value = `工程「${r.project_name}」run ${r.id} · ${r.model_name} · mAP@50 ${r.final_map50?.toFixed(3) ?? '-'}`
  // 架构模型名随来源权重走（无需下载基线）
  trainConfig.model_name = r.model_name
}

// 切换来源模式时重置选择态
watch(pretrainSource, (v) => {
  if (v === 'run') {
    const first = transferRuns.value[0]
    if (first) selectTransferRun(first)
    else {
      selectedTransferRun.value = null
      trainConfig.model_name = selectedModel.value
    }
  } else {
    trainConfig.model_name = selectedModel.value
  }
})
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
  if (isTraining.value) return
  if (pretrainSource.value === 'run' && !selectedTransferRun.value) {
    ElMessage.warning('请先选择迁移学习的来源训练成果')
    return
  }
  isTraining.value = true
  trainingProgress.value = 0
  trainingLog.value = ''
  
  try {
    const config = {
      model_name: trainConfig.model_name,
      epochs: trainConfig.epochs,
      img_size: trainConfig.img_size,
      batch_size: trainConfig.batch_size,
      pretrain_source: pretrainSource.value,
      pretrain_run_id: pretrainSource.value === 'run' ? selectedTransferRun.value : null,
    }
    
    const res = await trainApi.start(projectId.value, config)
    currentRunId.value = res.id
    
    ElMessage.info(res.message || '训练已启动')
    
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
      
      // Check completion（完成/失败提示由全局训练提醒统一弹出：标题闪烁 + 声音 + 通知）
      if (run.status === 'completed' || run.status === 'failed') {
        stopPolling()
        isTraining.value = false
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
  loadTransferSources()
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
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;

    h2 {
      font-size: 22px;
      font-weight: 600;
      color: var(--text-1);
      margin-bottom: 4px;
    }
    
    p {
      color: var(--text-3);
      font-size: 14px;
    }

    .ph-right {
      flex: 0 0 auto;
      padding-top: 6px;

      .notify-toggle {
        display: flex;
        align-items: center;
        gap: 8px;
        background: var(--bg-fill);
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 6px 10px;

        .nt-label {
          font-size: 12px;
          font-weight: 600;
          color: var(--text-2);
        }

        .nt-hint {
          font-size: 11px;
          color: var(--text-3);
          cursor: default;
        }
      }
    }
  }

  // 起始权重来源行
  .pretrain-row {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 14px;
    padding-bottom: 12px;
    border-bottom: 1px dashed var(--border-light);

    .pretrain-help {
      color: var(--text-faint);
      cursor: help;
      font-size: 15px;

      &:hover { color: var(--text-2); }
    }
  }

  .radio-count {
    margin-left: 4px;
    font-size: 11px;
    color: var(--text-3);
  }

  .tt-line {
    font-size: 12px;
    line-height: 1.7;
    max-width: 300px;
    color: #c6cbd4;

    b { color: #fff; }
  }

  // 迁移学习 run 列表
  .run-list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 8px;
    margin-bottom: 10px;

    .run-item {
      padding: 9px 12px;
      background: var(--bg-fill);
      border: 1px solid var(--border);
      border-radius: 5px;
      cursor: pointer;
      transition: border-color 0.15s, background 0.15s;

      &:hover {
        border-color: var(--text-faint);
        background: var(--bg-hover);
      }

      &.active {
        border-color: var(--brand);
        background: var(--brand-soft);
        box-shadow: inset 0 0 0 1px var(--brand);
      }

      .run-item-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        margin-bottom: 6px;

        .run-name {
          font-weight: 600;
          font-size: 13.5px;
          color: var(--text-1);
        }

        .run-proj {
          font-size: 11.5px;
          color: var(--text-3);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
      }

      .run-item-sub {
        display: flex;
        flex-wrap: wrap;
        gap: 4px 10px;
        font-size: 11px;
        color: var(--text-3);
      }
    }
  }

  .run-empty {
    padding: 14px;
    text-align: center;
    color: var(--text-3);
    font-size: 12px;
    background: var(--bg-fill);
    border: 1px dashed var(--border);
    border-radius: 5px;
  }

  .transfer-note {
    margin-top: 8px;
    font-size: 11.5px;
    color: var(--text-3);
    background: var(--bg-fill);
    border-radius: 4px;
    padding: 7px 10px;
    line-height: 1.6;

    b { color: var(--text-2); }
  }

  .start-note {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    margin-top: 10px;
    font-size: 12px;
    color: var(--text-3);
  }
  
  .model-family {
    margin-bottom: 14px;

    .family-title {
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.8px;
      color: var(--text-3);
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 8px;

      &::after {
        content: '';
        flex: 1;
        height: 1px;
        background: var(--border-light);
      }
    }
  }

  .model-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 8px;

    .model-card {
      padding: 9px 11px;
      background: var(--bg-fill); // 灰调填充，弱化刺眼白
      border: 1px solid var(--border);
      border-radius: 5px;
      cursor: pointer;
      transition: border-color 0.15s, background 0.15s;
      min-width: 0;

      &:hover {
        border-color: var(--text-faint);
        background: var(--bg-hover);
      }

      &.active {
        border-color: var(--brand);
        background: var(--brand-soft);
        box-shadow: inset 0 0 0 1px var(--brand);
      }

      .model-card-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 6px;
        margin-bottom: 5px;

        .model-name {
          font-weight: 600;
          font-size: 13.5px;
          color: var(--text-1);
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
        color: var(--text-3);
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
    color: var(--text-3);
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
