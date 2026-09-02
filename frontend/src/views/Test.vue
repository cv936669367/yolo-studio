<template>
  <div class="test-page">
    <div class="page-header">
      <h2>测试识别</h2>
      <p>上传图片进行目标检测推理，查看实时检测结果</p>
    </div>

    <!-- No model -->
    <el-empty v-if="!currentRun" description="暂无可用模型，请先完成训练">
      <el-button type="primary" @click="$router.push(`/project/${projectId}/train`)">
        前往训练
      </el-button>
    </el-empty>

    <template v-else>
      <el-row :gutter="20">
        <!-- Left: Image & Results -->
        <el-col :span="16">
          <!-- Upload / Result Display -->
          <el-card shadow="never" header="检测结果">
            <div v-if="!previewUrl" class="upload-area" @click="triggerUpload">
              <el-icon :size="48"><Upload /></el-icon>
              <p>点击或拖拽上传测试图片</p>
              <span class="upload-tip">支持 JPG、PNG、WebP 格式</span>
            </div>
            
            <div v-else class="result-container">
              <div class="image-wrapper" ref="imageWrapperRef">
                <img
                  :src="previewUrl"
                  alt="Test Image"
                  ref="testImageRef"
                  @load="onImageLoad"
                />
                
                <!-- Detection overlays -->
                <svg
                  v-if="detections.length > 0 && imageDimensions.width"
                  class="detection-overlay"
                  :viewBox="`0 0 ${imageDimensions.width} ${imageDimensions.height}`"
                >
                  <g v-for="(det, idx) in detections" :key="idx">
                    <rect
                      :x="det.bbox.x1"
                      :y="det.bbox.y1"
                      :width="det.bbox.x2 - det.bbox.x1"
                      :height="(det.bbox.y3 || det.bbox.y2) - det.bbox.y1"
                      stroke="#67c23a"
                      stroke-width="3"
                      fill="rgba(103,194,58,0.15)"
                      rx="4"
                    />
                    <text
                      :x="det.bbox.x1"
                      :y="det.bbox.y1 - 6"
                      fill="#67c23a"
                      font-size="13"
                      font-weight="600"
                    >
                      {{ det.class_name }} {{ (det.confidence * 100).toFixed(1) }}%
                    </text>
                  </g>
                </svg>
                
                <!-- Loading overlay -->
                <div v-if="detecting" class="loading-overlay">
                  <el-icon :size="32" class="is-loading"><Loading /></el-icon>
                  <span>检测中...</span>
                </div>
              </div>
              
              <div class="result-actions">
                <el-button type="primary" @click="runDetection" :loading="detecting">
                  <VideoPlay /> {{ detecting ? '检测中...' : '开始检测' }}
                </el-button>
                <el-button @click="clearResult">更换图片</el-button>
              </div>
            </div>
            
            <input
              ref="fileInputRef"
              type="file"
              accept="image/*"
              style="display: none;"
              @change="handleFileChange"
            />
          </el-card>

          <!-- Detection Results Table -->
          <el-card v-if="detections.length > 0" shadow="never" header="检测结果详情" style="margin-top: 16px;">
            <el-table :data="sortedDetections" stripe size="default">
              <el-table-column label="#" width="50" align="center">
                <template #default="{ $index }">{{ $index + 1 }}</template>
              </el-table-column>
              <el-table-column label="类别" width="120">
                <template #default="{ row }">
                  <el-tag type="success">{{ row.class_name }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="置信度" min-width="180">
                <template #default="{ row }">
                  <div style="display: flex; align-items: center; gap: 10px;">
                    <el-progress
                      :percentage="(row.confidence * 100)"
                      :color="getConfidenceColor(row.confidence)"
                      :stroke-width="10"
                      :show-text="false"
                      style="flex: 1;"
                    />
                    <span style="font-family: monospace; min-width: 55px;">
                      {{ (row.confidence * 100).toFixed(1) }}%
                    </span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="位置 (x, y, w, h)" min-width="180">
                <template #default="{ row }">
                  <code class="bbox-code">
                    ({{ Math.round(row.bbox.x1) }}, {{ Math.round(row.bbox.y1) }}) 
                    {{ Math.round(row.bbox.x2 - row.bbox.x1) }}×{{ Math.round((row.bbox.y3 || row.bbox.y2) - row.bbox.y1) }}
                  </code>
                </template>
              </el-table-column>
            </el-table>
            
            <el-divider />
            
            <el-descriptions :column="3" border size="small">
              <el-descriptions-item label="检测目标数">
                <strong>{{ detections.length }}</strong>
              </el-descriptions-item>
              <el-descriptions-item label="最高置信度">
                <strong style="color: #67c23a;">{{ maxConfidence }}</strong>
              </el-descriptions-item>
              <el-descriptions-item label="平均置信度">
                <strong>{{ avgConfidence }}</strong>
              </el-descriptions-item>
              <el-descriptions-item label="推理耗时">
                <strong>{{ inferenceTime }} ms</strong>
              </el-descriptions-item>
              <el-descriptions-item label="涉及类别">
                <strong>{{ uniqueClasses.join(', ') }}</strong>
              </el-descriptions-item>
              <el-descriptions-item label="使用模型">
                <code>{{ currentRun?.model_name }}</code>
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>

        <!-- Right: Settings -->
        <el-col :span="8">
          <!-- Model Selection -->
          <el-card shadow="never" header="选择模型">
            <el-select v-model="selectedRunId" style="width: 100%;" size="default" placeholder="选择训练模型版本">
              <el-option
                v-for="r in completedRuns"
                :key="r.id"
                :label="`${r.model_name} · ${formatDate(r.completed_at)}`"
                :value="r.id"
              >
                <span style="float: left;">{{ r.model_name }} · mAP {{ r.final_map50?.toFixed(3) || '-' }}</span>
                <span style="float: right; color: #86909c; font-size: 12px;">{{ formatDate(r.completed_at) }}</span>
              </el-option>
            </el-select>
            <p class="tool-tip" style="margin-top: 8px; font-size: 11px; color: #86909c;">
              共 {{ completedRuns.length }} 个模型版本，选择后推理使用该版本权重
            </p>
          </el-card>

          <!-- Model Info -->
          <el-card shadow="never" header="当前模型" style="margin-top: 16px;">
            <div class="model-info-box">
              <div class="model-name">{{ currentRun?.model_name }}</div>
              <div class="info-row">
                <span class="label">训练时间</span>
                <span>{{ formatDate(currentRun?.completed_at) }}</span>
              </div>
              <div class="info-row">
                <span class="label">mAP@50</span>
                <span class="value-primary">{{ currentRun?.final_map50?.toFixed(3) || '-' }}</span>
              </div>
              <div class="info-row">
                <span class="label">状态</span>
                <el-tag type="success" size="small">已就绪</el-tag>
              </div>
            </div>
          </el-card>

          <!-- Detection Parameters -->
          <el-card shadow="never" header="检测参数" style="margin-top: 16px;">
            <el-form label-position="top" size="default">
              <el-form-item label="置信度阈值">
                <el-slider
                  v-model="params.confThreshold"
                  :min="0.05"
                  :max="0.95"
                  :step="0.05"
                  show-input
                  :input-size="'small'"
                  :format-tooltip="(v) => `${(v * 100).toFixed(0)}%`"
                />
              </el-form-item>
              <el-form-item label="NMS IoU 阈值">
                <el-slider
                  v-model="params.iouThreshold"
                  :min="0.1"
                  :max="0.9"
                  :step="0.05"
                  show-input
                  :input-size="'small'"
                  :format-tooltip="(v) => `${(v * 100).toFixed(0)}%`"
                />
              </el-form-item>
            </el-form>
          </el-card>

          <!-- Quick Stats -->
          <el-card shadow="none" header="本次统计" style="margin-top: 16px;" v-if="detections.length > 0">
            <el-statistic title="检测目标数" :value="detections.length" />
            <el-divider />
            <el-row :gutter="12">
              <el-col :span="12">
                <el-statistic title="最高置信度" :value="parseFloat(maxConfidence)" suffix="%" :precision="1" />
              </el-col>
              <el-col :span="12">
                <el-statistic title="平均置信度" :value="parseFloat(avgConfidence)" suffix="%" :precision="1" />
              </el-col>
            </el-row>
          </el-card>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { projectApi, trainApi, inferenceApi } from '@/api'

const route = useRoute()
const projectId = computed(() => parseInt(route.params.id))

// Refs
const fileInputRef = ref(null)
const testImageRef = ref(null)
const imageWrapperRef = ref(null)

// Data
const trainRuns = ref([])
const project = ref({})
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

// State
const previewUrl = ref(null)
const selectedFile = ref(null)
const detections = ref([])
const detecting = ref(false)
const inferenceTime = ref(0)
const imageDimensions = reactive({ width: 0, height: 0 })

// Parameters
const params = reactive({
  confThreshold: 0.25,
  iouThreshold: 0.45,
})

// Computed
const sortedDetections = computed(() => {
  return [...detections.value].sort((a, b) => b.confidence - a.confidence)
})

const maxConfidence = computed(() => {
  if (!detections.value.length) return '0.0'
  return (Math.max(...detections.value.map(d => d.confidence)) * 100).toFixed(1)
})

const avgConfidence = computed(() => {
  if (!detections.value.length) return '0.0'
  const sum = detections.value.reduce((s, d) => s + d.confidence, 0)
  return ((sum / detections.value.length) * 100).toFixed(1)
})

const uniqueClasses = computed(() => {
  return [...new Set(detections.value.map(d => d.class_name))]
})

// Methods
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

const triggerUpload = () => fileInputRef.value?.click()

const handleFileChange = (e) => {
  const file = e.target.files[0]
  if (file && file.type.startsWith('image/')) {
    selectedFile.value = file
    previewUrl.value = URL.createObjectURL(file)
    detections.value = []
  }
}

const onImageLoad = () => {
  const img = testImageRef.value
  if (img) {
    imageDimensions.width = img.naturalWidth
    imageDimensions.height = img.naturalHeight
  }
}

const runDetection = async () => {
  if (!selectedFile.value || !currentRun.value) return
  
  detecting.value = true
  detections.value = []
  
  try {
    const result = await inferenceApi.predict(selectedFile.value, {
      runId: currentRun.value.id,
      confThreshold: params.confThreshold,
      iouThreshold: params.iouThreshold,
    })
    
    if (result.success) {
      detections.value = result.detections
      inferenceTime.value = result.inference_time_ms
      
      ElMessage.success(`检测完成，发现 ${result.detections.length} 个目标`)
    } else {
      ElMessage.error('检测失败')
    }
  } catch (e) {
    // Error handled by interceptor
  } finally {
    detecting.value = false
  }
}

const clearResult = () => {
  previewUrl.value = null
  selectedFile.value = null
  detections.value = []
  if (fileInputRef.value) fileInputRef.value.value = ''
}

const getConfidenceColor = (conf) => {
  if (conf > 0.8) return '#67c23a'
  if (conf > 0.5) return '#e6a23c'
  return '#f56c6c'
}

const formatDate = (dateStr) => dateStr ? new Date(dateStr).toLocaleString('zh-CN') : '-'

// Drag and drop support
const handleDrop = (e) => {
  e.preventDefault()
  const file = e.dataTransfer.files[0]
  if (file && file.type.startsWith('image/')) {
    selectedFile.value = file
    previewUrl.value = URL.createObjectURL(file)
    detections.value = []
  }
}

onMounted(() => {
  loadProject()
  loadTrainRuns()
  
  // Add drop listener
  document.addEventListener('drop', handleDrop)
  document.addEventListener('dragover', (e) => e.preventDefault())
})
</script>

<style lang="scss" scoped>
.test-page {
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
  
  .upload-area {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 400px;
    border: 2px dashed #dcdfe6;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
    color: #999;
    
    &:hover {
      border-color: #409eff;
      color: #409eff;
    }
    
    p {
      margin-top: 12px;
      font-size: 15px;
    }
    
    .upload-tip {
      margin-top: 8px;
      font-size: 12px;
    }
  }
  
  .result-container {
    .image-wrapper {
      position: relative;
      display: inline-block;
      
      > img {
        max-width: 100%;
        max-height: 500px;
        border-radius: 6px;
        display: block;
      }
      
      .detection-overlay {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
      }
      
      .loading-overlay {
        position: absolute;
        inset: 0;
        background: rgba(0, 0, 0, 0.6);
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 12px;
        color: #fff;
        font-size: 14px;
      }
    }
    
    .result-actions {
      margin-top: 16px;
      display: flex;
      gap: 12px;
    }
  }
  
  .model-info-box {
    padding: 12px;
    background: #f5f7fa;
    border-radius: 6px;
    
    .model-name {
      font-size: 18px;
      font-weight: 700;
      font-family: monospace;
      color: #1a1d27;
      margin-bottom: 12px;
    }
    
    .info-row {
      display: flex;
      justify-content: space-between;
      padding: 6px 0;
      font-size: 13px;
      
      .label { color: #999; }
      .value-primary { color: #409eff; font-weight: 600; }
    }
  }
  
  .bbox-code {
    font-size: 12px;
    color: #666;
    background: #f5f7fa;
    padding: 2px 6px;
    border-radius: 3px;
  }
}
</style>
