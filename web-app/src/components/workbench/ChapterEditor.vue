<template>
  <div class="chapter-editor">
    <div class="editor-header">
      <div class="editor-title">
        <h2 v-if="currentChapter">第{{ currentChapter.id }}章 {{ currentChapter.title }}</h2>
        <h2 v-else>选择章节开始编辑</h2>
      </div>
      <div class="editor-actions">
        <n-button-group>
          <n-button @click="handleSave" :disabled="!hasChanges" type="primary">
            保存
          </n-button>
          <n-button @click="handleReload" :disabled="!currentChapter">
            重新加载
          </n-button>
        </n-button-group>
      </div>
    </div>

    <div class="editor-body">
      <n-scrollbar v-if="currentChapter" class="editor-scroll">
        <div class="editor-content">
          <n-input
            v-model:value="content"
            type="textarea"
            placeholder="章节内容..."
            :autosize="{ minRows: 20 }"
            @update:value="handleContentChange"
          />
        </div>
      </n-scrollbar>
      <div v-else class="editor-empty">
        <n-empty description="请从左侧选择章节" />
      </div>
    </div>

    <!-- 流式生成区域 -->
    <div v-if="streaming" class="streaming-panel">
      <div class="streaming-header">
        <n-text strong>正在生成...</n-text>
        <n-button size="small" @click="handleStopStreaming">停止</n-button>
      </div>
      <n-scrollbar class="streaming-content">
        <div class="streaming-text">{{ streamingText }}</div>
      </n-scrollbar>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useMessage } from 'naive-ui'

interface Chapter {
  id: number
  title: string
  has_file: boolean
  content?: string
}

interface ChapterEditorProps {
  currentChapter: Chapter | null
  slug: string
}

const props = defineProps<ChapterEditorProps>()

const emit = defineEmits<{
  save: [chapterId: number, content: string]
  reload: [chapterId: number]
}>()

const message = useMessage()

const content = ref('')
const originalContent = ref('')
const streaming = ref(false)
const streamingText = ref('')

const hasChanges = computed(() => {
  return content.value !== originalContent.value
})

// 监听当前章节变化
watch(() => props.currentChapter, (newChapter) => {
  if (newChapter) {
    content.value = newChapter.content || ''
    originalContent.value = newChapter.content || ''
  } else {
    content.value = ''
    originalContent.value = ''
  }
}, { immediate: true })

const handleContentChange = () => {
  // 内容变化时的处理
}

const handleSave = () => {
  if (!props.currentChapter) return
  emit('save', props.currentChapter.id, content.value)
  originalContent.value = content.value
  message.success('保存成功')
}

const handleReload = () => {
  if (!props.currentChapter) return
  emit('reload', props.currentChapter.id)
}

const handleStopStreaming = () => {
  streaming.value = false
  streamingText.value = ''
}

// 暴露方法供父组件调用
defineExpose({
  startStreaming: () => {
    streaming.value = true
    streamingText.value = ''
  },
  appendStreamingText: (text: string) => {
    streamingText.value += text
  },
  finishStreaming: (finalContent: string) => {
    streaming.value = false
    content.value = finalContent
    originalContent.value = finalContent
  }
})
</script>

<style scoped>
.chapter-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--app-surface);
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--aitext-split-border);
}

.editor-title h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.editor-body {
  flex: 1;
  min-height: 0;
  position: relative;
}

.editor-scroll {
  height: 100%;
}

.editor-content {
  padding: 20px;
}

.editor-empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.streaming-panel {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 40%;
  background: var(--app-surface);
  border-top: 2px solid var(--primary-color);
  display: flex;
  flex-direction: column;
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.1);
}

.streaming-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--aitext-split-border);
  background: rgba(79, 70, 229, 0.05);
}

.streaming-content {
  flex: 1;
  min-height: 0;
}

.streaming-text {
  padding: 16px;
  white-space: pre-wrap;
  line-height: 1.6;
  font-family: var(--font-mono);
}
</style>
