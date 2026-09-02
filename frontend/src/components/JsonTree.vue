<template>
  <div class="json-tree">
    <!-- 可折叠节点：对象 / 数组 -->
    <template v-if="isContainer">
      <div class="node-row container" :style="{ paddingLeft: pad }" @click="toggle">
        <span class="twisty" :class="{ open: !collapsed }">
          <svg viewBox="0 0 8 10" width="8" height="10">
            <path d="M1 1 L7 5 L1 9 Z" fill="currentColor" />
          </svg>
        </span>
        <span class="node-key">{{ labelText }}</span>
        <span v-if="collapsed" class="node-summary">
          {{ containerSummary }}
        </span>
        <span v-else class="node-type">{{ typeName }}</span>
      </div>
      <div v-show="!collapsed" class="node-children">
        <JsonTree
          v-for="(val, key) in data"
          :key="key"
          :data="val"
          :label="key"
          :is-index="isArray"
          :level="level + 1"
          :mode="mode"
        />
      </div>
    </template>

    <!-- 标量 -->
    <div v-else class="node-row scalar" :style="{ paddingLeft: pad }">
      <span class="node-key" v-if="label !== null">{{ labelText }}</span>
      <span class="node-value" :class="typeClass">{{ valueText }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

defineOptions({ name: 'JsonTree' })

const props = defineProps({
  data: { type: [Object, Array, String, Number, Boolean, null], default: null },
  label: { type: [String, Number], default: null }, // null = 根节点
  isIndex: { type: Boolean, default: false },
  level: { type: Number, default: 0 },
  mode: { type: String, default: 'auto' }, // auto | expanded | collapsed
})

const resolveCollapsed = () => {
  if (props.mode === 'expanded') return false
  if (props.mode === 'collapsed') return true
  return props.level >= 2 // 深层默认折叠
}

const collapsed = ref(resolveCollapsed())

watch(() => props.mode, () => { collapsed.value = resolveCollapsed() })

const typeOf = computed(() => {
  const d = props.data
  if (d === null) return 'null'
  if (Array.isArray(d)) return 'array'
  return typeof d
})

const isContainer = computed(() => typeOf.value === 'object' || typeOf.value === 'array')
const isArray = computed(() => typeOf.value === 'array')

const typeName = computed(() => (isArray.value ? 'array' : 'object'))

const size = computed(() => {
  const d = props.data
  return d === null ? 0 : (Array.isArray(d) ? d.length : Object.keys(d).length)
})

const containerSummary = computed(() => {
  const d = props.data
  const n = size.value
  const head = isArray.value ? '[' : '{'
  const tail = isArray.value ? ']' : '}'
  if (n === 0) return `${head}${tail}`
  // 预览首元素
  const first = isArray.value ? d[0] : Object.values(d)[0]
  const preview = first === null ? 'null' : Array.isArray(first) ? '[…]' : typeof first === 'object' ? '{…}' : String(first)
  return `${head} ${preview} … ${tail}  (${n})`
})

const labelText = computed(() => {
  if (props.label === null) return ''
  return props.isIndex ? `[${props.label}]` : `${props.label}: `
})

const valueText = computed(() => {
  const d = props.data
  if (d === null) return 'null'
  if (typeof d === 'string') return `"${d}"`
  return String(d)
})

const typeClass = computed(() => ({
  null: 'v-null',
  string: 'v-string',
  number: 'v-number',
  boolean: 'v-boolean',
}[typeOf.value] || ''))

const pad = computed(() => `${props.level * 16 + (props.label === null ? 0 : 0)}px`)
// 子级内容左移对齐三角：容器行本身缩进 level*16，三角前再加 14px 对齐键文本
const containerPad = computed(() => `${props.level * 16}px`)

const toggle = () => { collapsed.value = !collapsed.value }
</script>

<style lang="scss" scoped>
.json-tree {
  font-family: "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.8;
  user-select: text;
}

.node-row {
  display: flex;
  align-items: flex-start;
  white-space: pre-wrap;
  word-break: break-all;
  cursor: default;

  &.container {
    cursor: pointer;
    border-radius: 3px;

    &:hover {
      background: rgba(127, 143, 166, 0.12);
    }
  }

  .twisty {
    flex: 0 0 14px;
    width: 14px;
    height: 16px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: #8f9bae;
    transition: transform 0.15s;
    margin-top: 5px;

    svg { transition: transform 0.12s; }

    &.open svg {
      transform: rotate(90deg);
    }
  }

  .node-key {
    color: #e8c36a;
    font-weight: 500;
  }

  .node-type {
    color: #5b6472;
    font-size: 11px;
    font-style: italic;
    margin-left: 6px;
  }

  .node-summary {
    color: #7d8b9f;
    margin-left: 2px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 70%;
  }

  .node-value {
    &.v-string { color: #98c379; }
    &.v-number { color: #61afef; }
    &.v-boolean { color: #c678dd; }
    &.v-null { color: #7d8b9f; font-style: italic; }
  }
}

.node-children {
  border-left: 1px dashed rgba(127, 143, 166, 0.18);
  margin-left: 7px;
}
</style>
