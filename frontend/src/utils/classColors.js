/**
 * 类别颜色工具：优先工程自定义 class_colors，其次按类别在 classes 中的顺序
 * 取调色板，兜底用名称哈希稳定取色。调色板与后端 _DEFAULT_PALETTE 一致。
 */
export const CLASS_PALETTE = [
  '#1f5aff', '#0f9d58', '#e6a23c', '#e5484d',
  '#7c3aed', '#0ea5e9', '#db2777', '#65a30d',
]

export const hashCode = (str) => {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i)
    hash |= 0
  }
  return Math.abs(hash)
}

/**
 * @param {string} name 类别名
 * @param {object} [classColors] 工程 class_colors 映射
 * @param {string[]} [classList]  工程 classes（顺序取色）
 */
export function getClassColor(name, classColors = {}, classList = []) {
  if (!name) return '#8a8f98'
  if (classColors && classColors[name]) return classColors[name]
  const idx = classList ? classList.indexOf(name) : -1
  if (idx >= 0) return CLASS_PALETTE[idx % CLASS_PALETTE.length]
  return CLASS_PALETTE[hashCode(name) % CLASS_PALETTE.length]
}

/** 半透明填充（RGBA hex 拼接，默认 15% 透明度） */
export function classColorFill(color, alpha = '26') {
  if (!color || !/^#[0-9a-fA-F]{6}$/.test(color)) return color ? `${color}26` : '#00000026'
  return `${color}${alpha}`
}
