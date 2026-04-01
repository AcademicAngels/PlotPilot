<template>
  <aside class="sidebar">
    <div class="sidebar-head">
      <n-button quaternary size="small" class="back-btn" @click="handleBack">
        <template #icon>
          <span class="ico-arrow">←</span>
        </template>
        书目列表
      </n-button>
      <h3 class="sidebar-title">章节</h3>
    </div>
    <n-scrollbar class="sidebar-scroll">
      <div v-if="!chapters.length" class="sidebar-empty">暂无章节大纲，可先执行「大纲规划」</div>
      <n-list v-else hoverable>
        <n-list-item
          v-for="ch in chapters"
          :key="ch.id"
          :class="{ 'is-active': currentChapterId === ch.id }"
        >
          <div class="chapter-item">
            <div class="chapter-header" @click="handleChapterClick(ch.id)">
              <n-thing :title="`第${ch.id}章 ${ch.title || ''}`">
                <template #description>
                  <n-tag size="small" :type="ch.has_file ? 'success' : 'default'" round>
                    {{ ch.has_file ? '已收稿' : '未收稿' }}
                  </n-tag>
                </template>
              </n-thing>
            </div>
            <div class="chapter-actions">
              <n-button-group size="tiny">
                <n-button
                  @click.stop="handleGenerate(ch.id)"
                  :disabled="generating === ch.id"
                  :loading="generating === ch.id"
                >
                  生成
                </n-button>
                <n-button
                  @click.stop="handleReview(ch.id)"
                  :disabled="!ch.has_file || reviewing === ch.id"
                  :loading="reviewing === ch.id"
                >
                  审稿
                </n-button>
                <n-button
                  @click.stop="handleExtendOutline(ch.id)"
                  :disabled="extending"
                  :loading="extending"
                >
                  续纲
                </n-button>
              </n-button-group>
            </div>
          </div>
        </n-list-item>
      </n-list>
    </n-scrollbar>
  </aside>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface Chapter {
  id: number
  title: string
  has_file: boolean
}

interface ChapterListProps {
  slug: string
  chapters: Chapter[]
  currentChapterId?: number | null
}

const props = withDefaults(defineProps<ChapterListProps>(), {
  chapters: () => [],
  currentChapterId: null
})

const emit = defineEmits<{
  select: [id: number]
  back: []
  generate: [chapterId: number]
  review: [chapterId: number]
  extendOutline: [fromChapterId: number]
}>()

const generating = ref<number | null>(null)
const reviewing = ref<number | null>(null)
const extending = ref(false)

const handleChapterClick = (id: number) => {
  emit('select', id)
}

const handleBack = () => {
  emit('back')
}

const handleGenerate = (chapterId: number) => {
  generating.value = chapterId
  emit('generate', chapterId)
  // 父组件完成后需要重置 generating.value
}

const handleReview = (chapterId: number) => {
  reviewing.value = chapterId
  emit('review', chapterId)
  // 父组件完成后需要重置 reviewing.value
}

const handleExtendOutline = (fromChapterId: number) => {
  extending.value = true
  emit('extendOutline', fromChapterId)
  // 父组件完成后需要重置 extending.value
}

// 暴露方法供父组件调用
defineExpose({
  resetGenerating: () => { generating.value = null },
  resetReviewing: () => { reviewing.value = null },
  resetExtending: () => { extending.value = false }
})
</script>

<style scoped>
.sidebar {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 12px 10px;
  background: var(--app-surface);
  border-right: 1px solid var(--aitext-split-border);
}

.sidebar-head {
  margin-bottom: 10px;
}

.back-btn {
  margin-bottom: 8px;
  font-weight: 500;
}

.ico-arrow {
  font-size: 14px;
  margin-right: 2px;
}

.sidebar-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.sidebar-scroll {
  flex: 1;
  min-height: 0;
}

.sidebar-empty {
  padding: 12px;
  font-size: 13px;
  color: var(--app-muted);
  line-height: 1.5;
}

.chapter-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chapter-header {
  cursor: pointer;
  flex: 1;
}

.chapter-actions {
  padding-left: 4px;
}

.sidebar :deep(.n-list-item) {
  border-radius: 10px;
  margin-bottom: 4px;
  padding: 8px;
  transition: background var(--app-transition), transform 0.15s ease;
}

.sidebar :deep(.n-list-item:hover) {
  background: rgba(79, 70, 229, 0.06);
}

.sidebar :deep(.n-list-item.is-active) {
  background: rgba(79, 70, 229, 0.12);
  box-shadow: inset 0 0 0 1px rgba(79, 70, 229, 0.25);
}
</style>
