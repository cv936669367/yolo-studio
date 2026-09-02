<template>
  <div class="app-shell">
    <!-- Top bar -->
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark">Y</span>
        <span class="brand-name" v-show="!sidebarCollapsed">YOLO Studio</span>
        <!-- 折叠侧栏按钮（标题右侧） -->
        <el-tooltip :content="sidebarCollapsed ? '展开菜单' : '折叠菜单（仅图标）'" placement="bottom">
          <button
            class="collapse-btn"
            :class="{ collapsed: sidebarCollapsed }"
            @click="toggleSidebar"
          >
            <el-icon :size="15">
              <Expand v-if="sidebarCollapsed" />
              <Fold v-else />
            </el-icon>
          </button>
        </el-tooltip>
      </div>

      <div class="topbar-right">
        <el-tag v-if="currentProject" type="primary" effect="plain" size="small" round>
          {{ currentProject.name }}
        </el-tag>
        <el-tag size="small" effect="plain" round>v1.2.11</el-tag>
        <!-- 计算设备 -->
        <el-tooltip v-if="sysInfo" :content="`推理设备: ${sysInfo.device_name} · torch ${sysInfo.torch}`" placement="bottom">
          <div class="device-badge" :class="sysInfo.device_label === 'GPU' ? 'gpu' : 'cpu'">
            <el-icon :size="13"><Cpu /></el-icon>
            <span class="device-type">{{ sysInfo.device_label }}</span>
            <span class="device-name">{{ sysInfo.device_name }}</span>
          </div>
        </el-tooltip>
        <!-- 主题切换 -->
        <el-tooltip :content="isDark ? '切换到明亮模式' : '切换到暗黑模式'" placement="bottom">
          <button class="theme-toggle" :class="{ dark: isDark }" @click="toggleTheme">
            <el-icon :size="16">
              <Sunny v-if="!isDark" />
              <Moon v-else />
            </el-icon>
          </button>
        </el-tooltip>
      </div>
    </header>

    <div class="app-body">
      <!-- Sidebar nav -->
      <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
        <div class="nav-scroll">
          <div class="nav-section-label" v-if="!sidebarCollapsed">工作区</div>
          <div class="nav-stack">
            <el-tooltip
              v-for="item in navItems"
              :key="item.path"
              :content="item.label"
              placement="right"
              :disabled="!sidebarCollapsed"
            >
              <div
                class="nav-item"
                :class="{ active: activeMenu === item.path, 'nav-icon-only': sidebarCollapsed }"
                @click="$router.push(item.path)"
              >
                <el-icon :size="16"><component :is="item.icon" /></el-icon>
                <span class="nav-label" v-show="!sidebarCollapsed">{{ item.label }}</span>
              </div>
            </el-tooltip>

            <template v-if="currentProjectId">
              <div class="nav-section-label project-label" v-if="!sidebarCollapsed">
                {{ currentProject ? currentProject.name : '当前工程' }}
              </div>
              <el-tooltip
                v-for="item in projectNavItems"
                :key="item.path"
                :content="item.label"
                placement="right"
                :disabled="!sidebarCollapsed"
              >
                <div
                  class="nav-item"
                  :class="{ active: activeMenu === item.path }"
                  @click="$router.push(item.path)"
                >
                  <el-icon :size="16"><component :is="item.icon" /></el-icon>
                  <span class="nav-label" v-show="!sidebarCollapsed">{{ item.label }}</span>
                </div>
              </el-tooltip>
            </template>
          </div>
        </div>

        <!-- 底部组织标识：新疆软件园 -->
        <div class="sidebar-footer" :class="{ collapsed: sidebarCollapsed }">
          <el-tooltip content="新疆软件园" placement="right" :disabled="!sidebarCollapsed">
            <div class="org-badge">
              <span class="org-mark">疆</span>
              <span class="org-text" v-show="!sidebarCollapsed">
                <span class="org-name">新疆软件园</span>
                <span class="org-sub">XINJIANG SOFTWARE PARK</span>
              </span>
            </div>
          </el-tooltip>
        </div>
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

// ─── 主题切换（明亮/暗黑）───
const isDark = ref(document.documentElement.classList.contains('dark'))

// 侧栏折叠（仅图标模式）
const sidebarCollapsed = ref(localStorage.getItem('yolo_sidebar') === '1')
const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
  localStorage.setItem('yolo_sidebar', sidebarCollapsed.value ? '1' : '0')
}

// 导航菜单（图标用全局注册的 Element 图标名）
const navItems = [
  { path: '/projects', icon: 'FolderOpened', label: '工程列表' },
]
const projectNavItems = computed(() => {
  const pid = currentProjectId.value
  if (!pid) return []
  return [
    { path: `/project/${pid}/dataset`, icon: 'Picture', label: '数据集' },
    { path: `/project/${pid}/annotate`, icon: 'EditPen', label: '图片标注' },
    { path: `/project/${pid}/train`, icon: 'Cpu', label: '模型训练' },
    { path: `/project/${pid}/artifacts`, icon: 'Box', label: '制品管理' },
    { path: `/project/${pid}/evaluate`, icon: 'DataAnalysis', label: '模型验证' },
    { path: `/project/${pid}/test`, icon: 'View', label: '测试识别' },
  ]
})

const applyTheme = (dark) => {
  document.documentElement.classList.toggle('dark', dark)
  localStorage.setItem('yolo_theme', dark ? 'dark' : 'light')
}

const toggleTheme = () => {
  isDark.value = !isDark.value
  applyTheme(isDark.value)
}

// 计算设备信息（GPU/CPU + 型号）
const sysInfo = ref(null)
const loadSysInfo = async () => {
  try {
    const res = await fetch('/api/system/info')
    sysInfo.value = await res.json()
  } catch (e) {}
}

const currentProjectId = computed(() => {
  const id = route.params.id
  return id ? parseInt(id) : null
})

const activeMenu = computed(() => route.path)

const handleProjectLoaded = (project) => {
  if (project) currentProject.value = project
}

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

loadSysInfo()
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
  background: var(--nav-bg);
  border-bottom: 1px solid var(--nav-border);

  .device-badge {
    display: flex;
    align-items: center;
    gap: 5px;
    height: 26px;
    padding: 0 10px;
    border-radius: 13px;
    font-size: 11px;
    cursor: default;

    &.gpu {
      background: rgba(31, 90, 255, 0.16);
      border: 1px solid rgba(93, 133, 255, 0.35);
      color: #8fabff;

      .device-type {
        font-weight: 700;
        color: #6d9bff;
      }
    }

    &.cpu {
      background: rgba(108, 117, 125, 0.14);
      border: 1px solid rgba(134, 142, 156, 0.3);
      color: #9aa1ad;
    }

    .device-name {
      max-width: 130px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .theme-toggle {
    width: 32px;
    height: 32px;
    border-radius: 6px;
    border: 1px solid var(--nav-border);
    background: transparent;
    color: var(--nav-text);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      background: var(--nav-bg-hover);
      color: #ffd666;
      border-color: rgba(255, 214, 102, 0.4);
    }

    &.dark {
      color: #8fabff;

      &:hover {
        color: #ffd666;
        background: var(--nav-bg-hover);
      }
    }
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 10px;

    .collapse-btn {
      width: 28px;
      height: 28px;
      margin-left: 4px;
      border-radius: 6px;
      border: 1px solid transparent;
      background: transparent;
      color: var(--nav-text);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: all 0.2s;

      &:hover {
        background: var(--nav-bg-hover);
        color: #fff;
      }

      &.collapsed {
        color: var(--nav-text-active);
        background: var(--nav-active-bg);
      }
    }

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
  background: var(--nav-bg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width 0.1s ease, flex-basis 0.1s ease;

  &.collapsed {
    width: 64px;
    flex-basis: 64px;
  }

  .nav-scroll {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    min-height: 0;
  }

  .nav-section-label {
    padding: 14px 16px 6px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    color: #5c6470;
    white-space: nowrap;
    overflow: hidden;
  }

  .nav-stack {
    display: flex;
    flex-direction: column;
    gap: 2px;

    .nav-item {
      display: flex;
      align-items: center;
      gap: 10px;
      height: 40px;
      margin: 2px 8px;
      padding: 0 10px;
      border-radius: 6px;
      color: var(--nav-text);
      font-size: 13px;
      cursor: pointer;
      transition: background 0.15s, color 0.15s;
      white-space: nowrap;
      overflow: hidden;

      .el-icon {
        flex: 0 0 auto;
        color: var(--text-faint);
      }

      &:hover {
        background: var(--nav-bg-hover);
        color: var(--text-1);

        .el-icon { color: var(--nav-text-active); }
      }

      &.active {
        background: var(--nav-active-bg);
        color: var(--nav-text-active);
        font-weight: 500;

        .el-icon { color: var(--nav-text-active); }
      }

      &.nav-icon-only {
        justify-content: center;
        padding: 0;
      }
    }
  }

  .sidebar-footer {
    flex: 0 0 auto;
    padding: 10px 12px;
    border-top: 1px solid var(--nav-border);
    background: rgba(0, 0, 0, 0.12);

    .org-badge {
      display: flex;
      align-items: center;
      gap: 10px;
      border-radius: 6px;
      padding: 6px 8px;
      cursor: default;
      transition: background 0.15s;

      &:hover {
        background: var(--nav-bg-hover);
      }

      .org-mark {
        flex: 0 0 auto;
        width: 30px;
        height: 30px;
        border-radius: 7px;
        background: linear-gradient(135deg, #1f5aff, #0f9d58);
        color: #fff;
        font-size: 16px;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .org-text {
        display: flex;
        flex-direction: column;
        min-width: 0;

        .org-name {
          font-size: 13px;
          font-weight: 600;
          color: var(--nav-text);
          white-space: nowrap;
        }

        .org-sub {
          font-size: 9px;
          letter-spacing: 0.4px;
          color: #5c6470;
          white-space: nowrap;
          overflow: hidden;
        }
      }
    }

    // 折叠：只显示标识方块
    &.collapsed {
      padding: 10px 0;
      display: flex;
      justify-content: center;

      .org-badge { padding: 4px; }
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
