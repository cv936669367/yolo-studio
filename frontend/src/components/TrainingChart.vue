<template>
  <div class="training-chart">
    <svg v-if="hasData" :viewBox="`0 0 ${svgWidth} ${svgHeight}`" style="width: 100%; height: auto;">
      <!-- Grid lines -->
      <g class="grid">
        <line
          v-for="(val, i) in gridLines"
          :key="'h-' + i"
          x1="40" :y1="yScale(val)" x2="380" :y2="yScale(val)"
          stroke="#f0f0f0" stroke-width="1"
        />
        <line
          v-for="(val, i) in gridLines"
          :key="'v-' + i"
          :x1="xScale(i / (gridLines.length - 1))" y1="20"
          :x2="xScale(i / (gridLines.length - 1))" y2="160"
          stroke="#f0f0f0" stroke-width="1"
        />
      </g>
      
      <!-- Y-axis labels -->
      <g class="y-labels">
        <text
          v-for="(val, i) in gridLines"
          :key="'yl-' + i"
          x="35" :y="yScale(val) + 4"
          text-anchor="end"
          font-size="10"
          fill="#999"
        >{{ val }}</text>
      </g>
      
      <!-- X-axis label -->
      <text x="210" y="185" text-anchor="middle" font-size="11" fill="#666">Epoch</text>
      
      <!-- Y-axis label -->
      <text x="12" y="90" text-anchor="middle" font-size="11" fill="#666"
        transform="rotate(-90, 12, 90)">mAP</text>
      
      <!-- mAP@50 line -->
      <polyline
        :points="map50Points"
        fill="none"
        stroke="#409eff"
        stroke-width="2"
        stroke-linejoin="round"
      />
      
      <!-- mAP@50:95 line -->
      <polyline
        :points="map95Points"
        fill="none"
        stroke="#9b59b6"
        stroke-width="2"
        stroke-linejoin="round"
        stroke-dasharray="4,3"
      />
      
      <!-- Legend -->
      <g transform="translate(260, 10)">
        <line x1="0" y1="8" x2="20" y2="8" stroke="#409eff" stroke-width="2" />
        <text x="26" y="12" font-size="11" fill="#666">mAP@50</text>
        
        <line x1="80" y1="8" x2="100" y2="8" stroke="#9b59b6" stroke-width="2" stroke-dasharray="4,3" />
        <text x="106" y="12" font-size="11" fill="#666">mAP@50:95</text>
      </g>
    </svg>
    
    <div v-else class="empty-chart">
      暂无训练数据
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  metrics: {
    type: Array,
    default: () => [],
  },
})

const svgWidth = 420
const svgHeight = 200

const hasData = computed(() => props.metrics && props.metrics.length > 0)

const gridLines = [0, 0.25, 0.5, 0.75, 1.0]

const xScale = (ratio) => 40 + ratio * 340
const yScale = (val) => 160 - val * 140

// Generate polyline points for mAP@50
const map50Points = computed(() => {
  if (!hasData.value) return ''
  
  const maxEpoch = Math.max(...props.metrics.map(m => m.epoch))
  
  return props.metrics.map((m, i) => {
    const x = xScale(m.epoch / Math.max(maxEpoch, 1))
    const y = yScale(Math.min(m.map50 || 0, 1))
    return `${x},${y}`
  }).join(' ')
})

// Generate polyline points for mAP@50:95
const map95Points = computed(() => {
  if (!hasData.value) return ''
  
  const maxEpoch = Math.max(...props.metrics.map(m => m.epoch))
  
  return props.metrics.map((m) => {
    const x = xScale(m.epoch / Math.max(maxEpoch, 1))
    const y = yScale(Math.min(m.map50_95 || 0, 1))
    return `${x},${y}`
  }).join(' ')
})
</script>

<style lang="scss" scoped>
.training-chart {
  .empty-chart {
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
