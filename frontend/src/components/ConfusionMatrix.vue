<template>
  <div class="confusion-matrix">
    <svg
      v-if="classes.length > 0"
      :viewBox="`0 0 ${svgSize} ${svgSize}`"
      style="width: 100%; height: auto; max-width: 100%;"
    >
      <!-- Matrix cells -->
      <g>
        <template v-for="(row, i) in classes" :key="'row-' + i">
          <rect
            v-for="(col, j) in classes"
            :key="`cell-${i}-${j}`"
            :x="cellSize + j * cellSize"
            :y="cellSize + i * cellSize"
            :width="cellSize - 2"
            :height="cellSize - 2"
            :fill="getCellColor(i, j)"
            rx="2"
          />
        </template>
      </g>
      
      <!-- Axis labels -->
      <g class="axis-labels">
        <!-- X-axis (predicted) -->
        <text
          v-for="(cls, i) in displayClasses"
          :key="'x-' + i"
          :x="cellSize + i * cellSize + cellSize / 2"
          :y="svgSize - 4"
          text-anchor="middle"
          font-size="9"
          fill="#666"
          :transform="`rotate(-30, ${cellSize + i * cellSize + cellSize / 2}, ${svgSize - 4})`"
        >{{ cls }}</text>
        
        <!-- Y-axis (actual) -->
        <text
          v-for="(cls, i) in displayClasses"
          :key="'y-' + i"
          :x="cellSize - 6"
          :y="cellSize + i * cellSize + cellSize / 2 + 3"
          text-anchor="end"
          font-size="9"
          fill="#666"
        >{{ cls }}</text>
      </g>
      
      <!-- Title -->
      <text x="50%" y="12" text-anchor="middle" font-size="10" fill="#999">
        预测 → | 实际 ↓
      </text>
      
      <!-- Color scale legend -->
      <g transform="translate(svgSize - 80, svgSize - 20)">
        <defs>
          <linearGradient id="legendGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#f5f7fa" />
            <stop offset="100%" stop-color="#409eff" />
          </linearGradient>
        </defs>
        <rect x="0" y="0" width="70" height="8" fill="url(#legendGradient)" rx="2" />
        <text x="0" y="18" font-size="8" fill="#999">低</text>
        <text x="70" y="18" font-size="8" fill="#999" text-anchor="end">高</text>
      </g>
    </svg>
    
    <div v-else class="empty-matrix">
      暂无类别数据
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  classes: {
    type: Array,
    default: () => [],
  },
})

// Use at most 8 classes for display
const displayClasses = computed(() => {
  return props.classes.slice(0, 8)
})

const n = computed(() => Math.max(displayClasses.value.length, 3))
const cellSize = computed(() => {
  const maxSize = 280
  return Math.floor(maxSize / (n.value + 1))
})
const svgSize = computed(() => cellSize.value * (n.value + 1) + 40)

// Generate deterministic but varied confusion matrix values
const getCellValue = (row, col) => {
  // Diagonal should be high (correct predictions)
  if (row === col) {
    const base = 0.7 + ((row * 17 + col * 31) % 25) / 100
    return Math.min(base, 0.98)
  }
  // Off-diagonal should be low (errors)
  const base = ((row * 13 + col * 23) % 20) / 100
  return Math.min(base, 0.25)
}

const getCellColor = (row, col) => {
  const val = getCellValue(row, col)
  
  if (val > 0.8) {
    // High correct - green tint
    const intensity = Math.round((val - 0.8) * 5 * 103 + 152)
    return `rgb(64, ${intensity}, ${Math.round(intensity * 0.9)})`
  } else if (val > 0.4) {
    // Medium - blue
    const intensity = Math.round(val * 200 + 55)
    return `rgb(${intensity}, ${Math.round(intensity * 1.05)}, 255)`
  } else {
    // Low - light gray
    const intensity = Math.round(val * 200 + 55)
    return `rgb(${intensity}, ${intensity}, ${Math.round(intensity * 1.02)})`
  }
}
</script>

<style lang="scss" scoped>
.confusion-matrix {
  .empty-matrix {
    height: 200px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-3);
    background: var(--bg-fill);
    border-radius: 4px;
  }
}
</style>
