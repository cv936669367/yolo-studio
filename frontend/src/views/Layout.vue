<template>
  <div class="app-shell">
    <!-- Top bar -->
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark">Y</span>
        <span class="brand-name">YOLO Studio</span>
      </div>

      <div class="topbar-right">
        <el-tag v-if="currentProject" type="primary" effect="plain" size="small" round>
          {{ currentProject.name }}
        </el-tag>
        <el-tag size="small" effect="plain" round>v1.0.0</el-tag>
      </div>
    </header>

    <div class="app-body">
      <!-- Sidebar nav -->
      <aside class="sidebar">
        <div class="nav-section-label">工作区</div>
        <el-menu
          :default-active="activeMenu"
          router
          class="nav-menu"
          @select="onMenuSelect"
        >
          <el-menu-item index="/projects">
            <el-icon><FolderOpened /></el-icon>
            <span>工程列表</span>
          </el-menu-item>

          <template v-if="currentProjectId">
            <div class="nav-section-label project-label">
              {{ currentProject ? currentProject.name : '当前工程' }}
            </div>
            <el-menu-item :index="`/project/${currentProjectId}/dataset`">
              <el-icon><Picture /></el-icon>
              <span>数据集</span>
            </el-menu-item>
            <el-menu-item :index="`/project/${currentProjectId}/annotate`">
              <el-icon><EditPen /></el-icon>
              <span>图片标注</span>
            </el-menu-item>
            <el-menu-item :index="`/project/${currentProjectId}/train`">
              <el-icon><Cpu /></el-icon>
              <span>模型训练</span>
            </el-menu-item>
            <el-menu-item :index="`/project/${currentProjectId}/evaluate`">
              <el-icon><DataAnalysis /></el-icon>
              <span>模型验证</span>
            </el-menu-item>
            <el-menu-item :index="`/project/${currentProjectId}/test`">
              <el-icon><View /></el-icon>
              <span>测试识别</span>
            </el-menu-item>
          </template>
        </el-menu>
      </aside>

      <!-- Main content -->
      <main class="main-area">
        <div class="content">
          <router-view @project-loaded="handleProjectLoaded" />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const currentProject = ref(null)

const currentProjectId = computed(() => {
  const id = route.params.id
  return id ? parseInt(id) : null
})

const activeMenu = computed(() => route.path)

const handleProjectLoaded = (project) => {
  if (project) currentProject.value = project
}

const onMenuSelect = () => {}

// 进入项目子页时加载工程信息
watch(currentProjectId, async (newId) => {
  if (newId) {
    try {
      const { projectApi } = await import('@/api')
      currentProject.value = await projectApi.get(newId)
    } catch {
      currentProject.value = null
    }
  } else {
    currentProject.value = null
  }
}, { immediate: true })
</script>

<style lang="scss" scoped>
.app-shell {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

// ─── Top bar ─────────────────────────────────────────────
.topbar {
  height: 52px;
  flex: 0 0 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: #16181d;
  border-bottom: 1px solid #26282f;

  .brand {
    display: flex;
    align-items: center;
    gap: 10px;

    .brand-mark {
      width: 26px;
      height: 26px;
      border-radius: 4px;
      background: #1f5aff;
      color: #fff;
      font-weight: 700;
      font-size: 15px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .brand-name {
      color: #e8eaed;
      font-size: 15px;
      font-weight: 600;
      letter-spacing: 0.2px;
    }
  }

  .topbar-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

// ─── Body ────────────────────────────────────────────────
.app-body {
  flex: 1;
  display: flex;
  min-height: 0;
}

.sidebar {
  width: 208px;
  flex: 0 0 208px;
  background: #1b1e25;
  overflow-y: auto;
  padding-bottom: 12px;

  .nav-section-label {
    padding: 14px 16px 6px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    color: #5c6470;
  }

  .nav-menu {
    background: transparent;
    border-right: none;

    :deep(.el-menu-item) {
      height: 38px;
      line-height: 38px;
      margin: 2px 8px;
      border-radius: 4px;
      color: #a7adb8;
      font-size: 13px;

      .el-icon {
        color: #6b7380;
        font-size: 15px;
      }

      &:hover {
        background: #262a33;
        color: #d5d9e0;
      }

      &.is-active {
        background: #25314f;
        color: #6d9bff;
        font-weight: 500;

        .el-icon {
          color: #6d9bff;
        }
      }
    }
  }
}

.main-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}
</style>
