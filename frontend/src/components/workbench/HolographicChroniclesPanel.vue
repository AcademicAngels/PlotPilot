<template>
  <div class="hc-panel">
    <header class="hc-head">
      <div>
        <h3 class="hc-title">全息编年史</h3>
        <p class="hc-lead">
          中轴为章进度锚点：<strong>左</strong>里世界剧情时间，<strong>右</strong>表世界快照（存档）。
          悬浮快照节点可联想左侧剧情节点；回滚接口就绪后右侧按钮将可点。
        </p>
      </div>
      <n-button size="small" type="primary" :loading="loading" @click="load">刷新</n-button>
    </header>

    <n-alert v-if="noteText" type="default" :show-icon="true" class="hc-note" style="font-size: 11px">
      {{ noteText }}
    </n-alert>

    <n-spin :show="loading" class="hc-spin">
      <div v-if="rows.length === 0 && !loading" class="hc-empty-wrap">
        <n-empty description="暂无编年节点：可在下方编辑 Bible 剧情时间线，或在后端创建 novel_snapshots">
          <template #icon><span style="font-size: 40px">🧬</span></template>
        </n-empty>
      </div>

      <div v-else class="helix-wrap">
        <div class="helix-header">
          <span class="helix-header-spine">进度</span>
          <span class="helix-header-left">里世界 · 剧情</span>
          <span class="helix-header-right">表世界 · 快照</span>
        </div>

        <div
          v-for="row in rows"
          :key="row.chapter_index"
          class="helix-row"
          :class="{ 'helix-row--hot': hoverChapter === row.chapter_index }"
          @mouseenter="hoverChapter = row.chapter_index"
          @mouseleave="hoverChapter = null"
        >
          <div class="helix-chapter">
            <span class="helix-dot" />
            <span class="helix-ch-num">第 {{ row.chapter_index }} 章</span>
          </div>

          <div class="helix-cell helix-cell--story">
            <div
              v-for="ev in row.story_events"
              :key="ev.note_id"
              class="story-node"
            >
              <n-tag type="success" size="tiny" round>{{ ev.time }}</n-tag>
              <div class="story-title">{{ ev.title }}</div>
              <div v-if="ev.description" class="story-desc">{{ ev.description }}</div>
            </div>
            <n-text v-if="row.story_events.length === 0" depth="3" style="font-size: 11px">—</n-text>
          </div>

          <div class="helix-cell helix-cell--snap">
            <div
              v-for="sn in row.snapshots"
              :key="sn.id"
              class="snap-node"
              :title="snapTooltip(sn)"
            >
              <n-tag :type="sn.kind === 'MANUAL' ? 'warning' : 'info'" size="tiny" round>
                {{ sn.kind === 'MANUAL' ? '🟣 Manual' : '🔵 Auto' }}
              </n-tag>
              <span class="snap-name">{{ sn.name }}</span>
              <n-button size="tiny" quaternary disabled title="rollback API 接入后启用">
                回滚
              </n-button>
            </div>
            <n-text v-if="row.snapshots.length === 0" depth="3" style="font-size: 11px">—</n-text>
          </div>
        </div>

        <div class="axis-footer">
          书目已展开至第 <strong>{{ maxChapter }}</strong> 章（章号来自章节表；编年条仅包含有数据的章位）
        </div>
      </div>
    </n-spin>

    <n-collapse class="hc-collapse" :default-expanded-names="[]">
      <n-collapse-item title="剧情时间线 · 列表编辑（Bible）" name="edit">
        <TimelinePanel :slug="slug" />
      </n-collapse-item>
    </n-collapse>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useWorkbenchRefreshStore } from '../../stores/workbenchRefreshStore'
import { useMessage } from 'naive-ui'
import { chroniclesApi } from '../../api/chronicles'
import type { ChronicleRow, ChronicleSnapshot } from '../../api/chronicles'
import TimelinePanel from './TimelinePanel.vue'

const props = defineProps<{ slug: string }>()
const message = useMessage()

const loading = ref(false)
const rows = ref<ChronicleRow[]>([])
const maxChapter = ref(1)
const noteText = ref('')
const hoverChapter = ref<number | null>(null)

function snapTooltip(sn: ChronicleSnapshot): string {
  const parts = [sn.name, sn.description, sn.created_at].filter(Boolean)
  return parts.join(' · ')
}

async function load() {
  loading.value = true
  try {
    const res = await chroniclesApi.get(props.slug)
    rows.value = res.rows
    maxChapter.value = res.max_chapter_in_book
    noteText.value = res.note
  } catch {
    rows.value = []
    noteText.value = ''
    message.error('编年史加载失败，请确认后端已包含 /chronicles 接口')
  } finally {
    loading.value = false
  }
}

watch(() => props.slug, () => void load(), { immediate: true })

const refreshStore = useWorkbenchRefreshStore()
const { chroniclesTick } = storeToRefs(refreshStore)
watch(chroniclesTick, () => {
  void load()
})
</script>

<style scoped>
.hc-panel {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 10px 12px 12px;
}

.hc-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 10px;
  flex-shrink: 0;
}

.hc-title {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 600;
}

.hc-lead {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--n-text-color-3);
  max-width: 520px;
}

.hc-note {
  flex-shrink: 0;
  margin-bottom: 10px;
}

.hc-spin {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.hc-empty-wrap {
  padding: 24px 0;
}

.helix-wrap {
  position: relative;
  max-height: min(52vh, 480px);
  overflow-y: auto;
  padding: 8px 4px 12px;
  border: 1px solid var(--n-border-color);
  border-radius: 8px;
  background: var(--n-color-modal);
}

.helix-header {
  display: grid;
  grid-template-columns: 56px 1fr 1fr;
  gap: 8px;
  align-items: center;
  padding: 6px 4px 10px;
  margin-bottom: 4px;
  border-bottom: 1px solid var(--n-border-color);
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--n-color-modal);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.03em;
  color: var(--n-text-color-3);
}

.helix-header-spine {
  text-align: center;
  font-size: 9px;
}

.helix-header-left {
  text-align: left;
  padding-left: 4px;
}

.helix-header-right {
  text-align: left;
  padding-left: 6px;
}

.helix-row {
  display: grid;
  grid-template-columns: 56px 1fr 1fr;
  gap: 8px;
  align-items: start;
  padding: 12px 0;
  border-bottom: 1px dashed var(--n-border-color);
  transition: background 0.15s ease;
}

.helix-row--hot {
  background: rgba(32, 128, 240, 0.06);
}

.helix-chapter {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding-top: 4px;
}

.helix-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--n-primary-color);
  box-shadow: 0 0 0 3px rgba(32, 128, 240, 0.25);
}

.helix-ch-num {
  font-size: 10px;
  color: var(--n-text-color-3);
  writing-mode: vertical-rl;
  text-orientation: mixed;
  max-height: 72px;
  line-height: 1.2;
}

.helix-cell {
  min-width: 0;
}

.helix-cell--story {
  border-right: 2px solid rgba(24, 160, 88, 0.35);
  padding-right: 10px;
}

.helix-cell--snap {
  padding-left: 6px;
}

.story-node {
  margin-bottom: 8px;
  padding: 8px;
  border-radius: 6px;
  background: rgba(24, 160, 88, 0.08);
  border: 1px solid rgba(24, 160, 88, 0.2);
}

.story-title {
  font-size: 13px;
  font-weight: 600;
  margin-top: 6px;
  line-height: 1.4;
}

.story-desc {
  font-size: 12px;
  color: var(--n-text-color-2);
  margin-top: 4px;
  line-height: 1.45;
}

.snap-node {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  padding: 8px;
  border-radius: 6px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.25);
}

.snap-name {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  font-weight: 500;
}

.axis-footer {
  font-size: 11px;
  color: var(--n-text-color-3);
  padding: 10px 8px 4px;
  border-top: 1px solid var(--n-border-color);
}

.hc-collapse {
  flex-shrink: 0;
  margin-top: 12px;
}

.hc-panel :deep(.timeline-panel) {
  max-height: 420px;
}
</style>
