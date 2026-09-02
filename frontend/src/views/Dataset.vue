<template>
  <div class="dataset-page">
    <div class="page-head">
      <div>
        <div class="page-title">数据集</div>
        <div class="page-sub">{{ project.name || '工程' }} · 管理图片、标注类别与数据集划分</div>
      </div>
      <el-button type="primary" @click="$router.push(`/project/${projectId}/annotate`)" :disabled="images.length === 0">
        <el-icon style="margin-right: 5px;"><EditPen /></el-icon>
        开始标注
      </el-button>
    </div>

    <!-- 统计条 -->
    <div class="stats-bar">
      <div class="stat-cell">
        <span class="stat-num mono">{{ images.length }}</span>
        <span class="stat-label">图片总数</span>
      </div>
      <div class="stat-cell">
        <span class="stat-num mono" style="color: #1f5aff;">{{ splitCounts.train }}</span>
        <span class="stat-label">训练集</span>
      </div>
      <div class="stat-cell">
        <span class="stat-num mono" style="color: #e6a23c;">{{ splitCounts.val }}</span>
        <span class="stat-label">验证集</span>
      </div>
      <div class="stat-cell">
        <span class="stat-num mono" style="color: #0f9d58;">{{ splitCounts.test }}</span>
        <span class="stat-label">测试集</span>
      </div>
      <div class="stat-cell">
        <span class="stat-num mono" style="color: #7c3aed;">{{ annotatedCount }}</span>
        <span class="stat-label">已标注</span>
      </div>
      <div class="stat-cell" style="border-right: none;">
        <span class="stat-num mono">{{ project.classes?.length || 0 }}</span>
        <span class="stat-label">类别</span>
      </div>
    </div>

    <div class="dataset-layout">
      <!-- 左侧：图片网格 -->
      <div class="grid-panel">
        <!-- 筛选 tabs -->
        <div class="filter-tabs">
          <div
            v-for="tab in tabs"
            :key="tab.value"
            class="tab"
            :class="{ active: filterTab === tab.value }"
            @click="filterTab = tab.value"
          >
            {{ tab.label }}
            <span class="tab-count mono">{{ tabCount(tab.value) }}</span>
          </div>
        </div>

        <!-- 标注状态筛选 -->
        <div class="anno-filter">
          <div
            v-for="f in annoFilters"
            :key="f.value"
            class="tab"
            :class="{ active: annoFilter === f.value }"
            @click="annoFilter = f.value"
          >
            {{ f.label }}
            <span class="tab-count mono">{{ annoFilterCount(f.value) }}</span>
          </div>
        </div>

        <!-- 图片网格 -->
        <div v-loading="loading" class="image-grid">
          <div
            v-for="img in pagedImages"
            :key="img.id"
            class="img-card"
            @click="goAnnotate(img.id)"
          >
            <!-- 划分色条 -->
            <div class="split-bar" :class="img.split"></div>
            <div class="img-wrap">
              <el-image
                :src="img.file_path"
                :preview-src-list="[img.file_path]"
                fit="cover"
                preview-teleported
                class="thumb"
              />
              <!-- 标注状态角标 -->
              <span
                class="anno-badge"
                :class="img.annotation_count > 0 ? 'done' : 'none'"
              >
                <el-icon :size="10"><Check v-if="img.annotation_count > 0" /></el-icon>
                {{ img.annotation_count > 0 ? `${img.annotation_count} 标注` : '未标注' }}
              </span>
            </div>
            <div class="img-info">
              <span class="img-name" :title="img.original_name">{{ img.original_name }}</span>
              <span class="img-meta mono" :class="img.annotation_count > 0 ? 'anno-done' : 'anno-none'">
                {{ img.annotation_count > 0 ? `已标注 ${img.annotation_count} 个` : '未标注' }}
              </span>
              <div class="img-opts">
                <el-button type="primary" size="small" @click.stop="goAnnotate(img.id)">标注</el-button>
                <el-popconfirm title="删除此图片？" width="180" @confirm="deleteImage(img.id)">
                  <template #reference>
                    <el-button size="small" type="danger" plain @click.stop>删除</el-button>
                  </template>
                </el-popconfirm>
              </div>
            </div>
          </div>

          <div v-if="!loading && filteredImages.length === 0" class="grid-empty">
            <el-empty
              :description="images.length === 0 ? '暂无图片，请在右侧上传' : '当前筛选无图片'"
              :image-size="70"
            />
          </div>
        </div>

        <!-- 加载更多 / 分页 -->
        <div v-if="filteredImages.length > PAGE_SIZE" class="grid-footer">
          <span class="mono footer-info">共 {{ filteredImages.length }} 张 · 已显示 {{ pagedImages.length }} 张</span>
          <el-button
            v-if="pagedImages.length < filteredImages.length"
            size="small"
            @click="loadMore"
          >加载更多</el-button>
        </div>
      </div>

      <!-- 右侧：操作面板 -->
      <div class="side-panel">
        <!-- 上传 -->
        <el-card shadow="never" header="上传图片">
          <el-upload
            ref="uploadRef"
            drag
            multiple
            accept="image/*"
            :auto-upload="false"
            :on-change="handleFileChange"
            :file-list="[]"
            action=""
            class="upload-area"
          >
            <el-icon :size="36"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽或点击上传</div>
            <template #tip>
              <div class="el-upload__tip">JPG / PNG / WebP，可批量</div>
            </template>
          </el-upload>

          <div class="upload-options">
            <div class="upload-opt-row">
              <span class="upload-label">上传后归入</span>
              <el-select v-model="defaultSplit" size="small" class="split-select">
                <el-option label="训练集" value="train" />
                <el-option label="验证集" value="val" />
                <el-option label="测试集" value="test" />
              </el-select>
            </div>
            <el-button
              type="primary"
              size="small"
              class="upload-btn"
              @click="handleUpload"
              :loading="uploading"
              :disabled="pendingFiles.length === 0"
            >
              <el-icon v-if="!uploading" style="margin-right: 4px;"><Upload /></el-icon>
              {{ uploading ? '上传中...' : (pendingFiles.length ? `上传 ${pendingFiles.length} 张图片` : '上传图片') }}
            </el-button>
          </div>

          <div v-if="pendingFiles.length > 0" class="pending-files">
            <div
              v-for="(file, idx) in pendingFiles"
              :key="idx"
              class="pending-item"
            >
              <el-icon><Document /></el-icon>
              <span class="pending-name">{{ file.name }}</span>
              <el-icon class="remove-btn" @click="pendingFiles.splice(idx, 1)"><Close /></el-icon>
            </div>
          </div>
        </el-card>

        <!-- 数据集划分 -->
        <el-card shadow="never" header="数据集划分" style="margin-top: 12px;">
          <div class="split-bars">
            <div class="split-segment train" :style="{ width: project.train_ratio * 100 + '%' }">训练 {{ Math.round(project.train_ratio * 100) }}%</div>
            <div class="split-segment val" :style="{ width: project.val_ratio * 100 + '%' }">验证 {{ Math.round(project.val_ratio * 100) }}%</div>
            <div class="split-segment test" :style="{ width: project.test_ratio * 100 + '%' }">测试 {{ Math.round(project.test_ratio * 100) }}%</div>
          </div>
          <el-slider
            v-model="trainRatioValue"
            :min="50"
            :max="90"
            :step="5"
            show-stops
            :format-tooltip="(val) => `训练 ${val}%`"
            @change="updateSplitRatio"
            style="margin: 14px 6px 0;"
          />
          <el-button type="primary" style="width: 100%; margin-top: 12px;" @click="autoSplit" :disabled="images.length === 0">
            按比例自动划分
          </el-button>
          <p class="tip-text">当前比例：{{ Math.round(project.train_ratio * 100) }} / {{ Math.round(project.val_ratio * 100) }} / {{ Math.round(project.test_ratio * 100) }}</p>
        </el-card>

        <!-- 标注类别 -->
        <el-card shadow="never" header="标注类别" style="margin-top: 12px;">
          <div class="class-list">
            <el-tag
              v-for="cls in project.classes"
              :key="cls"
              closable
              type="primary"
              effect="plain"
              size="default"
              @close="removeClass(cls)"
            >
              {{ cls }}
            </el-tag>
            <el-input
              v-if="showClassInput"
              ref="classInputRef"
              v-model="newClass"
              size="small"
              placeholder="类别名回车确认"
              style="width: 120px;"
              @keyup.enter="addClass"
              @blur="showClassInput = false"
            />
            <el-button v-else size="small" plain @click="openClassInput">
              <el-icon><Plus /></el-icon> 添加
            </el-button>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { projectApi, imageApi } from '@/api'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => parseInt(route.params.id))
const uploadRef = ref(null)
const classInputRef = ref(null)

// Data
const loading = ref(false)
const uploading = ref(false)
const project = ref({})
const images = ref([])
const pendingFiles = ref([])
const defaultSplit = ref('train')
const showClassInput = ref(false)
const newClass = ref('')
const filterTab = ref('all')
const annoFilter = ref('all') // all | annotated | unannotated
const PAGE_SIZE = 24
const visibleCount = ref(PAGE_SIZE)

// Tabs
const tabs = [
  { label: '全部', value: 'all' },
  { label: '训练', value: 'train' },
  { label: '验证', value: 'val' },
  { label: '测试', value: 'test' },
]

// 标注状态筛选
const annoFilters = [
  { label: '全部标注状态', value: 'all' },
  { label: '已标注', value: 'annotated' },
  { label: '未标注', value: 'unannotated' },
]

// Computed
const splitCounts = computed(() => ({
  train: images.value.filter(i => i.split === 'train').length,
  val: images.value.filter(i => i.split === 'val').length,
  test: images.value.filter(i => i.split === 'test').length,
}))

const annotatedCount = computed(() =>
  images.value.filter(i => i.annotation_count > 0).length
)

const filteredImages = computed(() => {
  let list = images.value
  if (filterTab.value !== 'all') {
    list = list.filter(i => i.split === filterTab.value)
  }
  if (annoFilter.value === 'annotated') {
    list = list.filter(i => i.annotation_count > 0)
  } else if (annoFilter.value === 'unannotated') {
    list = list.filter(i => !(i.annotation_count > 0))
  }
  return list
})

// 分页：当前筛选结果的前 N 张
const pagedImages = computed(() => filteredImages.value.slice(0, visibleCount.value))

// 筛选变化时重置分页
watch([filterTab, annoFilter], () => {
  visibleCount.value = PAGE_SIZE
})

const annoFilterCount = (value) => {
  let list = images.value
  if (filterTab.value !== 'all') {
    list = list.filter(i => i.split === filterTab.value)
  }
  if (value === 'annotated') return list.filter(i => i.annotation_count > 0).length
  if (value === 'unannotated') return list.filter(i => !(i.annotation_count > 0)).length
  return list.length
}

// 加载更多：追加一页并滚动到新内容位置
const loadMore = () => {
  const grid = document.querySelector('.image-grid')
  const before = grid ? grid.scrollHeight : 0
  visibleCount.value += PAGE_SIZE
  nextTick(() => {
    if (grid) {
      grid.scrollTop = grid.scrollHeight - before
    }
  })
}

const tabCount = (value) => {
  if (value === 'all') return images.value.length
  return splitCounts.value[value]
}

const trainRatioValue = computed({
  get: () => Math.round((project.value?.train_ratio || 0.7) * 100),
  set: () => {},
})

// Methods
const loadProject = async () => {
  try {
    project.value = await projectApi.get(projectId.value)
  } catch (e) {}
}

const loadImages = async () => {
  loading.value = true
  try {
    images.value = await imageApi.list(projectId.value)
  } finally {
    loading.value = false
  }
}

const handleFileChange = (file) => {
  if (file.raw && file.raw.type.startsWith('image/')) {
    pendingFiles.value.push(file.raw)
  }
}

const handleUpload = async () => {
  if (pendingFiles.value.length === 0) return
  uploading.value = true
  try {
    await imageApi.upload(projectId.value, pendingFiles.value, defaultSplit.value)
    ElMessage.success(`成功上传 ${pendingFiles.value.length} 张图片`)
    pendingFiles.value = []
    loadImages()
  } catch (e) {
  } finally {
    uploading.value = false
  }
}

const deleteImage = async (id) => {
  await imageApi.delete(id)
  ElMessage.success('图片已删除')
  loadImages()
}

// 跳转到标注页并定位到该图片
const goAnnotate = (imageId) => {
  router.push({
    path: `/project/${projectId.value}/annotate`,
    query: imageId ? { image: String(imageId) } : {},
  })
}

const autoSplit = async () => {
  const res = await imageApi.autoSplit(projectId.value)
  ElMessage.success(res.message)
  loadImages()
}

const updateSplitRatio = async (val) => {
  const ratio = val / 100
  const remaining = 1 - ratio
  try {
    await projectApi.update(projectId.value, {
      train_ratio: ratio,
      val_ratio: remaining / 2,
      test_ratio: remaining / 2,
    })
    project.value.train_ratio = ratio
    project.value.val_ratio = remaining / 2
    project.value.test_ratio = remaining / 2
  } catch (e) {}
}

const openClassInput = async () => {
  showClassInput.value = true
  await nextTick()
  classInputRef.value?.focus()
}

const addClass = async () => {
  const cls = newClass.value.trim().toLowerCase()
  if (!cls || (project.value.classes || []).includes(cls)) return
  const classes = [...(project.value.classes || []), cls]
  await projectApi.update(projectId.value, { classes })
  project.value.classes = classes
  newClass.value = ''
  showClassInput.value = false
}

const removeClass = async (cls) => {
  const classes = (project.value.classes || []).filter(c => c !== cls)
  await projectApi.update(projectId.value, { classes })
  project.value.classes = classes
}

onMounted(() => {
  loadProject()
  loadImages()
})
</script>

<style lang="scss" scoped>
.dataset-page {
  // ─── 统计条 ──────────────────────────────
  .stats-bar {
    display: flex;
    background: #fff;
    border: 1px solid #e5e6eb;
    border-radius: 4px;
    margin-bottom: 14px;
    overflow: hidden;

    .stat-cell {
      flex: 1;
      text-align: center;
      padding: 12px 0;
      border-right: 1px solid #f2f3f5;

      .stat-num {
        display: block;
        font-size: 20px;
        font-weight: 700;
        color: #1f2329;
      }

      .stat-label {
        font-size: 11px;
        color: #86909c;
        margin-top: 2px;
      }
    }
  }

  // ─── 布局 ────────────────────────────────
  .dataset-layout {
    display: flex;
    gap: 14px;
    align-items: flex-start;
  }

  // ─── 左侧网格 ────────────────────────────
  .grid-panel {
    flex: 1;
    min-width: 0;
    background: #fff;
    border: 1px solid #e5e6eb;
    border-radius: 4px;
    padding: 14px;

    .filter-tabs {
      display: flex;
      gap: 2px;
      border-bottom: 1px solid #e5e6eb;
      margin-bottom: 4px;

      .tab {
        padding: 8px 14px;
        font-size: 13px;
        color: #4e5969;
        cursor: pointer;
        border-bottom: 2px solid transparent;
        margin-bottom: -1px;
        display: flex;
        align-items: center;
        gap: 6px;

        &:hover { color: #1f5aff; }

        &.active {
          color: #1f5aff;
          font-weight: 600;
          border-bottom-color: #1f5aff;
        }

        .tab-count {
          font-size: 11px;
          color: #86909c;
          background: #f2f3f5;
          border-radius: 8px;
          padding: 0 6px;
        }
      }
    }

    .anno-filter {
      display: flex;
      gap: 2px;
      padding: 2px 0 10px;

      .tab {
        padding: 4px 12px;
        font-size: 12px;
        color: #86909c;
        cursor: pointer;
        border: 1px solid #e5e6eb;
        border-radius: 12px;
        display: flex;
        align-items: center;
        gap: 5px;
        transition: all 0.15s;

        &:hover { border-color: #8fabff; color: #1f5aff; }

        &.active {
          border-color: #1f5aff;
          color: #1f5aff;
          background: #f5f8ff;
          font-weight: 600;
        }

        .tab-count {
          font-size: 10px;
          color: #86909c;
        }
      }
    }

    .image-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
      gap: 10px;
      min-height: 200px;

      .img-card {
        border: 1px solid #e5e6eb;
        border-radius: 4px;
        overflow: hidden;
        background: #fff;
        cursor: pointer;
        transition: border-color 0.15s, box-shadow 0.15s;

        &:hover {
          border-color: #1f5aff;
          box-shadow: 0 1px 4px rgba(31, 90, 255, 0.12);
        }

        .split-bar {
          height: 3px;

          &.train { background: #1f5aff; }
          &.val { background: #e6a23c; }
          &.test { background: #0f9d58; }
        }

        .img-wrap {
          position: relative;

          .thumb {
            width: 100%;
            aspect-ratio: 4/3;
            display: block;

            :deep(img) {
              width: 100%;
              height: 100%;
              object-fit: cover;
            }
          }

          // 标注状态角标
          .anno-badge {
            position: absolute;
            top: 6px;
            right: 6px;
            display: flex;
            align-items: center;
            gap: 3px;
            font-size: 10px;
            font-weight: 600;
            padding: 2px 7px;
            border-radius: 10px;
            color: #fff;

            &.done {
              background: rgba(15, 157, 88, 0.9);
            }

            &.none {
              background: rgba(108, 117, 125, 0.85);
            }
          }
        }

        .img-info {
          padding: 7px 9px 9px;
          display: flex;
          flex-direction: column;
          gap: 3px;

          .img-name {
            font-size: 12px;
            color: #1f2329;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }

          .img-meta {
            font-size: 11px;

            &.anno-done { color: #0f9d58; font-weight: 600; }
            &.anno-none { color: #a9aeb8; }
          }

          .img-opts {
            display: flex;
            gap: 6px;
            margin-top: 4px;

            .el-button {
              flex: 1;
              margin: 0;
            }
          }
        }
      }

      .grid-empty {
        grid-column: 1 / -1;
        padding: 40px 0;
      }
    }

    // 分页脚
    .grid-footer {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 14px;
      padding: 14px 0 2px;
      border-top: 1px solid #f2f3f5;
      margin-top: 12px;

      .footer-info {
        font-size: 12px;
        color: #86909c;
      }
    }
  }

  // ─── 右侧面板 ────────────────────────────
  .side-panel {
    width: 300px;
    flex: 0 0 300px;

    .upload-area {
      :deep(.el-upload-dragger) {
        padding: 22px 10px;
      }
    }

    .upload-options {
      margin-top: 12px;

      .upload-opt-row {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;

        .upload-label {
          font-size: 12px;
          color: #4e5969;
          white-space: nowrap;
        }

        .split-select {
          flex: 1;
          min-width: 0;
        }
      }

      .upload-btn {
        width: 100%;
        margin: 0;
      }
    }

    .pending-files {
      margin-top: 10px;
      max-height: 140px;
      overflow-y: auto;
      border: 1px solid #f2f3f5;
      border-radius: 3px;
      padding: 4px 8px;

      .pending-item {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 3px 0;
        font-size: 12px;

        .pending-name {
          flex: 1;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .remove-btn {
          cursor: pointer;
          color: #86909c;
          &:hover { color: #e5484d; }
        }
      }
    }

    .split-bars {
      display: flex;
      height: 28px;
      border-radius: 3px;
      overflow: hidden;

      .split-segment {
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 11px;
        color: #fff;
        white-space: nowrap;
        overflow: hidden;
        transition: width 0.3s;

        &.train { background-color: #1f5aff; }
        &.val { background-color: #e6a23c; }
        &.test { background-color: #0f9d58; }
      }
    }

    .tip-text {
      margin-top: 10px;
      font-size: 11px;
      color: #86909c;
      text-align: center;
    }

    .class-list {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
  }
}
</style>
