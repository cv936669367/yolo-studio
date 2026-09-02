<template>
  <div class="projects-page">
    <div class="page-head">
      <div>
        <div class="page-title">工程列表</div>
        <div class="page-sub">创建 YOLO 检测工程并管理数据、标注与训练</div>
      </div>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon style="margin-right: 5px;"><Plus /></el-icon>
        新建工程
      </el-button>
    </div>

    <!-- Project Cards -->
    <div v-loading="loading" class="project-grid">
      <div
        v-for="project in projects"
        :key="project.id"
        class="project-card"
        @click="openProject(project)"
      >
        <div class="card-top">
          <div class="project-name">{{ project.name }}</div>
          <el-tag
            :type="project.anno_type === 'rectangle' ? 'primary' : 'warning'"
            size="small"
            effect="plain"
          >
            {{ project.anno_type === 'rectangle' ? '矩形框' : '多边形' }}
          </el-tag>
        </div>

        <div class="project-desc" v-if="project.description">{{ project.description }}</div>
        <div class="project-desc empty" v-else>—</div>

        <div class="stat-row">
          <div class="stat">
            <span class="stat-num">{{ project.image_count }}</span>
            <span class="stat-label">图片</span>
          </div>
          <div class="stat">
            <span class="stat-num">{{ project.classes?.length || 0 }}</span>
            <span class="stat-label">类别</span>
          </div>
          <div class="stat">
            <span class="stat-num">{{ project.train_run_count }}</span>
            <span class="stat-label">训练</span>
          </div>
        </div>

        <div class="card-bottom">
          <span class="created">{{ formatDate(project.created_at) }}</span>
          <span class="card-actions" @click.stop>
            <el-button type="primary" link size="small" @click="openProject(project)">打开</el-button>
            <el-popconfirm
              title="删除工程？将清除全部图片与标注数据"
              width="220"
              @confirm="handleDelete(project)"
            >
              <template #reference>
                <el-button type="danger" link size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </span>
        </div>
      </div>

      <div v-if="!loading && projects.length === 0" class="empty-state">
        <el-empty description="暂无工程，点击右上角「新建工程」开始" :image-size="80" />
      </div>
    </div>

    <!-- Create Project Dialog -->
    <el-dialog
      v-model="showCreateDialog"
      title="新建工程"
      width="600px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-position="top"
      >
        <el-form-item label="工程名称" prop="name">
          <el-input v-model="formData.name" placeholder="例如：安全帽检测、车辆识别" />
        </el-form-item>

        <el-form-item label="描述">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="2"
            placeholder="简要描述检测用途（可选）"
          />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="标注类型">
              <el-select v-model="formData.anno_type" style="width: 100%">
                <el-option label="矩形框 (Bounding Box)" value="rectangle" />
                <el-option label="多边形 (Segmentation)" value="polygon" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="默认类别">
              <div class="class-tags">
                <el-tag
                  v-for="cls in formData.classes"
                  :key="cls"
                  closable
                  size="small"
                  @close="removeClass(cls)"
                >
                  {{ cls }}
                </el-tag>
                <el-input
                  v-if="showClassInput"
                  ref="classInputRef"
                  v-model="newClass"
                  size="small"
                  style="width: 90px"
                  @keyup.enter="addClass"
                  @blur="handleClassBlur"
                  placeholder="类别"
                />
                <el-button v-else size="small" @click="addNewClassInput" :icon="Plus" circle />
              </div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left" style="margin: 8px 0;">数据集划分比例</el-divider>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="训练集">
              <el-input-number v-model="trainPercent" :min="50" :max="90" :step="5" @change="updateRatios" />%
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="验证集">
              <el-input-number v-model="valPercent" :min="5" :max="25" :step="5" @change="updateRatios" />%
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="测试集">
              <el-input-number v-model="testPercent" :min="5" :max="25" :step="5" disabled />%
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="creating">创建工程</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { projectApi } from '@/api'

const router = useRouter()
const loading = ref(false)
const creating = ref(false)
const showCreateDialog = ref(false)
const projects = ref([])
const formRef = ref(null)
const classInputRef = ref(null)

const formData = reactive({
  name: '',
  description: '',
  anno_type: 'rectangle',
  classes: ['person', 'car', 'truck'],
})

const formRules = {
  name: [{ required: true, message: '请输入工程名称', trigger: 'blur' }],
}

const trainPercent = ref(70)
const valPercent = ref(15)
const testPercent = computed(() => 100 - trainPercent.value - valPercent.value)

const showClassInput = ref(false)
const newClass = ref('')

const updateRatios = () => {
  const remaining = 100 - trainPercent.value
  valPercent.value = Math.round(remaining / 2)
}

const addNewClassInput = async () => {
  showClassInput.value = true
  await nextTick()
  classInputRef.value?.focus()
}

const handleClassBlur = () => {
  if (!newClass.value.trim()) showClassInput.value = false
}

const addClass = () => {
  const cls = newClass.value.trim().toLowerCase()
  if (cls && !formData.classes.includes(cls)) formData.classes.push(cls)
  newClass.value = ''
  showClassInput.value = false
}

const removeClass = (cls) => {
  const idx = formData.classes.indexOf(cls)
  if (idx > -1) formData.classes.splice(idx, 1)
}

const loadProjects = async () => {
  loading.value = true
  try {
    projects.value = await projectApi.list()
  } finally {
    loading.value = false
  }
}

const handleCreate = async () => {
  await formRef.value?.validate()
  creating.value = true
  try {
    const project = await projectApi.create({
      name: formData.name,
      description: formData.description,
      anno_type: formData.anno_type,
      classes: formData.classes,
      train_ratio: trainPercent.value / 100,
      val_ratio: valPercent.value / 100,
      test_ratio: testPercent.value / 100,
    })
    ElMessage.success('工程创建成功')
    showCreateDialog.value = false
    formData.name = ''
    formData.description = ''
    formData.anno_type = 'rectangle'
    formData.classes = ['person', 'car', 'truck']
    router.push(`/project/${project.id}/dataset`)
  } catch (e) {
    // interceptor handles error
  } finally {
    creating.value = false
  }
}

const openProject = (project) => {
  router.push(`/project/${project.id}/dataset`)
}

const handleDelete = async (project) => {
  try {
    await projectApi.delete(project.id)
    ElMessage.success(`工程 "${project.name}" 已删除`)
    loadProjects()
  } catch (e) {
    // interceptor handles error
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

onMounted(() => {
  loadProjects()
})
</script>

<style lang="scss" scoped>
.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;

  .project-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 16px;
    cursor: pointer;
    transition: border-color 0.15s, box-shadow 0.15s;

    &:hover {
      border-color: #1f5aff;
      box-shadow: 0 1px 4px rgba(31, 90, 255, 0.12);
    }

    .card-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;

      .project-name {
        font-size: 15px;
        font-weight: 600;
        color: var(--text-1);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }

    .project-desc {
      margin-top: 8px;
      font-size: 12px;
      color: var(--text-2);
      line-height: 1.5;
      min-height: 32px;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;

      &.empty {
        color: var(--text-faint);
      }
    }

    .stat-row {
      display: flex;
      gap: 28px;
      margin: 14px 0;
      padding: 10px 0;
      border-top: 1px solid var(--border-light);
      border-bottom: 1px solid var(--border-light);

      .stat {
        display: flex;
        align-items: baseline;
        gap: 4px;

        .stat-num {
          font-size: 17px;
          font-weight: 700;
          color: var(--text-1);
          font-variant-numeric: tabular-nums;
        }

        .stat-label {
          font-size: 12px;
          color: var(--text-3);
        }
      }
    }

    .card-bottom {
      display: flex;
      align-items: center;
      justify-content: space-between;

      .created {
        font-size: 12px;
        color: var(--text-3);
        font-variant-numeric: tabular-nums;
      }

      .card-actions {
        display: flex;
        gap: 4px;
      }
    }
  }

  .empty-state {
    grid-column: 1 / -1;
    background: var(--bg-card);
    border: 1px dashed #d9dde3;
    border-radius: 4px;
    padding: 40px 0;
  }
}

.class-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}
</style>
