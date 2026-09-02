<template>
  <div class="artifacts-page">
    <div class="page-head">
      <div>
        <div class="page-title">制品管理</div>
        <div class="page-sub">{{ project.name || '工程' }} · 训练产出的模型版本，可下载 / 删除</div>
      </div>
      <el-button type="primary" @click="$router.push(`/project/${projectId}/train`)">
        <el-icon style="margin-right: 5px;"><Cpu /></el-icon>
        新建训练
      </el-button>
    </div>

    <!-- 统计 -->
    <div class="stats-bar">
      <div class="stat-cell">
        <span class="stat-num mono">{{ completedCount }}</span>
        <span class="stat-label">可用制品</span>
      </div>
      <div class="stat-cell">
        <span class="stat-num mono" style="color: #1f5aff;">{{ bestMap }}</span>
        <span class="stat-label">最高 mAP@50</span>
      </div>
      <div class="stat-cell">
        <span class="stat-num mono">{{ totalSize }}</span>
        <span class="stat-label">占用空间</span>
      </div>
    </div>

    <!-- 制品列表 -->
    <el-card shadow="never" class="mt-12">
      <template #header>
        <div class="card-head">
          <span>模型制品（{{ completedCount }}）</span>
          <el-button v-if="runs.length" size="small" @click="load" :loading="loading">刷新</el-button>
        </div>
      </template>

      <el-table :data="artifactRows" v-loading="loading" stripe empty-text="暂无制品，请先完成模型训练">
        <el-table-column label="版本" width="70" align="center">
          <template #default="{ row }"><code class="mono">v{{ row.id }}</code></template>
        </el-table-column>
        <el-table-column prop="model_name" label="模型" width="130">
          <template #default="{ row }">
            <code class="mono">{{ row.model_name }}</code>
            <el-tag
              v-if="isSegModel(row.model_name)"
              type="warning"
              size="small"
              effect="plain"
              style="margin-left: 6px;"
            >分割</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="mAP@50" width="95" align="center">
          <template #default="{ row }">
            <span v-if="row.final_map50 !== null" class="map-val">{{ row.final_map50.toFixed(3) }}</span>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="mAP@50:95" width="95" align="center">
          <template #default="{ row }">
            {{ row.final_map50_95 !== null ? row.final_map50_95.toFixed(3) : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="Epochs" width="75" align="center">
          <template #default="{ row }">{{ row.epochs }}</template>
        </el-table-column>
        <el-table-column label="训练时间" min-width="150">
          <template #default="{ row }">{{ formatDate(row.completed_at || row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="权重" width="110" align="center">
          <template #default="{ row }">
            <span v-if="row.has_weights" class="ok-mono mono">{{ row.weights_size_mb }} MB</span>
            <el-tag v-else type="danger" size="small">文件缺失</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" align="center" fixed="right">
          <template #default="{ row }">
            <el-dropdown
              v-if="row.has_weights"
              trigger="click"
              @command="(cmd) => handleDownload(row, cmd)"
            >
              <el-button
                type="primary"
                link
                size="small"
                :loading="exportingId === row.id"
              >
                <template v-if="exportingId !== row.id">下载 <el-icon style="margin-left: 2px;"><ArrowDown /></el-icon></template>
                <template v-else>导出中... {{ exportingFormat }}</template>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="pt">PyTorch (.pt) — {{ row.weights_size_mb }} MB</el-dropdown-item>
                  <el-dropdown-item command="onnx">
                    {{ row.exports.some(e => e.format === 'onnx') ? 'ONNX — 已导出，直接下载' : 'ONNX — 导出后下载' }}
                  </el-dropdown-item>
                  <el-dropdown-item command="torchscript">
                    {{ row.exports.some(e => e.format === 'torchscript') ? 'TorchScript — 已导出，直接下载' : 'TorchScript — 导出后下载' }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-tooltip v-if="!row.has_weights" content="权重文件缺失，无法下载">
              <span><el-button type="primary" link size="small" disabled>下载</el-button></span>
            </el-tooltip>
            <el-popconfirm
              :title="`删除 v${row.id}（${row.model_name}）？\n验证与测试将不再包含此制品`"
              width="260"
              confirm-button-text="删除"
              confirm-button-type="danger"
              @confirm="deleteArtifact(row)"
            >
              <template #reference>
                <el-button type="danger" link size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 删除结果提示 -->
    <el-alert
      v-if="deletedInfo"
      type="info"
      :closable="true"
      show-icon
      :title="deletedInfo"
      class="mt-12"
      @close="deletedInfo = ''"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { projectApi, trainApi } from '@/api'

const route = useRoute()
const projectId = computed(() => parseInt(route.params.id))

const loading = ref(false)
const project = ref({})
const runs = ref([])
const deletedInfo = ref('')
const exportingId = ref(null) // 正在导出的 run id
const exportingFormat = ref('')

// 仅展示已完成的制品（训练失败/进行中不构成制品）
const artifactRows = computed(() => {
  return runs.value.filter(r => r.status === 'completed')
})

const completedCount = computed(() => artifactRows.value.length)

const bestMap = computed(() => {
  const vals = artifactRows.value.map(r => r.final_map50).filter(v => v !== null)
  return vals.length ? Math.max(...vals).toFixed(3) : '—'
})

const totalSize = computed(() => {
  const total = artifactRows.value.reduce((s, r) => s + (r.weights_size_mb || 0), 0)
  return total > 0 ? `${total.toFixed(1)} MB` : '—'
})

const isSegModel = (name) => (name || '').includes('-seg')

const load = async () => {
  loading.value = true
  try {
    project.value = await projectApi.get(projectId.value)
    runs.value = await trainApi.listRuns(projectId.value)
  } finally {
    loading.value = false
  }
}

const downloadArtifact = (row) => {
  const a = document.createElement('a')
  a.href = `/api/projects/${projectId.value}/runs/${row.id}/download`
  a.download = `${row.model_name}-v${row.id}.pt`
  document.body.appendChild(a)
  a.click()
  a.remove()
}

// 多格式下载：pt 直接下载；onnx/torchscript 未导出则先导出再下载
const handleDownload = async (row, format) => {
  if (format === 'pt') {
    downloadArtifact(row)
    return
  }
  if (exportingId.value) return // 已有导出任务进行中
  exportingId.value = row.id
  exportingFormat.value = format.toUpperCase()
  try {
    const res = await trainApi.exportModel(projectId.value, row.id, format)
    if (res.success) {
      const a = document.createElement('a')
      a.href = res.url
      a.download = res.url.split('/').pop()
      document.body.appendChild(a)
      a.click()
      a.remove()
      ElMessage.success(res.message)
      load() // 刷新 exports 显示（已导出标记）
    }
  } catch (e) {
    // interceptor handles error
  } finally {
    exportingId.value = null
    exportingFormat.value = ''
  }
}

const deleteArtifact = async (row) => {
  try {
    const res = await trainApi.deleteRun(projectId.value, row.id)
    ElMessage.success(res.message || '制品已删除')
    deletedInfo.value = `已删除 v${row.id}（${row.model_name}）。模型验证与测试识别中该版本已移除。`
    load()
  } catch (e) {
    // interceptor handles error
  }
}

const formatDate = (d) => (d ? new Date(d).toLocaleString('zh-CN') : '—')

onMounted(load)
</script>

<style lang="scss" scoped>
.stats-bar {
  display: flex;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 4px;
  overflow: hidden;

  .stat-cell {
    flex: 1;
    text-align: center;
    padding: 12px 0;
    border-right: 1px solid var(--border-light);

    &:last-child { border-right: none; }

    .stat-num {
      display: block;
      font-size: 20px;
      font-weight: 700;
      color: var(--text-1);
    }

    .stat-label {
      font-size: 11px;
      color: var(--text-3);
      margin-top: 2px;
    }
  }
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.map-val {
  font-weight: 700;
  color: #1f5aff;
}

.ok-mono {
  color: #0f9d58;
  font-weight: 600;
}
</style>
