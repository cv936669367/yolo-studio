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

        <!-- 数据集筛选：全部 / Tr / Va / Te -->
        <div class="filter-chips split-chips">
          <div
            v-for="s in splitFilters"
            :key="s.value"
            class="chip"
            :class="{ active: splitFilter === s.value, [s.value]: true }"
            @click="changeSplitFilter(s.value)"
          >
            {{ s.label }}
            <span class="chip-count mono">{{ splitCount(s.value) }}</span>
          </div>
        </div>

        <!-- 标注状态筛选：全部 / 已标注 / 未标注 -->
        <div class="filter-chips anno-chips">
          <div
            v-for="a in annoStateFilters"
            :key="a.value"
            class="chip"
            :class="{ active: annoStateFilter === a.value }"
            @click="changeAnnoFilter(a.value)"
          >
            {{ a.label }}
            <span class="chip-count mono">{{ annoStateCount(a.value) }}</span>
          </div>
        </div>

        <span class="image-counter mono" v-if="viewImages.length">{{ currentIndex + 1 }} / {{ viewImages.length }}</span>
      </div>
      <div class="toolbar-center">
        <!-- 尺寸/标注数已由左侧 GROUP 与 CLASSES 统计展示，此处留空保持对称 -->
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

    <!-- Film strip（横向虚拟滚动：只渲染视口附近缩略图，适配上千图） -->
    <div
      v-if="viewImages.length"
      ref="stripRef"
      class="film-strip"
      @scroll.passive="onStripScroll"
    >
      <div class="strip-track" :style="{ width: viewImages.length * STRIP_STRIDE + 'px' }">
        <div
          v-for="it in visibleStripItems"
          :key="it.img.id"
          class="strip-item"
          :class="{ active: it.idx === currentIndex }"
          :style="{ left: it.idx * STRIP_STRIDE + 'px' }"
          @click="currentIndex = it.idx"
        >
          <img :src="it.img.file_path" :alt="it.img.original_name" loading="lazy" />
          <!-- 数据集划分标记（右上角） -->
          <span class="strip-split" :class="it.img.split">
            {{ it.img.split === 'train' ? 'Tr' : (it.img.split === 'val' ? 'Va' : 'Te') }}
          </span>
          <!-- 标注数（右下角） -->
          <span class="strip-badge mono">{{ it.img.annotation_count || 0 }}</span>
        </div>
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
              <span class="info-value mono">{{ currentIndex + 1 }} / {{ viewImages.length }}</span>
            </div>
          </div>
        </div>

        <!-- CLASSES -->
        <div class="panel-section">
          <div class="panel-title-row">
            <span class="panel-title">CLASSES</span>
            <span class="title-stat mono">标注 {{ annotations.length }}</span>
          </div>
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

        <!-- AUTO LABEL 自动标注（批量生成初稿） -->
        <div class="panel-section auto-label-panel">
          <div class="panel-title-row">
            <span class="panel-title">AUTO LABEL</span>
            <span class="title-stat mono">批量初稿</span>
          </div>

          <div class="al-field">
            <div class="al-label-row">
              <span class="al-label">标注模型</span>
              <span class="al-type-tag" :class="needSeg ? 'seg' : 'det'">
                {{ needSeg ? '实例分割' : '目标检测' }}
              </span>
            </div>
            <el-select
              v-model="alModel"
              size="small"
              class="al-select"
              placeholder="无可用模型"
              :disabled="alRunning || !alModelReady"
            >
              <el-option-group
                v-if="alRuns.length"
                :label="`本工程已训模型（${needSeg ? '实例分割' : '目标检测'}，类别一致）`"
              >
                <el-option
                  v-for="r in alRuns"
                  :key="'run-' + r.id"
                  :value="'run:' + r.id"
                  :label="`run ${r.id} · ${r.model_name} · mAP@50 ${r.final_map50 ? r.final_map50.toFixed(3) : '-'}`"
                />
              </el-option-group>
              <el-option-group
                v-if="alBaselines.length"
                :label="`官方基线 COCO · ${needSeg ? '分割' : '检测'}（已下载）`"
              >
                <el-option
                  v-for="m in alBaselines"
                  :key="'base-' + m.id"
                  :value="'base:' + m.id"
                  :label="`${m.name} · ${m.desc}`"
                />
              </el-option-group>
            </el-select>
          </div>

          <div class="al-field">
            <div class="al-label-row">
              <span class="al-label">置信度阈值</span>
              <span class="mono al-val">{{ alConf.toFixed(2) }}</span>
            </div>
            <el-slider
              v-model="alConf"
              :min="0.05"
              :max="0.95"
              :step="0.05"
              size="small"
              :disabled="alRunning"
            />
          </div>

          <div class="al-field">
            <div class="al-label">范围</div>
            <el-select v-model="alScope" size="small" :disabled="alRunning">
              <el-option value="unanno-all" :label="`全部未标注（${unannotatedAll} 张）`" :disabled="!unannotatedAll" />
              <el-option value="unanno-group" :label="`当前分组未标注（${unannotatedGroup} 张）`" :disabled="!unannotatedGroup" />
              <el-option value="current" label="仅当前图片（允许追加）" />
            </el-select>
          </div>

          <el-button
            v-if="!alRunning"
            type="primary"
            plain
            style="width: 100%;"
            :disabled="!alReady"
            @click="startAutoLabel"
          >
            <el-icon><MagicStick /></el-icon> 开始自动标注
          </el-button>
          <div v-else class="al-progress">
            <el-progress :percentage="alPercent" :stroke-width="6" :show-text="false" />
            <div class="al-progress-text mono">
              处理 {{ alProcessed }}/{{ alTotal }} · 已生成 {{ alCreated }} 个标注
            </div>
            <el-button
              size="small"
              type="danger"
              plain
              style="width: 100%;"
              @click="cancelAutoLabel"
              :loading="alCancelling"
            >停止</el-button>
          </div>

          <div v-if="alHint && !alRunning" class="al-hint">{{ alHint }}</div>
        </div>
      </aside>

      <!-- Center: canvas -->
      <div class="canvas-area" ref="canvasAreaRef">
        <div v-if="!currentImage" class="empty-canvas">
          <el-empty description="暂无图片" :image-size="80" />
        </div>
        <div
          v-else
          class="canvas-wrapper"
          :class="currentTool === 'select' ? 'pan-cursor' : ''"
          :style="{ transform: `translate(${canvasPan.x}px, ${canvasPan.y}px) scale(${zoom})` }"
          @mousedown="handleMouseDown"
          @mousemove="handleMouseMove"
          @mouseup="handleMouseUp"
          @mouseleave="handleMouseLeave"
        >
          <!-- 整图：常驻显示层（CSS contain 自适应画布，行为与旧版一致，永远是布局与坐标基准） -->
          <img
            ref="imageRef"
            :src="getImageUrl(currentImage)"
            @load="markPlainLoaded"
            @dblclick="handleDoubleClick"
            @contextmenu.prevent="handleRightClick($event)"
            draggable="false"
            class="annotation-image"
          />

          <!-- 大图放大后的高清瓦片增强层：覆盖在整图上（原像素→显示盒等比缩放），
               未加载区域透出底层整图，无闪烁/无坐标错位 -->
          <div v-if="showTileLayer" class="tile-layer" @dblclick.stop="handleDoubleClick">
            <div
              class="tile-inner"
              :style="{
                width: tileNatW + 'px',
                height: tileNatH + 'px',
                transform: `scale(${tileScale})`,
              }"
            >
              <img
                v-for="t in visibleTiles"
                :key="`${t.x}-${t.y}`"
                class="tile-img"
                :src="tileMeta.tile_prefix + t.x + '_' + t.y + '.jpg'"
                :style="{ left: t.left + 'px', top: t.top + 'px', width: t.width + 'px', height: t.height + 'px' }"
                draggable="false"
              />
            </div>
          </div>

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
                  data-handle
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
                  class="anno-vertex"
                  :transform="`translate(${toDisplayX(pt.x)}, ${toDisplayY(pt.y)})`"
                  @mousedown.stop.prevent="startVertexDrag(anno, vi)"
                >
                  <!-- 透明热区：扩大命中范围 -->
                  <circle r="9" fill="transparent" />
                  <circle r="4.5" fill="#fff" stroke="#1f5aff" stroke-width="1.8" />
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
              <!-- 橡皮筋预览线：最后一点 → 当前鼠标 -->
              <line
                v-if="polygonHover"
                :x1="toDisplayX(polygonPoints[polygonPoints.length - 1].x)"
                :y1="toDisplayY(polygonPoints[polygonPoints.length - 1].y)"
                :x2="toDisplayX(polygonHover.x)"
                :y2="toDisplayY(polygonHover.y)"
                stroke="#1f5aff"
                stroke-width="1.5"
                stroke-dasharray="3,3"
                opacity="0.8"
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
              <!-- 下一个点提示 -->
              <circle
                v-if="polygonHover"
                :cx="toDisplayX(polygonHover.x)"
                :cy="toDisplayY(polygonHover.y)"
                r="2.5"
                fill="none"
                stroke="#1f5aff"
                stroke-width="1.5"
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

        <!-- 多边形编辑提示（选中 polygon 标注） -->
        <div
          v-if="selectedAnno && selectedAnno.anno_type === 'polygon'"
          class="poly-edit-hint"
        >
          <el-icon :size="14"><EditPen /></el-icon>
          <span>多边形编辑：拖动<b>白色圆点</b>调整顶点，完成后点击空白处或按 Esc 退出</span>
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
          v-if="currentImage && viewImages.length > 1"
          class="nav-arrow left"
          :class="{ disabled: currentIndex === 0 }"
          @click="prevImage"
        >
          <el-icon :size="18"><ArrowLeftBold /></el-icon>
        </div>
        <div
          v-if="currentImage && viewImages.length > 1"
          class="nav-arrow right"
          :class="{ disabled: currentIndex >= viewImages.length - 1 }"
          @click="nextImage"
        >
          <el-icon :size="18"><ArrowRightBold /></el-icon>
        </div>

        <!-- Vertical tool bar (Roboflow style) -->
        <div class="vertical-toolbar">
          <el-tooltip
            v-for="t in toolButtons"
            :key="t.key"
            placement="left"
            :show-after="200"
            popper-class="tool-tip-popper"
          >
            <template #content>
              <div class="tt-box">
                <div class="tt-title">
                  <span>{{ t.title }}</span>
                  <kbd v-if="t.shortcut">{{ t.shortcut }}</kbd>
                  <el-tag v-if="t.badge" size="small" effect="dark" class="tt-badge">{{ t.badge }}</el-tag>
                </div>
                <div class="tt-desc">{{ t.desc }}</div>
                <div v-if="t.usage" class="tt-usage">{{ t.usage }}</div>
              </div>
            </template>
            <div
              class="tool-btn"
              :class="{
                active: currentTool === t.key,
                danger: t.danger,
                disabled: t.danger && t.disabledCheck && t.disabledCheck(),
              }"
              @click="t.action ? t.action() : selectTool(t.key)"
            >
              <el-icon :size="17"><component :is="t.icon" /></el-icon>
            </div>
          </el-tooltip>

          <div class="tool-sep"></div>

          <el-tooltip
            v-for="t in actionButtons"
            :key="t.key"
            placement="left"
            :show-after="200"
            popper-class="tool-tip-popper"
          >
            <template #content>
              <div class="tt-box">
                <div class="tt-title">
                  <span>{{ t.title }}</span>
                  <kbd v-if="t.shortcut">{{ t.shortcut }}</kbd>
                </div>
                <div class="tt-desc">{{ t.desc }}</div>
              </div>
            </template>
            <div
              class="tool-btn danger"
              :class="{ disabled: t.disabledCheck() }"
              @click="t.action()"
            >
              <el-icon :size="17"><component :is="t.icon" /></el-icon>
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
              <el-button
                v-if="anno.anno_type === 'polygon'"
                type="primary"
                link
                size="small"
                @click.stop="selectedId = anno.id"
              >
                <el-icon><EditPen /></el-icon>
              </el-button>
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
import { projectApi, imageApi, annotationApi, aiApi, trainApi } from '@/api'
import { getClassColor as classColor } from '@/utils/classColors'

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
const smartLoading = ref(false)

// ─── 垂直工具条按钮（含详细悬停说明）───
const toolButtons = [
  {
    key: 'select', icon: 'Pointer', shortcut: 'V', title: '选择 / 移动',
    desc: '点选标注进行编辑',
    usage: '· 拖动已选框：移动位置\n· 拖动选中矩形手柄：调整大小\n· 选中多边形后拖动圆点：调整顶点\n· 空白处拖拽：平移画布（抓取光标）',
  },
  {
    key: 'smart-box', icon: 'Crop', shortcut: 'D', title: '智能分割 · 框选',
    desc: 'SAM 自动分割，画框圈住目标生成精确轮廓标注',
    usage: '· 按住左键拖出矩形框圈住物体\n· 松开即分割并生成多边形轮廓标注\n· 需先下载 SAM 模型（约 375MB）',
    badge: 'SAM',
  },
  {
    key: 'smart-point', icon: 'MagicStick', shortcut: 'S', title: '智能分割 · 点选',
    desc: '点击物体加区域、右键排除区域，SAM 联动分割',
    usage: '· 左键点击：添加正点（扩大选中区域）\n· 右键点击：添加负点（挖除误选区域）\n· 回车 / ✓按钮：确认保存为多边形\n· Esc：取消本次会话',
    badge: 'SAM',
  },
  {
    key: 'rectangle', icon: 'FullScreen', shortcut: 'B', title: '矩形框',
    desc: '拖拽绘制矩形检测框（Bounding Box）',
    usage: '· 空白处按住左键拖拽绘制\n· 选中后拖动移动、拖 8 个手柄缩放',
  },
  {
    key: 'lasso', icon: 'Aim', shortcut: 'L', title: '套索',
    desc: 'PS 风格自由圈选，松手自动闭合',
    usage: '· 按住左键沿物体边缘自由绘制\n· 松开闭合 → 矩形工程转外接框 / 多边形工程存自由轮廓',
  },
  {
    key: 'polygon', icon: 'Edit', shortcut: 'P', title: '多边形',
    desc: '逐点描出多边形轮廓',
    usage: '· 每次点击添加一个顶点（有橡皮筋预览线）\n· 双击闭合完成\n· 选中后点列表「编辑」可拖动顶点微调',
  },
]

const actionButtons = [
  {
    key: 'delete', icon: 'Delete', shortcut: 'Delete', title: '删除选中标注',
    desc: '删除当前选中的标注（支持 Ctrl+Z 撤销）',
    disabledCheck: () => !selectedAnno.value,
    action: () => deleteSelected(),
  },
  {
    key: 'clear', icon: 'DeleteFilled', title: '清除全部标注',
    desc: '删除当前图片上的全部标注（有二次确认）',
    disabledCheck: () => annotations.value.length === 0,
    action: () => clearAllAnnotations(),
  },
]

// ─── 筛选（顶部切换：数据集划分 + 标注状态）───
const splitFilter = ref('all')
const annoStateFilter = ref('all')

const splitFilters = [
  { label: '全部', value: 'all' },
  { label: 'Tr 训练', value: 'train' },
  { label: 'Va 验证', value: 'val' },
  { label: 'Te 测试', value: 'test' },
]
const annoStateFilters = [
  { label: '全部标注', value: 'all' },
  { label: '已标注', value: 'annotated' },
  { label: '未标注', value: 'unannotated' },
]

// 当前可导航图片 = 组合筛选结果
const viewImages = computed(() => {
  let list = images.value
  if (splitFilter.value !== 'all') {
    list = list.filter(i => i.split === splitFilter.value)
  }
  if (annoStateFilter.value === 'annotated') {
    list = list.filter(i => i.annotation_count > 0)
  } else if (annoStateFilter.value === 'unannotated') {
    list = list.filter(i => !(i.annotation_count > 0))
  }
  return list
})

const splitCount = (v) => (v === 'all' ? images.value.length : images.value.filter(i => i.split === v).length)
const annoStateCount = (v) => {
  let list = images.value
  if (splitFilter.value !== 'all') list = list.filter(i => i.split === splitFilter.value)
  if (v === 'annotated') return list.filter(i => i.annotation_count > 0).length
  if (v === 'unannotated') return list.filter(i => !(i.annotation_count > 0)).length
  return list.length
}

// 切换数据集筛选：保留当前图（若在新列表），否则跳第一个
const changeSplitFilter = (v) => {
  const curId = currentImage.value?.id
  splitFilter.value = v
  relocate(curId)
}

// 切换标注状态筛选
const changeAnnoFilter = (v) => {
  const curId = currentImage.value?.id
  annoStateFilter.value = v
  relocate(curId)
}

// 定位到指定图（若在筛选结果中），否则第一个；空列表 -1
const relocate = (targetId) => {
  if (targetId) {
    const idx = viewImages.value.findIndex(i => i.id === targetId)
    if (idx >= 0) { currentIndex.value = idx; return }
  }
  currentIndex.value = viewImages.value.length ? 0 : -1
}

// ─── Film strip 横向虚拟滚动 ─────────────────────────────
const STRIP_STRIDE = 70 // item 64px + 6px 间距（与 CSS 保持同步）
const STRIP_BUFFER = 5
const stripRef = ref(null)
const stripScroll = ref(0)
const stripViewW = ref(600)
let stripResizeObs = null

const onStripScroll = () => {
  stripScroll.value = stripRef.value?.scrollLeft || 0
}

// 渲染窗口：完全跟随 scrollLeft（用户拖动滚动条/横向滑屏时逐段加载）。
// 不要把窗口锚定回 currentIndex —— 否则手动向右浏览时会被强制拉回当前图，
// 表现为「横向滚动不加载」。
// 「当前项可见」由 ensureStripVisible 负责：任何 currentIndex 变化的入口
// （点击缩略图/键盘/翻页/筛选跳转）都会程序滚动并把 scrollLeft 同步进 ref，
// 渲染窗口随之包含当前项。
const visibleStripItems = computed(() => {
  const n = viewImages.value.length
  if (!n) return []
  const viewCount = Math.max(1, Math.ceil(stripViewW.value / STRIP_STRIDE))
  const count = viewCount + STRIP_BUFFER * 2
  const first = Math.max(0, Math.floor(stripScroll.value / STRIP_STRIDE) - STRIP_BUFFER)
  const last = Math.min(n, first + count)
  const out = []
  for (let i = first; i < last; i++) out.push({ img: viewImages.value[i], idx: i })
  return out
})

// 当前图滑出可视区时滚回；滚动后立即把 scrollLeft 同步进 ref，
// 保证同一帧渲染窗口就包含当前项（scroll 事件是异步派发的，不能等它）
const ensureStripVisible = (idx) => {
  const el = stripRef.value
  if (!el || idx < 0) return
  const left = idx * STRIP_STRIDE
  const right = left + STRIP_STRIDE
  if (left < el.scrollLeft) {
    el.scrollLeft = Math.max(0, left - 8)
  } else if (right > el.scrollLeft + el.clientWidth) {
    el.scrollLeft = Math.max(0, right - el.clientWidth + 8)
  }
  stripScroll.value = el.scrollLeft // 同步（scroll 事件随后也会再触发，幂等）
}

// 挂载缩略条宽度观测（film-strip 随图片异步加载后才出现，需兜底补挂）
const ensureStripObserver = () => {
  if (!stripRef.value) return
  stripViewW.value = stripRef.value.clientWidth
  if (!stripResizeObs) {
    stripResizeObs = new ResizeObserver(() => {
      stripViewW.value = stripRef.value?.clientWidth || stripViewW.value
    })
    stripResizeObs.observe(stripRef.value)
  }
}

// ─── 超大图高清瓦片（增强叠加层，不替代整图显示）────────
// 原则：
//  1. 整图 <img> 常驻（CSS contain 自适应画布 → 任何图打开即完整可见，行为同旧版）
//  2. 只有「足够大的图」且用户放大 zoom>1 时，才在整图之上叠加高清瓦片层；
//     瓦片层按原像素等比缩放到 img 显示盒（transform scale），与 overlay 坐标完全一致，
//     未加载区域透出底层整图 → 无黑屏、无闪烁、无坐标错位
//  3. 中低分辨率图（如手机竖图）不触发瓦片，永远走整图
const TILE_MIN_SIDE = 5500 // 长边 ≥5500px 才算超大图（与后端 TILE_THRESHOLD 一致）
const tileMeta = ref(null)         // tile-info 清单（后台预取，不阻塞显示）
const tileInfoCache = new Map()    // imageId → meta（避免重复请求）
const visibleTiles = ref([])
const tileScale = ref(0)           // 原像素 → 显示盒 等比缩放系数
let canvasResizeObs = null

// 瓦片层只在「超大图 + 清单就绪 + 放大 >100%」时叠加
const showTileLayer = computed(() =>
  tileMeta.value?.tiled === true && zoom.value > 1
)
const tileNatW = computed(() => tileMeta.value?.width || 0)
const tileNatH = computed(() => tileMeta.value?.height || 0)

// 整图 <img> 解码完成：记录显示盒尺寸（overlay 坐标基准）并解锁标注叠加层
const markPlainLoaded = () => {
  const img = imageRef.value
  if (!img || !currentImage.value) return
  imageWidth.value = img.clientWidth || currentImage.value.width || 0
  imageHeight.value = img.clientHeight || currentImage.value.height || 0
  imageLoaded.value = true
}

// 缓存命中等情况下 load 事件可能极快/已 complete → 手动补一次同步判定
const syncPlainLoadedIfComplete = () => {
  nextTick(() => {
    const img = imageRef.value
    if (img && img.complete && !imageLoaded.value && currentImage.value) {
      markPlainLoaded()
    }
  })
}

// 计算当前视口内的瓦片集合（图素坐标，左上原点）并同步缩放系数
const updateVisibleTiles = () => {
  const meta = tileMeta.value
  const img = imageRef.value
  if (!meta || !meta.tiled || zoom.value <= 1 || !img || !canvasAreaRef.value) {
    visibleTiles.value = []
    return
  }
  // img（整图）始终是布局/坐标基准；getBoundingClientRect 已含 wrapper 的 zoom/pan 变换
  const view = canvasAreaRef.value.getBoundingClientRect()
  const layer = img.getBoundingClientRect()
  if (!layer.width || !layer.height) {
    visibleTiles.value = []
    return
  }
  // 瓦片 inner 的缩放必须用「不含 zoom 的布局宽」(clientWidth)，
  // 因为 inner 与整图同处 wrapper 内、还会被 wrapper 的 transform 再放大一次
  tileScale.value = img.clientWidth / meta.width
  const sx = meta.width / layer.width   // 屏幕→原图像素
  const sy = meta.height / layer.height
  const pad = 1
  const x0 = Math.max(0, Math.floor(((view.left - layer.left) * sx - pad * meta.tile_size) / meta.tile_size))
  const x1 = Math.min(meta.cols, Math.ceil(((view.right - layer.left) * sx + pad * meta.tile_size) / meta.tile_size))
  const y0 = Math.max(0, Math.floor(((view.top - layer.top) * sy - pad * meta.tile_size) / meta.tile_size))
  const y1 = Math.min(meta.rows, Math.ceil(((view.bottom - layer.top) * sy + pad * meta.tile_size) / meta.tile_size))
  const out = []
  for (let ty = y0; ty < y1; ty++) {
    for (let tx = x0; tx < x1; tx++) {
      out.push({
        x: tx,
        y: ty,
        left: tx * meta.tile_size,
        top: ty * meta.tile_size,
        width: Math.min(meta.tile_size, meta.width - tx * meta.tile_size),
        height: Math.min(meta.tile_size, meta.height - ty * meta.tile_size),
      })
    }
  }
  visibleTiles.value = out
}

// 后台预取瓦片清单（不改变显示）
const fetchTileMeta = async () => {
  const img = currentImage.value
  if (!img) return
  const big = (img.width && img.height && Math.max(img.width, img.height) >= TILE_MIN_SIDE)
  if (!big) return
  try {
    let meta = tileInfoCache.get(img.id)
    if (!meta) {
      meta = await imageApi.tileInfo(img.id)
      if (meta && meta.tiled) tileInfoCache.set(img.id, meta)
    }
    if (!meta || meta.tiled !== true) return
    tileMeta.value = meta
    if (showTileLayer.value) updateVisibleTiles()
  } catch (e) {
    // 瓦片不可用则保持整图直显
  }
}

// 切换图片时重置瓦片状态并后台预取
const resetTileForImage = () => {
  tileMeta.value = null
  visibleTiles.value = []
  tileScale.value = 0
}

// Tool state
const currentTool = ref('rectangle')
const selectedClass = ref('')
const zoom = ref(1)
const imageLoaded = ref(false)

// 画布平移（select 工具空白拖拽）
const canvasPan = ref({ x: 0, y: 0 })
const panning = ref(false)
const panStart = ref(null) // {cx, cy, px, py}
const imageWidth = ref(640)
const imageHeight = ref(480)

// 平移/缩放时重算可见瓦片（仅瓦片层激活时渲染；否则清空）
// 注意：watcher 默认在 DOM 提交前执行，此时 transform 还是旧值；
// 需 nextTick 等新 scale 应用后再按最新矩形计算可见块
watch([zoom, canvasPan], async () => {
  if (!showTileLayer.value) {
    visibleTiles.value = []
    return
  }
  await nextTick()
  updateVisibleTiles()
})

// Selection & editing
const selectedId = ref(null)
const editing = ref(null) // {type:'move'|'resize'|'vertex', anno, handle?, dx?, dy?, orig?}

// Drawing state
const isDrawing = ref(false)
const startPos = ref(null)
const drawingRect = ref(null)
const polygonPoints = ref([])
const polygonHover = ref(null) // 多边形绘制时鼠标预览位置（归一化）

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
const currentImage = computed(() => viewImages.value[currentIndex.value])
const canUndo = computed(() => historyStack.value.length > 0)
const canRedo = computed(() => redoStack.value.length > 0)

// ─── Colors ──────────────────────────────────────────────
// 统一取色：工程自定义 class_colors 优先 → classes 顺序调色板 → 名称哈希兜底
const getClassColor = (className) =>
  classColor(className, project.value.class_colors || {}, project.value.classes || [])

const classColorFill = (className) => {
  const c = getClassColor(className)
  // 半透明填充（Roboflow 风格）
  return `${c}26` // 15% alpha
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
    if (targetId) {
      const idx = viewImages.value.findIndex(i => i.id === targetId)
      if (idx >= 0) { currentIndex.value = idx; return }
    }
    currentIndex.value = viewImages.value.length ? 0 : -1
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
const nextImage = () => { if (currentIndex.value < viewImages.value.length - 1) currentIndex.value++ }

const fitZoom = () => {
  const area = canvasAreaRef.value
  if (!area) return
  let W = 0
  let H = 0
  if (tileMeta.value?.tiled) {
    W = tileMeta.value.width
    H = tileMeta.value.height
  } else {
    const img = imageRef.value
    if (!img) return
    W = img.naturalWidth || 0
    H = img.naturalHeight || 0
  }
  if (!W || !H) return
  const availW = area.clientWidth - 40
  const availH = area.clientHeight - 40
  zoom.value = Math.min(1, Math.min(availW / W, availH / H))
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

  // select 工具：空白拖拽 = 平移画布（pan）
  if (currentTool.value === 'select') {
    panning.value = true
    panStart.value = {
      cx: e.clientX, cy: e.clientY,
      px: canvasPan.value.x, py: canvasPan.value.y,
    }
    return
  }

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

  // 画布平移（select 工具空白拖拽）
  if (panning.value && panStart.value) {
    canvasPan.value = {
      x: panStart.value.px + (e.clientX - panStart.value.cx),
      y: panStart.value.py + (e.clientY - panStart.value.cy),
    }
    return
  }

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

  // 多边形绘制：橡皮筋预览线（记录鼠标位置，等下一次点击）
  if (currentTool.value === 'polygon' && polygonPoints.value.length > 0) {
    polygonHover.value = pos
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
  // 平移结束
  if (panning.value) {
    panning.value = false
    panStart.value = null
    return
  }

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
  if (panning.value) {
    panning.value = false
    panStart.value = null
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

// 更新标注到后端（需完整字段，否则 422）
const updateAnno = async (anno) => {
  try {
    const data = {
      image_id: anno.image_id ?? currentImage.value?.id,
      anno_type: anno.anno_type,
      class_name: anno.class_name,
      bbox: anno.bbox || null,
      points: anno.points || null,
    }
    await annotationApi.update(anno.id, data)
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

// ─── Auto-Label 自动标注（批量初稿）─────────────────────
// 模型来源：本工程已完成 run（best.pt）或任务匹配的已下载基线
// 任务匹配是硬约束：polygon 工程只允许 实例分割(segment) 模型（产出多边形），
//                   rectangle 工程只允许 目标检测(detect) 模型（产出矩形框）
const alRuns = ref([])
const alBaselines = ref([])
const alModel = ref('')           // 'run:5' | 'base:yolov8s-seg'
const alConf = ref(0.25)
const alScope = ref('unanno-all') // 'unanno-all' | 'unanno-group' | 'current'
const alRunning = ref(false)
const alCancelling = ref(false)
const alStatus = ref(null)
const alTimer = ref(null)

// 工程标注类型 → 所需模型任务（与后端 auto_label 校验规则一致）
const needSeg = computed(() => project.value.anno_type === 'polygon')

// 模型名 → 任务类型（官方 run 名带 -seg 后缀；与后端 model_task 同规则）
const modelTaskOf = (name) => (String(name || '').toLowerCase().endsWith('-seg') ? 'segment' : 'detect')

// 当前工程允许的模型任务
const requiredTask = computed(() => (needSeg.value ? 'segment' : 'detect'))

// 全部 / 当前分组 未标注数量
const unannotatedAll = computed(() => images.value.filter(i => !(i.annotation_count > 0)).length)
const unannotatedGroup = computed(() => {
  const sp = splitFilter.value
  return images.value.filter(i => (sp === 'all' || i.split === sp) && !(i.annotation_count > 0)).length
})

// 可用模型数量不足时的提示
const alModelReady = computed(() => alRuns.value.length + alBaselines.value.length > 0)
const alHint = computed(() => {
  if (!project.value.anno_type) return '工程类型加载中，请稍候...'
  if (!alModelReady.value) {
    const t = needSeg.value ? '实例分割' : '目标检测'
    return `暂无${t}模型：需先完成一次训练或下载 ${t === '实例分割' ? 'YOLOv8s-seg / YOLO11s-seg' : 'YOLOv8s / YOLO11s'} 官方基线`
  }
  if (!alModel.value) return '请选择标注模型'
  if (alScope.value === 'current') return ''
  const n = alScope.value === 'unanno-all' ? unannotatedAll.value : unannotatedGroup.value
  if (n === 0) return '当前范围没有未标注图片，可切到「仅当前图片」追加初稿'
  return ''
})
// 启动条件：有模型 + 范围有目标（当前图片范围恒可执行）
const alReady = computed(() => {
  if (!alModel.value || alRunning.value) return false
  if (alScope.value === 'current') return !!currentImage.value
  return alScope.value === 'unanno-all' ? unannotatedAll.value > 0 : unannotatedGroup.value > 0
})

const alTotal = computed(() => alStatus.value?.total ?? 0)
const alProcessed = computed(() => alStatus.value?.processed ?? 0)
const alCreated = computed(() => alStatus.value?.created ?? 0)
const alPercent = computed(() => {
  const t = alTotal.value
  return t > 0 ? Math.min(100, Math.round(alProcessed.value / t * 100)) : 0
})

// 加载自动标注可用模型（只保留与工程标注类型匹配的模型，杜绝跨任务错配）
const loadAutoLabelModels = async () => {
  // 工程类型未知 → 绝不猜测任务，等工程加载完由 watch 重载
  if (!project.value.anno_type) return
  const task = requiredTask.value
  try {
    const runs = await trainApi.listRuns(projectId.value)
    alRuns.value = (runs || []).filter(r =>
      r.status === 'completed' && r.has_weights && modelTaskOf(r.model_name) === task)
  } catch (e) {
    alRuns.value = []
  }
  try {
    const models = await trainApi.listModels()
    alBaselines.value = (models || []).filter(m =>
      m.downloaded && m.task === task)
  } catch (e) {
    alBaselines.value = []
  }
  // 默认：优先本工程已训 run，其次基线；并校验旧选择是否仍合法
  if (!alRunning.value) {
    const valid = [...alRuns.value.map(r => `run:${r.id}`), ...alBaselines.value.map(m => `base:${m.id}`)]
    if (valid.includes(alModel.value)) return
    if (alRuns.value.length) alModel.value = `run:${alRuns.value[0].id}`
    else if (alBaselines.value.length) alModel.value = `base:${alBaselines.value[0].id}`
    else alModel.value = ''
  }
}

// 工程信息就绪/变更后重载自动标注模型源
watch(() => project.value.anno_type, (v) => {
  if (v) loadAutoLabelModels()
})

const startAutoLabel = async () => {
  if (!alReady.value) return
  const [kind, val] = alModel.value.split(':')
  const params = {
    conf: alConf.value,
    iou: 0.45,
    only_unannotated: true,
  }
  if (kind === 'run') params.run_id = parseInt(val)
  else params.model_name = val

  if (alScope.value === 'current') {
    params.only_unannotated = false
    params.image_ids = String(currentImage.value.id)
  } else if (alScope.value === 'unanno-group' && splitFilter.value !== 'all') {
    params.split = splitFilter.value
  }

  try {
    const res = await aiApi.autoLabel(projectId.value, params)
    ElMessage.info(res.message || '自动标注已启动')
    alRunning.value = true
    alCancelling.value = false
    alStatus.value = { total: 0, processed: 0, created: 0, skipped_annotated: 0 }
    alTimer.value = setInterval(pollAutoLabel, 1000)
  } catch (e) {}
}

const pollAutoLabel = async () => {
  try {
    const st = await aiApi.autoLabelStatus(projectId.value)
    alStatus.value = st
    if (!st.running && ['done', 'cancelled', 'error'].includes(st.status)) {
      stopAutoLabelPoll()
      alRunning.value = false
      if (st.status === 'error') ElMessage.error(st.error || '自动标注失败')
      else ElMessage.success(st.message || '自动标注完成')
      // 刷新图片标注数并保留当前浏览位置
      const curId = currentImage.value?.id
      await loadImages()
      if (curId) relocate(curId)
      await loadAnnotations()
    }
  } catch (e) {
    stopAutoLabelPoll()
    alRunning.value = false
  }
}

const cancelAutoLabel = async () => {
  alCancelling.value = true
  try {
    const res = await aiApi.autoLabelCancel(projectId.value)
    ElMessage.info(res.message || '正在停止...')
  } catch (e) {
    alCancelling.value = false
  }
}

const stopAutoLabelPoll = () => {
  if (alTimer.value) {
    clearInterval(alTimer.value)
    alTimer.value = null
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
  canvasPan.value = { x: 0, y: 0 }
  imageLoaded.value = false
  tileMeta.value = null
  visibleTiles.value = []

  if (currentImage.value) {
    await loadAnnotations()
    resetTileForImage()          // 清空上一张的瓦片状态
    fetchTileMeta()              // 后台预取（不阻塞整图显示）
    await nextTick()
    syncPlainLoadedIfComplete()  // 缓存图同步补一次加载判定
    ensureStripVisible(currentIndex.value)
  }
}, { immediate: true })

// 通过键盘/翻页切换图片时保持当前项在缩略条可视范围
watch(currentIndex, (idx) => {
  if (viewImages.value.length) ensureStripVisible(idx)
})

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
  loadAutoLabelModels()
  window.addEventListener('keydown', handleKeydown)

  // 视口尺寸观测：缩略条宽度 / 画布尺寸（瓦片视口变化）
  const observeResize = () => {
    ensureStripObserver() // film-strip 此时可能尚未渲染（图片异步加载），加载后由下方 watch 兜底补挂
    if (canvasAreaRef.value) {
      canvasResizeObs = new ResizeObserver(() => {
        if (showTileLayer.value) updateVisibleTiles()
      })
      canvasResizeObs.observe(canvasAreaRef.value)
    }
  }
  nextTick(observeResize)
  // film-strip 随图片列表出现 → 出现后再补挂宽度观测
  watch(() => viewImages.value.length, () => {
    nextTick(ensureStripObserver)
  })
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  stopSamPolling()
  stopAutoLabelPoll()
  stripResizeObs?.disconnect()
  canvasResizeObs?.disconnect()
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

    .filter-chips {
      display: flex;
      gap: 2px;

      .chip {
        padding: 4px 10px;
        font-size: 12px;
        color: var(--text-2);
        cursor: pointer;
        border: 1px solid var(--border);
        border-radius: 3px;
        display: flex;
        align-items: center;
        gap: 5px;
        transition: all 0.15s;
        background: var(--bg-card);

        &:hover {
          border-color: var(--brand);
          color: var(--brand);
        }

        &.active {
          border-color: var(--brand);
          color: #fff;
          background: var(--brand);
          font-weight: 600;

          .chip-count { color: rgba(255, 255, 255, 0.85); }
        }

        .chip-count {
          font-size: 10.5px;
          color: var(--text-3);
        }
      }

      // Tr/Va/Te 色点：非激活时颜色标识
      &.split-chips .chip {
        &.train { border-left: 2px solid #1f5aff; }
        &.val { border-left: 2px solid #e6a23c; }
        &.test { border-left: 2px solid #0f9d58; }

        &.train.active { background: #1f5aff; border-left-color: #1f5aff; }
        &.val.active { background: #e6a23c; border-left-color: #e6a23c; }
        &.test.active { background: #0f9d58; border-left-color: #0f9d58; }
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
    contain: layout style; // 隔离自身布局，避免影响其他区域

    // 暗黑下缩略图底更贴近卡片
    html.dark & { background: var(--bg-fill); }

    .strip-item {
      content-visibility: auto;
      contain-intrinsic-size: 64px 48px;
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

      // 数据集划分标记（右上角）
      .strip-split {
        position: absolute;
        top: 1px;
        right: 1px;
        font-size: 8.5px;
        font-weight: 700;
        padding: 1px 4px;
        border-radius: 2px;
        color: #fff;
        letter-spacing: 0.3px;

        &.train { background: #1f5aff; }
        &.val { background: #e6a23c; }
        &.test { background: #0f9d58; }
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

      .panel-title-row {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        margin-bottom: 8px;

        .panel-title {
          margin-bottom: 0;
        }

        .title-stat {
          font-size: 10.5px;
          color: var(--text-3);
          background: var(--bg-fill);
          padding: 1px 7px;
          border-radius: 8px;
        }
      }

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
      contain: layout style; // 隔离：避免画布布局/样式计算影响全局（主题/折叠时）
      transform: translateZ(0); // 独立合成层：主题切换时图片/标注层不参与整页重绘

      &.pan-cursor {
        cursor: grab;

        &:active { cursor: grabbing; }
      }

      .annotation-image {
        max-width: 100%;
        max-height: calc(100vh - 250px); // 略小于画布可用高度，保证整图完整可见（不裁边）
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
        will-change: transform;

        .anno-shape {
          pointer-events: none;
        }

        .anno-shape g[data-handle],
        .anno-shape g.anno-vertex {
          pointer-events: auto;
          cursor: move;
        }

        .anno-shape g.anno-vertex circle {
          transition: r 0.12s;
        }

        .anno-shape g.anno-vertex:hover circle {
          r: 6;
          stroke-width: 2;
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

    // ─── 多边形编辑提示 ───
    .poly-edit-hint {
      position: absolute;
      top: 12px;
      left: 50%;
      transform: translateX(-50%);
      display: flex;
      align-items: center;
      gap: 7px;
      background: rgba(20, 22, 26, 0.85);
      color: #d5d9e0;
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 5px;
      padding: 6px 14px;
      font-size: 12px;
      z-index: 15;
      white-space: nowrap;

      b { color: #fff; }

      .el-icon { color: #8fabff; }
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
        position: relative;
        width: 36px;
        height: 36px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 6px;
        color: #b8bdc7;
        cursor: pointer;
        transition: background 0.15s, color 0.15s, transform 0.1s;

        .el-icon {
          transition: transform 0.15s;
        }

        &:hover {
          background: rgba(255, 255, 255, 0.12);
          color: #fff;

          .el-icon { transform: scale(1.15); }
        }

        // 激活：左侧指示条 + 蓝色高亮
        &.active {
          background: linear-gradient(135deg, #1f5aff, #4c78ff);
          color: #fff;
          box-shadow: 0 2px 8px rgba(31, 90, 255, 0.35);

          &::before {
            content: '';
            position: absolute;
            left: -4px;
            top: 8px;
            bottom: 8px;
            width: 3px;
            border-radius: 2px;
            background: #6d9bff;
          }
        }

        &.danger:hover:not(.disabled) {
          background: rgba(229, 72, 77, 0.28);
          color: #ff8a85;
          box-shadow: 0 2px 8px rgba(229, 72, 77, 0.25);

          .el-icon { transform: scale(1.12); }
        }

        &.disabled {
          opacity: 0.32;
          cursor: not-allowed;

          &:hover {
            background: transparent;
            color: #b8bdc7;

            .el-icon { transform: none; }
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

// ─── AUTO LABEL 自动标注面板 ──────────────────────────────
.auto-label-panel {
  .al-field {
    margin-bottom: 12px;

    .al-select { width: 100%; }

    .al-label {
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.4px;
      color: var(--text-3);
      text-transform: uppercase;
      margin-bottom: 5px;
    }

    .al-label-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 2px;
    }

    .al-val {
      font-size: 11px;
      color: var(--brand);
    }

    // 工程所需模型任务徽标
    .al-type-tag {
      font-size: 10px;
      font-weight: 600;
      line-height: 1;
      padding: 3px 6px;
      border-radius: 3px;

      &.seg {
        color: #0f9d58;
        background: rgba(15, 157, 88, 0.12);
        border: 1px solid rgba(15, 157, 88, 0.35);
      }

      &.det {
        color: #1f5aff;
        background: rgba(31, 90, 255, 0.1);
        border: 1px solid rgba(31, 90, 255, 0.32);
      }
    }
  }

  .al-progress {
    display: flex;
    flex-direction: column;
    gap: 6px;

    .al-progress-text {
      font-size: 11px;
      color: var(--text-2);
      text-align: center;
    }
  }

  .al-hint {
    margin-top: 8px;
    font-size: 11px;
    line-height: 1.6;
    color: #d97706;
    background: rgba(217, 119, 6, 0.08);
    border: 1px solid rgba(217, 119, 6, 0.25);
    border-radius: 4px;
    padding: 6px 8px;
  }
}

// ─── Film strip 虚拟滚动（绝对定位轨道；同特异性下后声明覆盖原 flex 布局）───
.annotate-page .film-strip {
  .strip-track {
    position: relative;
    height: 48px;
    flex: 0 0 auto;
  }

  .strip-item {
    position: absolute;
    top: 0;
    left: 0;
    margin: 0;
    flex: none;
  }
}

// ─── 超大图瓦片增强层（叠加在整图之上，不拦截交互）──────
.tile-layer {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none; // 所有鼠标事件透传给 wrapper/整图（标注交互不受影响）

  .tile-inner {
    position: absolute;
    top: 0;
    left: 0;
    transform-origin: 0 0;
    will-change: transform;
  }

  .tile-img {
    position: absolute;
    display: block;
  }

  .tile-loading {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    color: #aeb4c0;
    font-size: 12px;
    background: rgba(18, 20, 26, 0.35);
    z-index: 3;
  }
}

.tile-wait {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 260px;
  padding: 22px 20px;
  color: #aeb4c0;
  font-size: 13px;
  background: #1b1f28;
  border: 1px solid #2a2f3a;
  border-radius: 6px;
}
</style>
