import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * 工作台右栏「软刷新」信号：不整页 remount，仅驱动伏笔账本 / 编年史等重新拉数。
 * 在 loadDesk 成功后由 Workbench 触发（全托管完章、保存、规划确认等同源）。
 */
export const useWorkbenchRefreshStore = defineStore('workbenchRefresh', () => {
  const foreshadowTick = ref(0)
  const chroniclesTick = ref(0)

  function bumpForeshadowLedger() {
    foreshadowTick.value += 1
  }

  function bumpChronicles() {
    chroniclesTick.value += 1
  }

  /** 章节落库或结构变化后：伏笔与编年史强联动（故事线/弧光保持手动或宏观事件再刷） */
  function bumpAfterChapterDeskChange() {
    bumpForeshadowLedger()
    bumpChronicles()
  }

  return {
    foreshadowTick,
    chroniclesTick,
    bumpForeshadowLedger,
    bumpChronicles,
    bumpAfterChapterDeskChange,
  }
})
