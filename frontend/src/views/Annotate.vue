<template>
  <div class="annotate-page">
    <!-- Top toolbar -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button @click="$router.back()">
          <el-icon><ArrowLeft /></el-icon>
        </el-button>
        <div class="breadcrumb">
          <span class="crumb-project">{{ project.name || '工程' }}</span>
          <span class="crumb-sep">›</span>
          <span class="crumb-page">ANNOTATE</span>
          <span class="crumb-sep">›</span>
          <span class="crumb-file" :title="fileName">{{ fileName }}</span>
        </div>
        <el-button-group>
          <el-button :disabled="currentIndex === 0" @click="prevImage">
            <el-icon><ArrowLeftBold /></el-icon>
          </el-button>
          <el-button :disabled="currentIndex >= images.length - 1" @click="nextImage">
            <el-icon><ArrowRightBold /></el-icon>
          </el-button>
        </el-button-group>
        <span class="image-counter mono">{{ currentIndex + 1 }} / {{ images.length }}</span>
      </div>
      <div class="toolbar-center">
        <span class="img-meta mono" v-if="currentImage">
          {{ imageWidth }}×{{ imageHeight }}px · {{ annotations.length }} 标注
        </span>
      </div>
      <div class="toolbar-right">
        <el-tooltip content="撤销 (Ctrl+Z)">
          <el-button :disabled="!canUndo" @click="undo" circle size="small">
            <el-icon><RefreshLeft /></el-icon>
          </el-button>
        </el-tooltip>
        <el-tooltip content="重做 (Ctrl+Shift+Z)">
          <el-button :disabled="!canRedo" @click="redo" circle size="small">
            <el-icon><RefreshRight /></el-icon>
          </el-button>
        </el-tooltip>
        <el-tooltip content="复制选中 (Ctrl+D)">
          <el-button :disabled="!selectedAnno" @click="duplicateSelected" circle size="small">
            <el-icon><CopyDocument /></el-icon>
          </el-button>
        </el-tooltip>
        <el-tooltip content="删除选中 (Delete)">
          <el-button :disabled="!selectedAnno" @click="deleteSelected" circle size="small" type="danger">
            <el-icon><Delete /></el-icon>
          </el-button>
        </el-tooltip>
      </div>
    </div>

    <!-- Film strip: image thumbnails -->
    <div class="film-strip" v-if="images.length">
      <div
        v-for="(img, idx) in images"
        :key="img.id"
        class="strip-item"
        :class="{ active: idx === currentIndex }"
        @click="goToImage(idx)"
      >
        <img :src="img.file_path" :alt="img.original_name" />
        <span class="strip-badge mono">{{ img.annotation_count || 0 }}</span>
      </div>
    </div>

    <div class="annotate-content">
      <!-- Left: property panel (Roboflow style) -->
      <aside class="image-panel">
        <!-- ANNOTATIONS -->
        <div class="panel-section">
          <div class="panel-title">ANNOTATIONS</div>
          <div class="anno-summary">
            <div class="summary-item">
              <span class="summary-num mono">{{ annotations.length }}</span>
              <span class="summary-label">标注</span>
            </div>
            <div class="summary-item">
              <span class="summary-num mono">{{ annotatedClassCount }}</span>
              <span class="summary-label">类别</span>
            </div>
            <div class="summary-item">
              <span class="summary-num mono">{{ unusedClasses.length }}</span>
              <span class="summary-label">未用</span>
            </div>
          </div>
        </div>

        <!-- GROUP -->
        <div class="panel-section">
          <div class="panel-title">GROUP</div>
          <div class="img-info">
            <div class="info-row">
              <span class="info-label">文件</span>
              <span class="info-value" :title="currentImage?.original_name">{{ fileName }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">尺寸</span>
              <span class="info-value mono">{{ currentImage?.width || '-' }} × {{ currentImage?.height || '-' }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">分组</span>
              <span class="info-value mono">{{ currentIndex + 1 }} / {{ images.length }}</span>
            </div>
          </div>
        </div>

        <!-- CLASSES -->
        <div class="panel-section">
          <div class="panel-title">CLASSES</div>
          <div class="class-buttons">
            <div
              v-for="(cls, i) in project.classes"
              :key="cls"
              class="class-btn"
              :class="{ active: selectedClass === cls }"
              :style="selectedClass === cls ? { borderColor: getClassColor(cls), color: getClassColor(cls) } : {}"
              @click="selectedClass = cls"
            >
              <span class="class-dot" :style="{ background: getClassColor(cls) }"></span>
              <span class="class-name">{{ cls }}</span>
              <span class="class-count mono">{{ classInstanceCount(cls) }}</span>
              <kbd>{{ i + 1 }}</kbd>
            </div>
            <div v-if="!project.classes?.length" class="panel-empty">工程未配置类别</div>
          </div>
          <!-- Unused Classes -->
          <div v-if="unusedClasses.length" class="unused-classes">
            <div class="unused-title">Unused Classes ({{ unusedClasses.length }})</div>
            <div
              v-for="cls in unusedClasses"
              :key="'u-' + cls"
              class="unused-item"
              @click="selectedClass = cls"
            >
              <span class="class-dot" :style="{ background: getClassColor(cls) }"></span>
              <span class="class-name">{{ cls }}</span>
              <kbd>+</kbd>
            </div>
          </div>
        </div>

        <!-- TAGS -->
        <div class="panel-section">
          <div class="panel-title">TAGS</div>
          <div class="tag-box">
            <div v-if="imageTags.length" class="tag-list">
              <el-tag
                v-for="t in imageTags"
                :key="t"
                size="small"
                closable
                effect="plain"
                @close="removeTag(t)"
              >{{ t }}</el-tag>
            </div>
            <div v-else class="no-tags">No Tags Applied</div>
            <div class="tag-add">
              <el-input v-model="tagInput" size="small" placeholder="Add tag..." @keyup.enter="addTag" />
              <el-button size="small" @click="addTag">+ Add</el-button>
            </div>
          </div>
        </div>

        <!-- FIND OBJECTS WITH AI -->
        <div class="panel-section">
          <el-button type="primary" plain style="width: 100%;" @click="autoAnnotate" :disabled="!currentImage" :loading="aiLoading">
            <el-icon><MagicStick /></el-icon> Find Objects with AI
          </el-button>
        </div>
      </aside>

      <!-- Center: canvas -->
      <div class="canvas-area" ref="canvasAreaRef">
        <div v-if="!currentImage" class="empty-canvas">
          <el-empty description="暂无图片" :image-size="80" />
        </div>
        <div v-else class="canvas-wrapper" :style="{ transform: `scale(${zoom})` }">
          <img
            ref="imageRef"
            :src="getImageUrl(currentImage)"
            @mousedown="handleMouseDown"
            @mousemove="handleMouseMove"
            @mouseup="handleMouseUp"
            @mouseleave="handleMouseLeave"
            @dblclick="handleDoubleClick"
            @contextmenu.prevent="handleRightClick($event)"
            draggable="false"
            class="annotation-image"
          />

          <svg class="overlay-svg" v-if="imageLoaded">
            <!-- Existing annotations -->
            <g
              v-for="anno in annotations"
              :key="anno.id"
              class="anno-shape"
              :class="{ selected: selectedId === anno.id }"
            >
              <!-- Rectangle -->
              <template v-if="anno.anno_type === 'rectangle' && anno.bbox">
                <rect
                  :x="toDisplayX(anno.bbox.x)"
                  :y="toDisplayY(anno.bbox.y)"
                  :width="toDisplayW(anno.bbox.w)"
                  :height="toDisplayH(anno.bbox.h)"
                  :fill="classColorFill(anno.class_name)"
                  :stroke="getClassColor(anno.class_name)"
                  :stroke-width="selectedId === anno.id ? 2.5 : 2"
                  rx="1"
                />
                <!-- Label tag -->
                <g :transform="`translate(${toDisplayX(anno.bbox.x)}, ${toDisplayY(anno.bbox.y)})`">
                  <rect
                    :width="labelWidth(anno.class_name)"
                    height="16"
                    :fill="getClassColor(anno.class_name)"
                    rx="2"
                  />
                  <text x="3" y="11" fill="#fff" font-size="10" font-weight="600">
                    {{ anno.class_name }}
                  </text>
                </g>
              </template>

              <!-- Polygon -->
              <polygon
                v-else-if="anno.anno_type === 'polygon' && anno.points"
                :points="getPolygonPoints(anno.points)"
                :fill="classColorFill(anno.class_name)"
                :stroke="getClassColor(anno.class_name)"
                :stroke-width="selectedId === anno.id ? 2.5 : 2"
                stroke-linejoin="round"
              />

              <!-- Selected handles (rectangle) -->
              <g v-if="selectedId === anno.id && anno.anno_type === 'rectangle' && anno.bbox">
                <g
                  v-for="h in rectHandles(anno.bbox)"
                  :key="h.key"
                  :transform="`translate(${toDisplayX(h.x)}, ${toDisplayY(h.y)})`"
                  @mousedown.stop.prevent="startResize(anno, h.key)"
                >
                  <rect x="-4" y="-4" width="8" height="8" fill="#fff" stroke="#1f5aff" stroke-width="1.5" />
                </g>
              </g>

              <!-- Selected vertices (polygon) -->
              <g v-if="selectedId === anno.id && anno.anno_type === 'polygon' && anno.points">
                <g
                  v-for="(pt, vi) in anno.points"
                  :key="vi"
                  :transform="`translate(${toDisplayX(pt.x)}, ${toDisplayY(pt.y)})`"
                  @mousedown.stop.prevent="startVertexDrag(anno, vi)"
                >
                  <circle r="4" fill="#fff" stroke="#1f5aff" stroke-width="1.5" />
                </g>
              </g>
            </g>

            <!-- Drawing rectangle (rectangle & smart tools) -->
            <rect
              v-if="drawingRect && (currentTool === 'rectangle' || currentTool === 'smart-box')"
              :x="toDisplayX(drawingRect.x)"
              :y="toDisplayY(drawingRect.y)"
              :width="toDisplayW(drawingRect.w)"
              :height="toDisplayH(drawingRect.h)"
              stroke="#fff"
              stroke-width="1.5"
              stroke-dasharray="4,3"
              :fill="classColorFill(selectedClass)"
            />
            <!-- Smart loading indicator -->
            <g v-if="smartLoading && drawingRect" transform="translate(10, 20)">
              <rect width="130" height="22" rx="3" fill="rgba(0,0,0,0.7)" />
              <text x="8" y="15" fill="#fff" font-size="11">SAM 分割中...</text>
            </g>

            <!-- Lasso freehand trace -->
            <g v-if="currentTool === 'lasso' && lassoPoints.length > 1">
              <polygon
                :points="getLassoClosedPoints()"
                fill="rgba(31,90,255,0.15)"
                stroke="#1f5aff"
                stroke-width="1.5"
                stroke-linejoin="round"
              />
            </g>

            <!-- Polygon points -->
            <g v-if="currentTool === 'polygon' && polygonPoints.length > 0">
              <polyline
                :points="getPolygonPoints(polygonPoints)"
                stroke="#1f5aff"
                stroke-width="1.5"
                fill="none"
                stroke-dasharray="4,2"
              />
              <circle
                v-for="(pt, i) in polygonPoints"
                :key="i"
                :cx="toDisplayX(pt.x)"
                :cy="toDisplayY(pt.y)"
                r="3.5"
                fill="#1f5aff"
                stroke="#fff"
                stroke-width="1"
              />
            </g>

            <!-- Smart point prompts & live preview -->
            <g v-if="currentTool === 'smart-point'">
              <!-- 预览分割多边形 -->
              <polygon
                v-if="smartPreview && smartPreview.length > 2"
                :points="getSmartPreviewPoints()"
                fill="rgba(31,90,255,0.25)"
                stroke="#1f5aff"
                stroke-width="1.5"
                stroke-linejoin="round"
              />
              <!-- 提示点：绿=加区域 红=减区域 -->
              <g v-for="(pt, i) in smartPoints" :key="'sp-' + i">
                <circle
                  :cx="toDisplayX(pt.x)"
                  :cy="toDisplayY(pt.y)"
                  r="5"
                  :fill="pt.positive ? '#0f9d58' : '#e5484d'"
                  stroke="#fff"
                  stroke-width="1.5"
                />
                <text
                  :x="toDisplayX(pt.x) + 8"
                  :y="toDisplayY(pt.y) + 4"
                  font-size="10"
                  :fill="pt.positive ? '#0f9d58' : '#e5484d'"
                  font-weight="600"
                >{{ pt.positive ? '+' : '−' }}</text>
              </g>
            </g>
          </svg>
        </div>

        <!-- Zoom Controls -->
        <div class="zoom-controls" v-if="currentImage">
          <el-button-group size="small">
            <el-button @click="zoom = Math.max(0.2, +(zoom - 0.25).toFixed(2))">−</el-button>
            <el-button class="zoom-pct mono" @click="zoom = 1">{{ Math.round(zoom * 100) }}%</el-button>
            <el-button @click="zoom = Math.min(5, +(zoom + 0.25).toFixed(2))">＋</el-button>
            <el-button @click="fitZoom">适应</el-button>
            <el-button @click="zoom = 1">RESET</el-button>
          </el-button-group>
        </div>

        <!-- SAM 模型下载提示 -->
        <div v-if="!samDownloaded" class="sam-download-bar">
          <el-icon :size="16"><WarningFilled /></el-icon>
          <span class="sam-text">
            智能选框 / 智能点选需要 SAM 分割模型（约 {{ samSizeMb }} MB，国内源下载）
          </span>
          <el-button
            v-if="samProgress === null"
            type="primary"
            size="small"
            @click="startSamDownload"
            :loading="samStarting"
          >下载 SAM 模型</el-button>
          <div v-else class="sam-progress">
            <el-progress
              :percentage="samProgress"
              :stroke-width="6"
              :status="samProgress >= 100 ? 'success' : ''"
              style="width: 160px;"
            />
            <span class="sam-pct mono">{{ samProgress }}%</span>
          </div>
        </div>

        <!-- Smart session hint -->
        <div v-if="currentTool === 'smart-point' && smartPoints.length" class="smart-hint">
          <span class="hint-pos">正 {{ positiveCount }}</span>
          <span class="hint-neg">负 {{ negativeCount }}</span>
          <span class="hint-action">左键添加 · 右键排除 · 回车确认</span>
          <el-button type="primary" size="small" :disabled="!smartPreview" @click="confirmSmart">
            ✓ 确认
          </el-button>
          <el-button size="small" @click="cancelSmart">✗</el-button>
        </div>

        <!-- 画布左右切换图片 -->
        <div
          v-if="currentImage && images.length > 1"
          class="nav-arrow left"
          :class="{ disabled: currentIndex === 0 }"
          @click="prevImage"
        >
          <el-icon :size="18"><ArrowLeftBold /></el-icon>
        </div>
        <div
          v-if="currentImage && images.length > 1"
          class="nav-arrow right"
          :class="{ disabled: currentIndex >= images.length - 1 }"
          @click="nextImage"
        >
          <el-icon :size="18"><ArrowRightBold /></el-icon>
        </div>

        <!-- Vertical tool bar (Roboflow style) -->
        <div class="vertical-toolbar">
          <el-tooltip content="选择 / 移动 (V)" placement="left" :show-after="300">
            <div class="tool-btn" :class="{ active: currentTool === 'select' }" @click="currentTool = 'select'">
              <el-icon :size="17"><Pointer /></el-icon>
            </div>
          </el-tooltip>
          <el-tooltip content="智能框选 (D) — 画框圈住目标自动分割" placement="left" :show-after="300">
            <div class="tool-btn" :class="{ active: currentTool === 'smart-box' }" @click="selectTool('smart-box')">
              <el-icon :size="17"><Crop /></el-icon>
            </div>
          </el-tooltip>
          <el-tooltip content="智能点选 (S) — 点击加区域 / 右键减区域 / 双击确认" placement="left" :show-after="300">
            <div class="tool-btn" :class="{ active: currentTool === 'smart-point' }" @click="selectTool('smart-point')">
              <el-icon :size="17"><MagicStick /></el-icon>
            </div>
          </el-tooltip>
          <el-tooltip content="矩形框 (B) — 拖拽绘制" placement="left" :show-after="300">
            <div class="tool-btn" :class="{ active: currentTool === 'rectangle' }" @click="currentTool = 'rectangle'">
              <el-icon :size="17"><FullScreen /></el-icon>
            </div>
          </el-tooltip>
          <el-tooltip content="套索 (L) — 自由圈选区域" placement="left" :show-after="300">
            <div class="tool-btn" :class="{ active: currentTool === 'lasso' }" @click="currentTool = 'lasso'">
              <el-icon :size="17"><Aim /></el-icon>
            </div>
          </el-tooltip>
          <el-tooltip content="多边形 (P) — 点击描点，双击闭合" placement="left" :show-after="300">
            <div class="tool-btn" :class="{ active: currentTool === 'polygon' }" @click="currentTool = 'polygon'">
              <el-icon :size="17"><Edit /></el-icon>
            </div>
          </el-tooltip>
          <div class="tool-sep"></div>
          <el-tooltip content="删除选中 (Delete)" placement="left" :show-after="300">
            <div class="tool-btn danger" :class="{ disabled: !selectedAnno }" @click="deleteSelected">
              <el-icon :size="17"><Delete /></el-icon>
            </div>
          </el-tooltip>
          <el-tooltip content="清除全部标注" placement="left" :show-after="300">
            <div class="tool-btn danger" :class="{ disabled: annotations.length === 0 }" @click="clearAllAnnotations">
              <el-icon :size="17"><Broom /></el-icon>
            </div>
          </el-tooltip>
        </div>
      </div>

      <!-- Right: tools -->
      <aside class="tools-sidebar">
        <el-card shadow="never" header="标注列表" style="margin-top: 10px;">
          <div v-if="annotations.length === 0" class="panel-empty">在图片上拖拽绘制标注</div>
          <div v-else class="anno-list">
            <div
              v-for="(anno, idx) in annotations"
              :key="anno.id"
              class="anno-item"
              :class="{ active: selectedId === anno.id }"
              @click="selectedId = anno.id"
            >
              <span class="class-dot" :style="{ background: getClassColor(anno.class_name) }"></span>
              <el-select
                v-model="anno.class_name"
                size="small"
                class="anno-class-select"
                @change="(val) => changeAnnoClass(anno, val)"
                @click.stop
              >
                <el-option v-for="cls in project.classes" :key="cls" :label="cls" :value="cls" />
              </el-select>
              <span class="anno-size mono">
                {{ anno.anno_type === 'rectangle'
                  ? `${Math.round((anno.bbox?.w || 0) * imageWidth)}×${Math.round((anno.bbox?.h || 0) * imageHeight)}`
                  : `${anno.points?.length || 0}点` }}
              </span>
              <el-button type="danger" link size="small" @click.stop="removeAnnotation(idx)">删</el-button>
            </div>
          </div>
        </el-card>

        <el-card shadow="never" header="快捷键" style="margin-top: 10px;">
          <div class="shortcuts">
            <div><kbd>1</kbd>-<kbd>9</kbd> 切换类别</div>
            <div><kbd>R</kbd> 矩形 <kbd>L</kbd> 套索 <kbd>P</kbd> 多边形</div>
            <div><kbd>Ctrl+Z</kbd> / <kbd>Ctrl+Shift+Z</kbd> 撤销 / 重做</div>
            <div><kbd>Delete</kbd> 删除选中</div>
            <div><kbd>Ctrl+D</kbd> 复制选中</div>
            <div><kbd>←</kbd> <kbd>→</kbd> 切换图片</div>
            <div><kbd>双击</kbd> 完成多边形</div>
          </div>
        </el-card>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { projectApi, imageApi, annotationApi, aiApi } from '@/api'

const route = useRoute()
const projectId = computed(() => parseInt(route.params.id))

// Refs
const canvasAreaRef = ref(null)
const imageRef = ref(null)

// State
const images = ref([])
const currentIndex = ref(0)
const project = ref({})
const annotations = ref([])
const historyStack = ref([])
const redoStack = ref([])
const aiLoading = ref(false)
const smartLoading = ref(false)

// Tool state
const currentTool = ref('rectangle')
const selectedClass = ref('')
const zoom = ref(1)
const imageLoaded = ref(false)
const imageWidth = ref(640)
const imageHeight = ref(480)

// Selection & editing
const selectedId = ref(null)
const editing = ref(null) // {type:'move'|'resize'|'vertex', anno, handle?, dx?, dy?, orig?}

// Drawing state
const isDrawing = ref(false)
const startPos = ref(null)
const drawingRect = ref(null)
const polygonPoints = ref([])

// Lasso state
const lassoPoints = ref([])
const lassoDrawing = ref(false)
const LASSO_MIN_DIST = 0.004

// Smart point-prompt state
const smartPoints = ref([])    // [{x, y, positive}]
const smartPreview = ref(null) // 预览多边形（归一化点数组）
const smartDownPos = ref(null) // 区分点击/拖拽
const smartDragging = ref(false)
const smartSeq = ref(0)        // 请求序列号，防并发竞态

// SAM 模型状态（智能选框/点选依赖）
const samDownloaded = ref(true)
const samSizeMb = ref(375)
const samProgress = ref(null) // null=未开始下载, 0-100=下载中/完成
const samStarting = ref(false)
const samTimer = ref(null)

// 检查 SAM 模型状态
const checkSamStatus = async () => {
  try {
    const st = await aiApi.samStatus()
    samDownloaded.value = st.downloaded
    samSizeMb.value = st.size_mb || 375
  } catch (e) {}
}

const startSamDownload = async () => {
  samStarting.value = true
  try {
    const res = await aiApi.samDownload()
    ElMessage.info(res.message || '开始下载 SAM 模型')
    samProgress.value = 0
    // 轮询下载进度
    stopSamPolling()
    samTimer.value = setInterval(async () => {
      try {
        const st = await aiApi.samDownloadStatus()
        if (st.progress !== undefined) samProgress.value = Math.round(st.progress)
        if (st.status === 'done') {
          stopSamPolling()
          samDownloaded.value = true
          samProgress.value = 100
          ElMessage.success('SAM 模型下载完成，智能分割可用')
        } else if (st.status === 'error') {
          stopSamPolling()
          samProgress.value = null
          ElMessage.error(`SAM 下载失败: ${st.error || '未知错误'}`)
        }
      } catch (e) {
        stopSamPolling()
      }
    }, 1000)
  } catch (e) {
    // interceptor handles error
  } finally {
    samStarting.value = false
  }
}

const stopSamPolling = () => {
  if (samTimer.value) {
    clearInterval(samTimer.value)
    samTimer.value = null
  }
}

// 工具选择：智能工具需 SAM 已下载
const selectTool = (tool) => {
  if ((tool === 'smart-box' || tool === 'smart-point') && !samDownloaded.value) {
    ElMessage.warning('请先下载 SAM 模型后再使用智能分割')
    return
  }
  currentTool.value = tool
}

// Tags（图片级标签，会话内有效）
const imageTags = ref([])
const tagInput = ref('')

const fileName = computed(() => {
  const img = currentImage.value
  if (!img) return '-'
  return img.original_name || img.filename || '-'
})

const classInstanceCount = (cls) => {
  return annotations.value.filter(a => a.class_name === cls).length
}

// 已使用类别数 / 未使用类别（Roboflow Unused Classes）
const annotatedClassCount = computed(() => {
  const used = new Set(annotations.value.map(a => a.class_name))
  return used.size
})

const unusedClasses = computed(() => {
  const used = new Set(annotations.value.map(a => a.class_name))
  return (project.value.classes || []).filter(cls => !used.has(cls))
})

const addTag = () => {
  const t = tagInput.value.trim()
  if (t && !imageTags.value.includes(t)) imageTags.value.push(t)
  tagInput.value = ''
}

const removeTag = (t) => {
  imageTags.value = imageTags.value.filter(x => x !== t)
}

const selectedAnno = computed(() => annotations.value.find(a => a.id === selectedId.value) || null)

// Computed
const currentImage = computed(() => images.value[currentIndex.value])
const canUndo = computed(() => historyStack.value.length > 0)
const canRedo = computed(() => redoStack.value.length > 0)

// ─── Colors ──────────────────────────────────────────────
const CLASS_COLORS = ['#1f5aff', '#0f9d58', '#e6a23c', '#e5484d', '#7c3aed', '#0ea5e9', '#db2777', '#65a30d']

const getClassColor = (className) => {
  const classes = project.value.classes || []
  const idx = classes.indexOf(className)
  return CLASS_COLORS[idx >= 0 ? idx % CLASS_COLORS.length : hashCode(className) % CLASS_COLORS.length]
}

const classColorFill = (className) => {
  const c = getClassColor(className)
  // 半透明填充（Roboflow 风格）
  return `${c}26` // 15% alpha
}

const hashCode = (str) => {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i)
    hash |= 0
  }
  return Math.abs(hash)
}

const labelWidth = (name) => name.length * 7 + 8

// ─── Coordinate transforms ───────────────────────────────
const toDisplayX = (x) => x * imageWidth.value
const toDisplayY = (y) => y * imageHeight.value
const toDisplayW = (w) => w * imageWidth.value
const toDisplayH = (h) => h * imageHeight.value

const getPolygonPoints = (points) => {
  if (!points || !Array.isArray(points)) return ''
  return points.map(p => `${toDisplayX(p.x)},${toDisplayY(p.y)}`).join(' ')
}

const getLassoClosedPoints = () => {
  if (!lassoPoints.value.length) return ''
  const pts = [...lassoPoints.value, lassoPoints.value[0]]
  return pts.map(p => `${toDisplayX(p.x)},${toDisplayY(p.y)}`).join(' ')
}

const getSmartPreviewPoints = () => {
  if (!smartPreview.value || !smartPreview.value.length) return ''
  return smartPreview.value.map(p => `${toDisplayX(p.x)},${toDisplayY(p.y)}`).join(' ')
}

const rectHandles = (bbox) => {
  const { x, y, w, h } = bbox
  return [
    { key: 'nw', x, y },
    { key: 'n', x: x + w / 2, y },
    { key: 'ne', x: x + w, y },
    { key: 'e', x: x + w, y: y + h / 2 },
    { key: 'se', x: x + w, y: y + h },
    { key: 's', x: x + w / 2, y: y + h },
    { key: 'sw', x, y: y + h },
    { key: 'w', x, y: y + h / 2 },
  ]
}

const getImageUrl = (img) => img.file_path || ''

// ─── Data loading ────────────────────────────────────────
const loadProject = async () => {
  try {
    project.value = await projectApi.get(projectId.value)
    selectedClass.value = project.value.classes[0] || ''
  } catch (e) {}
}

const loadImages = async () => {
  try {
    images.value = await imageApi.list(projectId.value)
    // 从数据集页跳转：定位到指定图片（query.image = 图片 id）
    const targetId = parseInt(route.query.image)
    if (targetId && images.value.length) {
      const idx = images.value.findIndex(i => i.id === targetId)
      if (idx >= 0) currentIndex.value = idx
    }
  } catch (e) {}
}

const loadAnnotations = async () => {
  if (!currentImage.value) return
  try {
    annotations.value = await annotationApi.list(currentImage.value.id)
    selectedId.value = null
  } catch (e) {}
}

// Navigation
const prevImage = () => { if (currentIndex.value > 0) currentIndex.value-- }
const nextImage = () => { if (currentIndex.value < images.value.length - 1) currentIndex.value++ }
const goToImage = (idx) => { currentIndex.value = idx }

const fitZoom = () => {
  const img = imageRef.value
  if (!img) return
  const area = canvasAreaRef.value
  if (!area) return
  const availW = area.clientWidth - 40
  const availH = area.clientHeight - 40
  zoom.value = Math.min(1, Math.min(availW / img.naturalWidth, availH / img.naturalHeight))
}

// ─── Undo/Redo ───────────────────────────────────────────
const undo = async () => {
  if (!canUndo.value) return
  const prev = historyStack.value.pop()
  redoStack.value.push([...annotations.value])
  annotations.value = prev
  selectedId.value = null
  await syncAnnotations()
}

const redo = async () => {
  if (!canRedo.value) return
  const next = redoStack.value.pop()
  historyStack.value.push([...annotations.value])
  annotations.value = next
  selectedId.value = null
  await syncAnnotations()
}

const pushHistory = () => {
  historyStack.value.push(annotations.value.map(a => ({ ...a })))
  redoStack.value = []
  if (historyStack.value.length > 50) historyStack.value.shift()
}

const popHistory = () => {
  if (historyStack.value.length) historyStack.value.pop()
}

// ─── Hit testing ─────────────────────────────────────────
const pointInRect = (pos, bbox) => (
  pos.x >= bbox.x && pos.x <= bbox.x + bbox.w &&
  pos.y >= bbox.y && pos.y <= bbox.y + bbox.h
)

const pointInPolygon = (pos, pts) => {
  let inside = false
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const xi = pts[i].x, yi = pts[i].y
    const xj = pts[j].x, yj = pts[j].y
    if (((yi > pos.y) !== (yj > pos.y)) && (pos.x < (xj - xi) * (pos.y - yi) / (yj - yi) + xi)) {
      inside = !inside
    }
  }
  return inside
}

const hitTest = (pos) => {
  // 从上层往下找（后画的在上）
  for (let i = annotations.value.length - 1; i >= 0; i--) {
    const anno = annotations.value[i]
    if (anno.anno_type === 'rectangle' && anno.bbox && pointInRect(pos, anno.bbox)) return anno
    if (anno.anno_type === 'polygon' && anno.points && anno.points.length >= 3 && pointInPolygon(pos, anno.points)) return anno
  }
  return null
}

const handleHitHandle = (pos, anno) => {
  if (anno.anno_type !== 'rectangle' || !anno.bbox) return null
  const b = anno.bbox
  const MARGIN = 0.02
  const near = (v, t) => Math.abs(v - t) <= MARGIN
  const { x, y, w, h } = b
  if (near(pos.x, x) && near(pos.y, y)) return 'nw'
  if (near(pos.x, x + w) && near(pos.y, y)) return 'ne'
  if (near(pos.x, x + w) && near(pos.y, y + h)) return 'se'
  if (near(pos.x, x) && near(pos.y, y + h)) return 'sw'
  if (near(pos.y, y) && pos.x > x && pos.x < x + w) return 'n'
  if (near(pos.y, y + h) && pos.x > x && pos.x < x + w) return 's'
  if (near(pos.x, x) && pos.y > y && pos.y < y + h) return 'w'
  if (near(pos.x, x + w) && pos.y > y && pos.y < y + h) return 'e'
  return null
}

// ─── Mouse handlers ──────────────────────────────────────
const getImageCoords = (e) => {
  const img = imageRef.value
  if (!img) return null
  const rect = img.getBoundingClientRect()
  return {
    x: Math.min(Math.max((e.clientX - rect.left) / rect.width, 0), 1),
    y: Math.min(Math.max((e.clientY - rect.top) / rect.height, 0), 1),
  }
}

const handleMouseDown = (e) => {
  const pos = getImageCoords(e)
  if (!pos) return

  // 1. 已有选中 → 检测手柄（resize）
  if (selectedId.value) {
    const sel = selectedAnno.value
    if (sel) {
      const handle = handleHitHandle(pos, sel)
      if (handle) {
        editing.value = { type: 'resize', anno: sel, handle, orig: { ...sel.bbox } }
        return
      }
    }
  }

  // 2. 命中已有标注 → 选中并准备移动（智能点选除外：始终加点）
  const hit = hitTest(pos)
  if (hit && currentTool.value !== 'polygon' && currentTool.value !== 'smart-point') {
    selectedId.value = hit.id
    if (hit.anno_type === 'rectangle' && hit.bbox) {
      editing.value = {
        type: 'move', anno: hit, dx: pos.x - hit.bbox.x, dy: pos.y - hit.bbox.y,
        orig: { ...hit.bbox },
      }
    }
    return
  }
  // 多边形工具：命中标注也选中（不绘制）
  if (hit && currentTool.value === 'polygon') {
    selectedId.value = hit.id
    return
  }

  // 3. 未命中 → 取消选中，开始绘制
  selectedId.value = null

  // select 工具：只选择/移动，不绘制
  if (currentTool.value === 'select') return

  if (currentTool.value === 'lasso') {
    lassoPoints.value = [pos]
    lassoDrawing.value = true
    isDrawing.value = true
    return
  }
  if (currentTool.value === 'polygon') {
    polygonPoints.value.push(pos)
    return
  }
  if (currentTool.value === 'smart-point') {
    // 右键由 contextmenu 单独处理（加 negative 点）
    if (e.button === 2) return
    // 记录按下位置，区分「点击加提示点」与「拖拽画框」
    smartDownPos.value = pos
    smartDragging.value = false
    startPos.value = pos
    return
  }
  if (currentTool.value === 'smart-box') {
    // 画框式智能分割
    isDrawing.value = true
    startPos.value = pos
    return
  }
  if (currentTool.value === 'rectangle') {
    isDrawing.value = true
    startPos.value = pos
  }
}

const handleMouseMove = (e) => {
  const pos = getImageCoords(e)
  if (!pos) return

  // 编辑移动
  if (editing.value?.type === 'move' && editing.value.anno.anno_type === 'rectangle') {
    const { anno, dx, dy } = editing.value
    anno.bbox.x = clamp01(pos.x - dx)
    anno.bbox.y = clamp01(pos.y - dy)
    return
  }

  // 编辑缩放
  if (editing.value?.type === 'resize') {
    const { anno, handle, orig } = editing.value
    const b = orig
    let { x, y, w, h } = b
    if (handle.includes('e')) w = clamp01(pos.x - x)
    if (handle.includes('s')) h = clamp01(pos.y - y)
    if (handle.includes('w')) { const nx = clamp01(pos.x); w = clamp01(x + w - nx); x = nx }
    if (handle.includes('n')) { const ny = clamp01(pos.y); h = clamp01(y + h - ny); y = ny }
    if (w < 0.01) w = 0.01
    if (h < 0.01) h = 0.01
    anno.bbox = { x: clamp01(x), y: clamp01(y), w, h }
    return
  }

  // 编辑多边形顶点
  if (editing.value?.type === 'vertex') {
    const { anno, vi } = editing.value
    if (anno.points && anno.points[vi]) {
      anno.points[vi] = { x: clamp01(pos.x), y: clamp01(pos.y) }
    }
    return
  }

  // 套索轨迹
  if (lassoDrawing.value) {
    const last = lassoPoints.value[lassoPoints.value.length - 1]
    const dx = pos.x - last.x
    const dy = pos.y - last.y
    if (Math.sqrt(dx * dx + dy * dy) >= LASSO_MIN_DIST) lassoPoints.value.push(pos)
    return
  }

  // 智能点选：拖拽检测（移动超阈值进入画框模式）
  if (currentTool.value === 'smart-point' && smartDownPos.value && !smartDragging.value) {
    const dx = pos.x - smartDownPos.value.x
    const dy = pos.y - smartDownPos.value.y
    if (Math.sqrt(dx * dx + dy * dy) > 0.01) {
      smartDragging.value = true
      isDrawing.value = true
    }
  }

  // 矩形/智能框选绘制
  if (isDrawing.value && (currentTool.value === 'rectangle' || currentTool.value === 'smart-box' || (currentTool.value === 'smart-point' && smartDragging.value))) {
    if (!startPos.value) return
    drawingRect.value = {
      x: Math.min(startPos.value.x, pos.x),
      y: Math.min(startPos.value.y, pos.y),
      w: Math.abs(pos.x - startPos.value.x),
      h: Math.abs(pos.y - startPos.value.y),
    }
  }
}

const clamp01 = (v) => Math.min(Math.max(v, 0), 1)

const handleMouseUp = async () => {
  // 编辑结束：保存
  if (editing.value) {
    const { anno, type } = editing.value
    editing.value = null
    if (type === 'move' && anno.anno_type === 'rectangle' && anno.bbox) {
      const b = anno.bbox
      if (b.w < 0.005 || b.h < 0.005) { selectedId.value = null; return }
      await updateAnno(anno)
    } else if (type === 'resize') {
      await updateAnno(anno)
    } else if (type === 'vertex') {
      await updateAnno(anno)
    }
    return
  }

  // 套索闭合
  if (lassoDrawing.value) {
    lassoDrawing.value = false
    isDrawing.value = false
    await finishLasso()
    return
  }

  // 智能点选：点击（非拖拽）→ 添加 positive 提示点
  if (currentTool.value === 'smart-point' && smartDownPos.value && !smartDragging.value) {
    const clickPos = smartDownPos.value
    smartDownPos.value = null
    await addSmartPoint(true, clickPos)
    return
  }

  // 矩形/智能框选绘制结束
  if (isDrawing.value && (currentTool.value === 'rectangle' || currentTool.value === 'smart-box')) {
    if (!drawingRect.value) { resetDrawing(); return }
    if (drawingRect.value.w < 0.01 || drawingRect.value.h < 0.01) { resetDrawing(); return }

    if (currentTool.value === 'smart-box') {
      // 智能框选：SAM 分割生成多边形标注
      pushHistory()
      smartLoading.value = true
      try {
        const res = await aiApi.smartSelect(projectId.value, {
          image_id: currentImage.value.id,
          class_name: selectedClass.value,
          prompt_type: 'box',
          bbox: drawingRect.value,
        })
        if (res.success && res.annotation) {
          annotations.value.push(res.annotation)
          selectedId.value = res.annotation.id
          ElMessage.success(res.message || '智能分割完成')
        } else {
          ElMessage.warning(res.message || '未分割出目标')
          popHistory()
        }
      } catch (e) {
        popHistory()
      } finally {
        smartLoading.value = false
      }
      resetDrawing()
      return
    }

    pushHistory()
    const newAnno = await annotationApi.create({
      image_id: currentImage.value.id,
      anno_type: 'rectangle',
      class_name: selectedClass.value,
      bbox: drawingRect.value,
    })
    annotations.value.push(newAnno)
    selectedId.value = newAnno.id
    resetDrawing()
  }
}

// ─── Smart 点击式：加/减区域提示点 ────────────────────────
// 交互规则（对齐 Roboflow Smart Select）：
//   左键点击 = 始终加区域（positive 点，多点联动扩大区域）
//   右键点击 = 始终排除区域（negative 点）
const addSmartPoint = async (positive, posOverride) => {
  const pos = posOverride || smartDownPos.value
  if (!pos || !currentImage.value) return
  smartPoints.value.push({ x: pos.x, y: pos.y, positive })
  await runSmartSegment()
}

const runSmartSegment = async () => {
  if (!smartPoints.value.length || !currentImage.value) return
  smartLoading.value = true
  const seq = ++smartSeq.value
  try {
    const res = await aiApi.smartSelect(projectId.value, {
      image_id: currentImage.value.id,
      class_name: selectedClass.value,
      prompt_type: 'point',
      points: smartPoints.value,
      preview: true, // 预览模式：不写库，确认后才保存
    })
    // 只应用最新一次请求的结果（防止快速点击时旧响应覆盖新响应）
    if (seq !== smartSeq.value) return
    if (res.success && res.points) {
      smartPreview.value = res.points
    } else {
      smartPreview.value = null
    }
  } catch (e) {
    if (seq === smartSeq.value) smartPreview.value = null
  } finally {
    if (seq === smartSeq.value) smartLoading.value = false
  }
}

// 右键：添加 negative 提示点（减区域）
const handleRightClick = async (e) => {
  if (currentTool.value !== 'smart-point') return
  const pos = getImageCoords(e)
  if (!pos) return
  smartPoints.value.push({ x: pos.x, y: pos.y, positive: false })
  await runSmartSegment()
}

// 双击：确认保存当前预览为标注
const confirmSmart = async () => {
  if (currentTool.value !== 'smart-point') return
  if (!smartPreview.value || smartPreview.value.length < 3) return
  pushHistory()
  try {
    const newAnno = await annotationApi.create({
      image_id: currentImage.value.id,
      anno_type: 'polygon',
      class_name: selectedClass.value,
      points: smartPreview.value,
    })
    annotations.value.push(newAnno)
    selectedId.value = newAnno.id
    ElMessage.success(`已确认保存（${smartPoints.value.length} 个提示点）`)
  } catch (e) {
    popHistory()
  }
  smartPoints.value = []
  smartPreview.value = null
}

// 取消智能会话
const cancelSmart = () => {
  smartPoints.value = []
  smartPreview.value = null
  smartDownPos.value = null
  smartDragging.value = false
}

const positiveCount = computed(() => smartPoints.value.filter(p => p.positive).length)
const negativeCount = computed(() => smartPoints.value.filter(p => !p.positive).length)

const handleMouseLeave = async () => {
  if (editing.value) {
    const { anno } = editing.value
    editing.value = null
    await updateAnno(anno)
  }
  if (lassoDrawing.value) {
    lassoDrawing.value = false
    isDrawing.value = false
    await finishLasso()
  }
  resetDrawing()
}

const resetDrawing = () => {
  isDrawing.value = false
  startPos.value = null
  drawingRect.value = null
}

const startResize = (anno, handle) => {
  editing.value = { type: 'resize', anno, handle, orig: { ...anno.bbox } }
}

const startVertexDrag = (anno, vi) => {
  editing.value = { type: 'vertex', anno, vi }
}

// 更新标注到后端
const updateAnno = async (anno) => {
  try {
    if (anno.anno_type === 'rectangle') {
      await annotationApi.update(anno.id, { bbox: anno.bbox })
    } else {
      await annotationApi.update(anno.id, { points: anno.points })
    }
  } catch (e) {}
}

const handleDoubleClick = async () => {
  // 智能点选：双击不确认保存（用浮动按钮，防快速多点误触）
  if (currentTool.value === 'smart-point') return
  if (currentTool.value !== 'polygon' || polygonPoints.value.length < 3) return
  pushHistory()
  const newAnno = await annotationApi.create({
    image_id: currentImage.value.id,
    anno_type: 'polygon',
    class_name: selectedClass.value,
    points: polygonPoints.value,
  })
  annotations.value.push(newAnno)
  selectedId.value = newAnno.id
  polygonPoints.value = []
}

// ─── Lasso 闭合保存 ──────────────────────────────────────
const finishLasso = async () => {
  const pts = lassoPoints.value
  lassoPoints.value = []
  if (!currentImage.value || pts.length < 3) return
  const xs = pts.map(p => p.x)
  const ys = pts.map(p => p.y)
  const w = Math.max(...xs) - Math.min(...xs)
  const h = Math.max(...ys) - Math.min(...ys)
  if (w < 0.01 || h < 0.01) return
  pushHistory()
  if (project.value.anno_type === 'polygon') {
    const newAnno = await annotationApi.create({
      image_id: currentImage.value.id, anno_type: 'polygon', class_name: selectedClass.value, points: pts,
    })
    annotations.value.push(newAnno)
    selectedId.value = newAnno.id
  } else {
    const newAnno = await annotationApi.create({
      image_id: currentImage.value.id, anno_type: 'rectangle', class_name: selectedClass.value,
      bbox: { x: Math.min(...xs), y: Math.min(...ys), w, h },
    })
    annotations.value.push(newAnno)
    selectedId.value = newAnno.id
  }
}

// ─── Actions ─────────────────────────────────────────────
const removeAnnotation = async (idx) => {
  pushHistory()
  const anno = annotations.value[idx]
  await annotationApi.delete(anno.id)
  annotations.value.splice(idx, 1)
  if (selectedId.value === anno.id) selectedId.value = null
}

const deleteSelected = async () => {
  if (!selectedAnno.value) return
  const idx = annotations.value.findIndex(a => a.id === selectedId.value)
  if (idx >= 0) await removeAnnotation(idx)
}

const duplicateSelected = async () => {
  const anno = selectedAnno.value
  if (!anno) return
  pushHistory()
  const data = { image_id: currentImage.value.id, class_name: anno.class_name }
  if (anno.anno_type === 'rectangle' && anno.bbox) {
    const b = anno.bbox
    const off = 0.02
    data.anno_type = 'rectangle'
    data.bbox = {
      x: clamp01(b.x + off), y: clamp01(b.y + off),
      w: Math.min(b.w, 1 - b.x - off), h: Math.min(b.h, 1 - b.y - off),
    }
  } else {
    data.anno_type = 'polygon'
    data.points = anno.points.map(p => ({ x: clamp01(p.x + 0.02), y: clamp01(p.y + 0.02) }))
  }
  const newAnno = await annotationApi.create(data)
  annotations.value.push(newAnno)
  selectedId.value = newAnno.id
}

const clearAllAnnotations = async () => {
  if (!confirm(`确定清除当前 ${annotations.value.length} 个标注吗？`)) return
  pushHistory()
  await annotationApi.clearAll(currentImage.value.id)
  annotations.value = []
  selectedId.value = null
}

// 修改标注类别（标注列表下拉）
const changeAnnoClass = async (anno, newClass) => {
  if (!newClass || newClass === anno.class_name) return
  pushHistory()
  const old = anno.class_name
  anno.class_name = newClass
  try {
    await annotationApi.update(anno.id, {
      image_id: currentImage.value.id,
      anno_type: anno.anno_type,
      class_name: newClass,
      bbox: anno.bbox || null,
      points: anno.points || null,
    })
  } catch (e) {
    anno.class_name = old
    popHistory()
  }
}

const autoAnnotate = async () => {
  if (!currentImage.value) return
  pushHistory()
  aiLoading.value = true
  try {
    const res = await aiApi.annotate(projectId.value, {
      image_id: currentImage.value.id, model_id: 'yolov8s', conf: 0.25,
    })
    if (!res.success) {
      ElMessage.error(res.message || 'AI 辅助标注失败')
      popHistory()
      return
    }
    annotations.value.push(...res.created)
    ElMessage.success(res.message || `AI 检测到 ${res.detections.length} 个目标`)
  } catch (e) {
    popHistory()
  } finally {
    aiLoading.value = false
  }
}

const syncAnnotations = async () => {
  if (!currentImage.value) return
  try {
    await annotationApi.clearAll(currentImage.value.id)
    for (const anno of annotations.value) {
      await annotationApi.create({ image_id: currentImage.value.id, ...anno })
    }
  } catch (e) {}
}

// 标注增删后实时同步缩略图角标计数
watch(annotations, () => {
  if (currentImage.value) {
    currentImage.value.annotation_count = annotations.value.length
  }
}, { deep: true })

// Image load handler
watch(currentImage, async () => {
  annotations.value = []
  polygonPoints.value = []
  lassoPoints.value = []
  lassoDrawing.value = false
  selectedId.value = null
  editing.value = null
  imageTags.value = []
  cancelSmart()
  imageLoaded.value = false

  if (currentImage.value) {
    await loadAnnotations()
    await nextTick()
    const img = imageRef.value
    if (img) {
      const onLoad = () => {
        imageWidth.value = img.clientWidth
        imageHeight.value = img.clientHeight
        imageLoaded.value = true
      }
      if (img.complete) onLoad()
      else img.onload = onLoad
    }
  }
}, { immediate: true })

// ─── Keyboard shortcuts ──────────────────────────────────
const handleKeydown = (e) => {
  if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return

  // 数字键切换类别
  if (/^[1-9]$/.test(e.key)) {
    const cls = (project.value.classes || [])[parseInt(e.key) - 1]
    if (cls) { selectedClass.value = cls; return }
  }

  switch (e.key) {
    case 'ArrowLeft': e.preventDefault(); prevImage(); break
    case 'ArrowRight': e.preventDefault(); nextImage(); break
    case 'v': case 'V': currentTool.value = 'select'; break
    case 's': case 'S': selectTool('smart-point'); break
    case 'b': case 'B': case 'r': case 'R': currentTool.value = 'rectangle'; break
    case 'l': case 'L': currentTool.value = 'lasso'; break
    case 'p': case 'P': currentTool.value = 'polygon'; break
    case 'z':
      if (e.ctrlKey || e.metaKey) { e.preventDefault(); undo() }
      break
    case 'Z':
      if (e.ctrlKey && e.shiftKey) { e.preventDefault(); redo() }
      break
    case 'd':
    case 'D':
      if (e.ctrlKey || e.metaKey) { e.preventDefault(); duplicateSelected() }
      else { selectTool('smart-box') }
      break
    case 'Delete':
    case 'Backspace':
      if (selectedAnno.value) { e.preventDefault(); deleteSelected() }
      break
    case 'Escape':
      selectedId.value = null
      polygonPoints.value = []
      cancelSmart()
      break
    case 'Enter':
      // 智能点选：回车 = 确认保存
      if (currentTool.value === 'smart-point' && smartPreview.value && smartPoints.value.length) {
        e.preventDefault()
        confirmSmart()
      }
      break
  }
}

onMounted(() => {
  loadProject()
  loadImages()
  checkSamStatus()
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  stopSamPolling()
})
</script>

<style lang="scss" scoped>
.annotate-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 104px);

  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0 12px;

    .toolbar-left, .toolbar-center, .toolbar-right {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .breadcrumb {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      padding: 0 4px;

      .crumb-project {
        color: var(--text-2);
        font-weight: 500;
      }

      .crumb-sep {
        color: var(--text-faint);
      }

      .crumb-page {
        color: var(--text-1);
        font-weight: 700;
        letter-spacing: 0.5px;
      }

      .crumb-file {
        color: var(--text-3);
        max-width: 200px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }

    .image-counter {
      font-size: 12px;
      color: var(--text-2);
      background: var(--bg-fill);
      padding: 3px 10px;
      border-radius: 3px;
    }

    .img-meta {
      font-size: 12px;
      color: var(--text-3);
    }
  }

  .annotate-content {
    display: flex;
    gap: 12px;
    flex: 1;
    min-height: 0;
  }

  // ─── 缩略图横条 ────────────────────────────
  .film-strip {
    display: flex;
    gap: 6px;
    overflow-x: auto;
    padding: 8px 4px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 4px;
    margin-bottom: 12px;
    flex: 0 0 auto;

    // 暗黑下缩略图底更贴近卡片
    html.dark & { background: var(--bg-fill); }

    .strip-item {
      position: relative;
      width: 64px;
      height: 48px;
      flex: 0 0 64px;
      border: 2px solid transparent;
      border-radius: 3px;
      cursor: pointer;
      overflow: hidden;

      img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }

      &.active {
        border-color: #1f5aff;
      }

      .strip-badge {
        position: absolute;
        right: 1px;
        bottom: 1px;
        background: rgba(0, 0, 0, 0.7);
        color: #fff;
        font-size: 9px;
        padding: 0 3px;
        border-radius: 2px;
      }
    }
  }

  // ─── 左侧属性面板 ────────────────────────────
  .image-panel {
    width: 200px;
    flex: 0 0 200px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 4px;
    overflow-y: auto;
    padding-bottom: 8px;

    .panel-section {
      padding: 12px;
      border-bottom: 1px solid var(--border);

      .panel-title {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.8px;
        color: var(--text-2);
        margin-bottom: 8px;
      }

      .anno-summary {
        display: flex;
        gap: 6px;

        .summary-item {
          flex: 1;
          text-align: center;
          background: var(--bg-fill);
          border: 1px solid var(--border-light);
          border-radius: 4px;
          padding: 6px 0;

          .summary-num {
            display: block;
            font-size: 16px;
            font-weight: 700;
            color: var(--text-1);
          }

          .summary-label {
            font-size: 10px;
            color: var(--text-3);
          }
        }
      }

      .unused-classes {
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px dashed var(--border);

        .unused-title {
          font-size: 11px;
          color: var(--text-3);
          margin-bottom: 5px;
        }

        .unused-item {
          display: flex;
          align-items: center;
          gap: 7px;
          padding: 4px 6px;
          border-radius: 3px;
          cursor: pointer;
          font-size: 12px;
          color: var(--text-3);

          &:hover { background: var(--bg-fill); color: var(--text-1); }

          .class-name { flex: 1; }

          kbd {
            font-size: 10px;
            color: var(--text-faint);
            background: var(--bg-fill);
            border: 1px solid var(--border);
            border-radius: 3px;
            padding: 0 4px;
            font-family: inherit;
          }
        }
      }

      .img-info {
        display: flex;
        flex-direction: column;
        gap: 5px;

        .info-row {
          display: flex;
          justify-content: space-between;
          gap: 8px;
          font-size: 12px;

          .info-label { color: var(--text-3); flex: 0 0 auto; }
          .info-value {
            color: var(--text-1);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
        }
      }

      .class-buttons {
        display: flex;
        flex-direction: column;
        gap: 5px;

        .class-btn {
          display: flex;
          align-items: center;
          gap: 7px;
          padding: 5px 8px;
          border: 1px solid var(--border);
          border-radius: 4px;
          cursor: pointer;
          font-size: 12px;
          transition: border-color 0.15s;

          &:hover { border-color: #b8c7ff; }
          &.active { background: var(--brand-soft); }

          .class-dot {
            width: 10px;
            height: 10px;
            border-radius: 2px;
            flex: 0 0 auto;
          }

          .class-name { flex: 1; color: var(--text-1); }
          .class-count { color: var(--text-3); font-size: 11px; }

          kbd {
            font-size: 10px;
            color: var(--text-3);
            background: var(--bg-fill);
            border: 1px solid var(--border);
            border-radius: 3px;
            padding: 0 4px;
            font-family: inherit;
          }
        }
      }

      .tag-box {
        .no-tags {
          font-size: 12px;
          color: var(--text-faint);
          margin-bottom: 8px;
        }

        .tag-list {
          display: flex;
          flex-wrap: wrap;
          gap: 4px;
          margin-bottom: 8px;
        }

        .tag-add {
          display: flex;
          gap: 6px;

          .el-input { flex: 1; }
        }
      }
    }

    .panel-empty {
      padding: 14px 0;
      text-align: center;
      color: var(--text-faint);
      font-size: 12px;
    }
  }

  // ─── 画布 ────────────────────────────────────
  .canvas-area {
    flex: 1;
    position: relative;
    background: #14161a;
    border-radius: 4px;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;

    .canvas-wrapper {
      position: relative;
      transform-origin: top left;

      .annotation-image {
        max-width: 100%;
        max-height: calc(100vh - 240px);
        object-fit: contain;
        display: block;
        user-select: none;
        cursor: crosshair;
      }

      .overlay-svg {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;

        .anno-shape {
          pointer-events: none;
        }

        .anno-shape g[data-handle] {
          pointer-events: auto;
        }
      }
    }

    .zoom-controls {
      position: absolute;
      bottom: 12px;
      left: 50%;
      transform: translateX(-50%);
      background: rgba(20, 22, 26, 0.72);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 5px;
      padding: 3px;
      backdrop-filter: blur(4px);

      :deep(.el-button) {
        background: transparent;
        border-color: transparent;
        color: #d5d9e0;

        &:hover {
          background: rgba(255, 255, 255, 0.14);
          color: #fff;
        }
      }

      .zoom-pct {
        min-width: 56px;
        text-align: center;
      }
    }

    // ─── 画布左右切换按钮 ───
    .nav-arrow {
      position: absolute;
      top: 50%;
      transform: translateY(-50%);
      width: 34px;
      height: 56px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(28, 30, 36, 0.55);
      color: #e8eaed;
      border-radius: 4px;
      cursor: pointer;
      z-index: 10;
      transition: background 0.15s;

      &:hover {
        background: rgba(31, 90, 255, 0.75);
      }

      &.disabled {
        opacity: 0.3;
        cursor: not-allowed;

        &:hover { background: rgba(28, 30, 36, 0.55); }
      }

      &.left { left: 8px; }
      &.right { right: 58px; } // 避开右侧垂直工具条
    }

    // ─── SAM 下载提示条 ───
    .sam-download-bar {
      position: absolute;
      top: 12px;
      left: 50%;
      transform: translateX(-50%);
      display: flex;
      align-items: center;
      gap: 10px;
      background: rgba(229, 72, 77, 0.95);
      color: #fff;
      border-radius: 5px;
      padding: 8px 16px;
      font-size: 13px;
      z-index: 20;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
      white-space: nowrap;

      .sam-progress {
        display: flex;
        align-items: center;
        gap: 8px;
        width: 200px;
      }

      .sam-pct {
        font-size: 12px;
        min-width: 36px;
      }
    }

    // ─── 智能会话提示条 ───
    .smart-hint {
      position: absolute;
      top: 12px;
      left: 12px;
      display: flex;
      align-items: center;
      gap: 10px;
      background: rgba(28, 30, 36, 0.92);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 4px;
      padding: 6px 12px;
      font-size: 12px;
      z-index: 10;

      .hint-pos { color: #0f9d58; font-weight: 600; }
      .hint-neg { color: #e5484d; font-weight: 600; }
      .hint-action { color: var(--text-3); }
    }

    // ─── 垂直工具条（Roboflow 风格）───
    .vertical-toolbar {
      position: absolute;
      right: 12px;
      top: 50%;
      transform: translateY(-50%);
      display: flex;
      flex-direction: column;
      gap: 4px;
      background: rgba(28, 30, 36, 0.92);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 6px;
      padding: 6px 4px;
      z-index: 10;

      .tool-btn {
        width: 34px;
        height: 34px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 4px;
        color: #b8bdc7;
        cursor: pointer;
        transition: background 0.12s, color 0.12s;

        &:hover {
          background: rgba(255, 255, 255, 0.1);
          color: #fff;
        }

        &.active {
          background: #1f5aff;
          color: #fff;
        }

        &.danger:hover {
          background: rgba(229, 72, 77, 0.25);
          color: #ff7875;
        }

        &.disabled {
          opacity: 0.35;
          cursor: not-allowed;

          &:hover {
            background: transparent;
            color: #b8bdc7;
          }
        }
      }

      .tool-sep {
        height: 1px;
        background: rgba(255, 255, 255, 0.12);
        margin: 3px 2px;
      }
    }
  }

  // ─── 右侧工具面板 ────────────────────────────
  .tools-sidebar {
    width: 236px;
    flex: 0 0 236px;
    overflow-y: auto;

    .tool-radio {
      display: flex;
      width: 100%;

      .el-radio-button {
        flex: 1;

        .el-radio-button__inner {
          padding: 6px 0;
          font-size: 12px;

          .el-icon { margin-right: 2px; }
        }
      }
    }

    .tool-tip {
      margin-top: 8px;
      font-size: 11px;
      color: var(--text-3);
      line-height: 1.5;
    }

    .anno-list {
      max-height: 240px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 4px;

      .anno-item {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 5px 6px;
        border: 1px solid transparent;
        border-radius: 3px;
        cursor: pointer;
        font-size: 12px;

        &:hover { background: var(--bg-fill); }
        &.active { border-color: #1f5aff; background: var(--brand-soft); }

        .class-dot {
          width: 8px;
          height: 8px;
          border-radius: 2px;
          flex: 0 0 auto;
        }

        .anno-class-select {
          flex: 1;
          min-width: 0;

          :deep(.el-select__wrapper) {
            min-height: 22px;
            padding: 0 8px;
            box-shadow: none;
            background: transparent;
          }
        }

        .anno-size { color: var(--text-3); font-size: 11px; flex: 0 0 auto; }
      }
    }

    .shortcuts {
      display: flex;
      flex-direction: column;
      gap: 5px;
      font-size: 12px;
      color: var(--text-2);

      kbd {
        display: inline-block;
        font-size: 10px;
        color: var(--text-2);
        background: var(--bg-fill);
        border: 1px solid var(--border);
        border-radius: 3px;
        padding: 0 5px;
        font-family: inherit;
      }
    }

    .panel-empty {
      padding: 14px 0;
      text-align: center;
      color: var(--text-faint);
      font-size: 12px;
    }
  }
}
</style>
