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
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElNotification } from 'element-plus'
import { trainApi } from '@/api'

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

// ─── 训练完成全局提醒（标题闪烁 + 提示音 + 通知）────────
// 无论停留在哪个页面，训练结束都能收到提醒；开关在训练页（localStorage yolo_notify_enabled）
const notifyEnabled = () => localStorage.getItem('yolo_notify_enabled') !== '0'

// 声音：WebAudio 提示音（需用户交互解锁 AudioContext）
let audioCtx = null
let audioUnlocked = false

const unlockAudio = () => {
  ensureAudio()
  audioUnlocked = true
  window.removeEventListener('pointerdown', unlockAudio)
  window.removeEventListener('keydown', unlockAudio)
}

const ensureAudio = () => {
  if (!audioCtx) {
    const AC = window.AudioContext || window.webkitAudioContext
    if (AC) audioCtx = new AC()
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume().catch(() => {})
  }
}

const tone = (freq, startIn, dur) => {
  if (!audioCtx) return
  try {
    const osc = audioCtx.createOscillator()
    const gain = audioCtx.createGain()
    osc.type = 'sine'
    osc.frequency.value = freq
    const t0 = audioCtx.currentTime + startIn
    gain.gain.setValueAtTime(0.0001, t0)
    gain.gain.exponentialRampToValueAtTime(0.16, t0 + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur)
    osc.connect(gain)
    gain.connect(audioCtx.destination)
    osc.start(t0)
    osc.stop(t0 + dur + 0.05)
  } catch (e) {}
}

const playDoneSound = () => {
  ensureAudio()
  tone(880, 0, 0.16)      // 叮
  tone(1174.66, 0.2, 0.26) // 咚（高）
}

const playFailSound = () => {
  ensureAudio()
  tone(392, 0, 0.2)       // 低
  tone(311.13, 0.24, 0.3)
}

// 标题闪烁（页面在后台时）
let blinkData = null

const startBlink = (mark) => {
  stopBlink()
  const base = document.title
  let on = true
  blinkData = {
    mark,
    timer: setInterval(() => {
      on = !on
      document.title = on ? `${mark} · ${base}` : base
    }, 800),
  }
}

const stopBlink = () => {
  if (!blinkData) return
  clearInterval(blinkData.timer)
  if (document.title.startsWith(blinkData.mark)) {
    document.title = document.title.slice(blinkData.mark.length + 3) // 去掉 "✓ 训练完成 · "
  }
  blinkData = null
}

const onVisibilityChange = () => {
  if (!document.hidden) stopBlink()
}

// 训练状态轮询：记录 running → 消失即查询终态 → 提醒
const knownRunning = new Map() // run_id -> {project_name, model_name}
let trainingPollTimer = null

const notifyTrainDone = (run) => {
  const ok = run.status === 'completed'
  const who = run.project_name ? `工程「${run.project_name}」` : `run ${run.id}`
  const mark = ok ? '✓ 训练完成' : '✗ 训练失败'
  const title = `${ok ? '训练完成' : '训练失败'} · ${who}`
  const summary = ok
    ? `${run.model_name} · ${run.epochs} 轮 · mAP@50 ${run.final_map50 ? run.final_map50.toFixed(4) : '-'}`
    : `${run.model_name} · ${run.epochs} 轮 · 训练异常，请查看训练日志`

  if (document.hidden) {
    startBlink(mark)
    ok ? playDoneSound() : playFailSound()
  } else {
    ElNotification({
      title,
      message: summary,
      type: ok ? 'success' : 'error',
      duration: 8000,
    })
    ok ? playDoneSound() : playFailSound()
  }
}

const pollTraining = async () => {
  if (!notifyEnabled()) {
    knownRunning.clear()
    return
  }
  let active = []
  try {
    active = await trainApi.active()
  } catch (e) {
    return // 网络抖动跳过本轮
  }

  const activeIds = new Set(active.map((a) => a.run_id))
  // 之前 running、现在不在列表 → 查询终态
  const finishedIds = [...knownRunning.keys()].filter((id) => !activeIds.has(id))
  for (const id of finishedIds) {
    try {
      const run = await trainApi.getRun(id)
      if (run.status === 'completed' || run.status === 'failed') {
        notifyTrainDone(run)
      } else {
        knownRunning.set(id, {}) // 仍在运行（或未知），继续跟踪
      }
    } catch (e) {
      // 查询失败：保留跟踪，下轮再查
      knownRunning.set(id, {})
    }
  }

  // 更新本轮 running 集合
  const next = new Map()
  for (const a of active) {
    next.set(a.run_id, { project_name: a.project_name, model_name: a.model_name })
  }
  knownRunning.clear()
  for (const [k, v] of next) knownRunning.set(k, v)
}

onMounted(() => {
  window.addEventListener('visibilitychange', onVisibilityChange)
  window.addEventListener('pointerdown', unlockAudio)
  window.addEventListener('keydown', unlockAudio)
  trainingPollTimer = setInterval(pollTraining, 2500)
})

onUnmounted(() => {
  window.removeEventListener('visibilitychange', onVisibilityChange)
  window.removeEventListener('pointerdown', unlockAudio)
  window.removeEventListener('keydown', unlockAudio)
  if (trainingPollTimer) clearInterval(trainingPollTimer)
  stopBlink()
})

// 路由切换时标题由 router 重写，先停下闪烁避免覆盖
watch(() => route.fullPath, () => stopBlink())

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
