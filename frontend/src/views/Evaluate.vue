<template>
  <div class="evaluate-page">
    <div class="page-head">
      <div>
        <div class="page-title">模型验证</div>
        <div class="page-sub">查看真实训练指标与可视化结果</div>
      </div>
      <!-- 多模型选择 -->
      <el-select
        v-if="completedRuns.length"
        v-model="selectedRunId"
        size="default"
        style="width: 300px;"
        placeholder="选择训练模型版本"
      >
        <el-option
          v-for="r in completedRuns"
          :key="r.id"
          :label="`${r.model_name} · ${formatDate(r.completed_at)} · mAP ${r.final_map50?.toFixed(3) || '-'}`"
          :value="r.id"
        />
      </el-select>
    </div>

    <!-- 无训练记录 -->
    <div v-if="!currentRun" class="panel-empty">
      <el-empty description="暂无训练记录，请先完成模型训练">
        <el-button type="primary" @click="$router.push(`/project/${projectId}/train`)">前往训练</el-button>
      </el-empty>
    </div>

    <template v-else>
      <!-- 指标概览 -->
      <el-row :gutter="12" class="metrics-row">
        <el-col :span="6">
          <div class="metric-box">
            <div class="metric-value" style="color: #1f5aff;">{{ fmt(currentRun.final_map50) }}</div>
            <div class="metric-label">mAP@50</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="metric-box">
            <div class="metric-value" style="color: #7c3aed;">{{ fmt(currentRun.final_map50_95) }}</div>
            <div class="metric-label">mAP@50:95</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="metric-box">
            <div class="metric-value" style="color: #0f9d58;">{{ fmtPct(currentRun.precision) }}</div>
            <div class="metric-label">Precision</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="metric-box">
            <div class="metric-value" style="color: #e6a23c;">{{ fmtPct(currentRun.recall) }}</div>
            <div class="metric-label">Recall</div>
          </div>
        </el-col>
      </el-row>

      <!-- 训练曲线（真实逐 epoch 指标） -->
      <el-card shadow="never" header="训练曲线（逐 epoch 真实指标）" class="mt-12">
        <TrainingChart v-if="history.length > 0" :metrics="history" />
        <el-empty v-else description="训练过程中未记录到指标" :image-size="60" />
      </el-card>

      <!-- 训练产物图片（ultralytics 生成） -->
      <el-row :gutter="12" class="mt-12">
        <el-col :span="12">
          <el-card shadow="never" header="混淆矩阵">
            <img
              v-if="artifacts.confusion"
              :src="artifacts.confusion"
              class="artifact-img"
              alt="confusion matrix"
            />
            <el-empty v-else description="暂无混淆矩阵" :image-size="60" />
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never" header="训练结果曲线 (results.png)">
            <img
              v-if="artifacts.results"
              :src="artifacts.results"
              class="artifact-img"
              alt="results"
            />
            <el-empty v-else description="暂无训练结果图" :image-size="60" />
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="12" class="mt-12">
        <el-col :span="12">
          <el-card shadow="never" header="验证集预测样例">
            <img
              v-if="artifacts.valPred"
              :src="artifacts.valPred"
              class="artifact-img"
              alt="val prediction"
            />
            <el-empty v-else description="暂无预测样例" :image-size="60" />
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never" header="标签分布">
            <img
              v-if="artifacts.labels"
              :src="artifacts.labels"
              class="artifact-img"
              alt="labels"
            />
            <el-empty v-else description="暂无标签分布图" :image-size="60" />
          </el-card>
        </el-col>
      </el-row>

      <!-- 训练记录对比 -->
      <el-card v-if="trainRuns.length > 1" shadow="never" header="历史训练记录" class="mt-12">
        <el-table :data="sortedRuns" stripe size="default">
          <el-table-column prop="model_name" label="模型" width="110">
            <template #default="{ row }"><code class="mono">{{ row.model_name }}</code></template>
          </el-table-column>
          <el-table-column prop="epochs" label="Epochs" width="80" align="center" />
          <el-table-column label="mAP@50" width="100" align="center">
            <template #default="{ row }">
              <span v-if="row.final_map50 !== null" style="font-weight: 600; color: #1f5aff;">
                {{ row.final_map50.toFixed(3) }}
              </span>
              <span v-else>—</span>
            </template>
          </el-table-column>
          <el-table-column label="mAP@50:95" width="110" align="center">
            <template #default="{ row }">
              {{ row.final_map50_95 !== null ? row.final_map50_95.toFixed(3) : '—' }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="时间" min-width="150">
            <template #default="{ row }">{{ formatDate(row.completed_at || row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="90" align="center">
            <template #default="{ row }">
              <el-button
                type="primary"
                link
                size="small"
                :disabled="row.status !== 'completed'"
                @click="selectedRunId = row.id"
              >
                {{ currentRun?.id === row.id ? '查看中' : '查看' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 模型导出 -->
      <el-card shadow="never" header="模型导出" class="mt-12">
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="导出训练好的模型权重，用于本地部署或推理"
          style="margin-bottom: 12px;"
        />
        <div class="export-row">
          <div class="export-info">
            <div class="export-model mono">{{ currentRun.model_name }}</div>
            <div class="export-meta mono">
              best.pt · mAP@50 {{ fmt(currentRun.final_map50) }} · 训练 {{ currentRun.epochs }} epochs
            </div>
          </div>
          <div class="export-actions">
            <el-select v-model="exportFormat" size="default" style="width: 150px;">
              <el-option label="PyTorch (.pt)" value="pt" />
              <el-option label="ONNX" value="onnx" />
              <el-option label="TorchScript" value="torchscript" />
            </el-select>
            <el-button
              v-if="exportFormat === 'pt'"
              type="primary"
              @click="downloadPt"
              :loading="ptLoading"
            >
              <el-icon style="margin-right: 4px;"><Download /></el-icon>
              下载权重
            </el-button>
            <el-button
              v-else
              type="primary"
              @click="exportModel"
              :loading="exporting"
            >
              <el-icon style="margin-right: 4px;"><Download /></el-icon>
              {{ exporting ? '导出中...' : '导出 ' + exportFormat.toUpperCase() }}
            </el-button>
          </div>
        </div>
        <div v-if="exportedUrl" class="export-result">
          <el-alert
            type="success"
            :closable="false"
            show-icon
            :title="exportMessage"
          >
            <template #default>
              <el-link type="primary" :href="exportedUrl" :download="exportedName" target="_blank">
                <el-icon style="margin-right: 4px;"><Download /></el-icon>
                点击下载导出文件（{{ exportedSize }} MB）
              </el-link>
            </template>
          </el-alert>
        </div>
      </el-card>

      <div class="mt-16" style="display: flex; justify-content: flex-end;">
        <el-button type="primary" @click="$router.push(`/project/${projectId}/test`)">
          前往测试识别
        </el-button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { projectApi, trainApi } from '@/api'
import TrainingChart from '@/components/TrainingChart.vue'

const route = useRoute()
const projectId = computed(() => parseInt(route.params.id))

const trainRuns = ref([])
const exportFormat = ref('pt')
const exporting = ref(false)
const ptLoading = ref(false)
const exportedUrl = ref('')
const exportedName = ref('')
const exportedSize = ref('')
const exportMessage = ref('')

const completedRuns = computed(() =>
  trainRuns.value.filter(r => r.status === 'completed')
)
const selectedRunId = ref(null)
const currentRun = computed(() => {
  if (!completedRuns.value.length) return null
  if (selectedRunId.value) {
    const found = completedRuns.value.find(r => r.id === selectedRunId.value)
    if (found) return found
  }
  return completedRuns.value[completedRuns.value.length - 1]
})
watch(currentRun, (run) => {
  if (run) selectedRunId.value = run.id
}, { immediate: true })

const history = computed(() => currentRun.value?.metrics_history || [])

const sortedRuns = computed(() => [...trainRuns.value].reverse())

// 训练产物图片（真实 ultralytics 输出）
const artifacts = computed(() => {
  if (!currentRun.value) return {}
  const base = `/outputs/${projectId.value}/run_${currentRun.value.id}`
  return {
    confusion: `${base}/confusion_matrix.png`,
    results: `${base}/results.png`,
    valPred: `${base}/val_batch0_pred.jpg`,
    labels: `${base}/labels.jpg`,
  }
})

const fmt = (v) => (v !== null && v !== undefined ? v.toFixed(3) : '—')
const fmtPct = (v) => (v !== null && v !== undefined ? `${(v * 100).toFixed(1)}%` : '—')

const statusType = (s) => ({ pending: 'info', running: 'warning', completed: 'success', failed: 'danger' }[s] || 'info')
const statusLabel = (s) => ({ pending: '待运行', running: '训练中', completed: '已完成', failed: '失败' }[s] || s)

const formatDate = (d) => (d ? new Date(d).toLocaleString('zh-CN') : '—')

const load = async () => {
  try {
    trainRuns.value = await trainApi.listRuns(projectId.value)
  } catch (e) {}
}

// ─── 模型导出 ───────────────────────────────────────────
const downloadPt = async () => {
  if (!currentRun.value) return
  ptLoading.value = true
  try {
    // 直接浏览器下载 best.pt
    const a = document.createElement('a')
    a.href = `/api/projects/${projectId.value}/runs/${currentRun.value.id}/download`
    a.download = `${currentRun.value.model_name}-best.pt`
    document.body.appendChild(a)
    a.click()
    a.remove()
    ElMessage.success('开始下载模型权重')
  } finally {
    ptLoading.value = false
  }
}

const exportModel = async () => {
  if (!currentRun.value) return
  exporting.value = true
  exportedUrl.value = ''
  try {
    const res = await trainApi.exportModel(projectId.value, currentRun.value.id, exportFormat.value)
    if (res.success) {
      exportedUrl.value = res.url
      exportedName.value = res.url.split('/').pop()
      exportedSize.value = res.size_mb
      exportMessage.value = res.message
    }
  } catch (e) {
    // interceptor handles error
  } finally {
    exporting.value = false
  }
}

onMounted(load)
</script>

<style lang="scss" scoped>
.panel-empty {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 4px;
  padding: 60px 0;
}

.metrics-row {
  .metric-box {
    background: #fff;
    border: 1px solid #e5e6eb;
    border-radius: 4px;
    text-align: center;
    padding: 20px 0;

    .metric-value {
      font-size: 30px;
      font-weight: 700;
      font-variant-numeric: tabular-nums;
    }

    .metric-label {
      font-size: 12px;
      color: #86909c;
      margin-top: 6px;
    }
  }
}

.artifact-img {
  width: 100%;
  display: block;
  border: 1px solid #f2f3f5;
  border-radius: 3px;
}

.export-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;

  .export-info {
    .export-model {
      font-size: 16px;
      font-weight: 700;
      color: #1f2329;
    }

    .export-meta {
      font-size: 12px;
      color: #86909c;
      margin-top: 3px;
    }
  }

  .export-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.export-result {
  margin-top: 12px;
}
</style>
