<template>
  <div class="workbench">
    <StatsTopBar :slug="slug" />

    <n-spin :show="pageLoading" class="workbench-spin" description="加载工作台…">
      <div class="workbench-inner">
        <n-split direction="horizontal" :min="0.14" :max="0.42" :default-size="0.22">
          <template #1>
            <ChapterListNew
              ref="chapterListRef"
              :slug="slug"
              :chapters="chapters"
              :current-chapter-id="currentChapterId"
              @select="handleSelectChapter"
              @back="goHome"
              @generate="handleGenerateChapter"
              @review="handleReviewChapter"
              @extend-outline="handleExtendOutline"
            />
          </template>

          <template #2>
            <n-split direction="horizontal" :min="0.28" :max="0.72" :default-size="0.65">
              <template #1>
                <ChapterEditor
                  ref="editorRef"
                  :slug="slug"
                  :current-chapter="currentChapter"
                  @save="handleSaveChapter"
                  @reload="handleReloadChapter"
                />
              </template>

              <template #2>
                <ToolPanel
                  :slug="slug"
                  @plan="handlePlan"
                  @start-hosted-write="handleStartHostedWrite"
                />
              </template>
            </n-split>
          </template>
        </n-split>
      </div>
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import StatsTopBar from '../components/stats/StatsTopBar.vue'
import ChapterListNew from '../components/workbench/ChapterListNew.vue'
import ChapterEditor from '../components/workbench/ChapterEditor.vue'
import ToolPanel from '../components/workbench/ToolPanel.vue'
import { workflowApi } from '../api/workflow'
import { bookApi } from '../api/book'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const slug = computed(() => route.params.slug as string)
const pageLoading = ref(true)
const chapters = ref<any[]>([])
const currentChapterId = ref<number | null>(null)
const chapterListRef = ref()
const editorRef = ref()

const currentChapter = computed(() => {
  if (!currentChapterId.value) return null
  return chapters.value.find(ch => ch.id === currentChapterId.value) || null
})

onMounted(async () => {
  await loadChapters()
  pageLoading.value = false
})

const loadChapters = async () => {
  try {
    const data = await bookApi.getBook(slug.value)
    chapters.value = data.chapters || []
  } catch (error) {
    message.error('加载章节失败')
    console.error(error)
  }
}

const handleSelectChapter = async (chapterId: number) => {
  currentChapterId.value = chapterId
  // 加载章节内容
  try {
    const chapter = await bookApi.getChapter(slug.value, chapterId)
    const idx = chapters.value.findIndex(ch => ch.id === chapterId)
    if (idx >= 0) {
      chapters.value[idx] = { ...chapters.value[idx], content: chapter.content }
    }
  } catch (error) {
    message.error('加载章节内容失败')
  }
}

const handleGenerateChapter = async (chapterId: number) => {
  try {
    message.info(`开始生成第${chapterId}章...`)

    // 使用流式生成
    editorRef.value?.startStreaming()

    await workflowApi.consumeGenerateChapterStream(
      slug.value,
      { chapter_number: chapterId, outline: '根据大纲生成' },
      {
        onEvent: (event) => {
          if (event.type === 'chunk') {
            editorRef.value?.appendStreamingText(event.text)
          } else if (event.type === 'done') {
            editorRef.value?.finishStreaming(event.content)
            message.success(`第${chapterId}章生成完成`)
            loadChapters()
          } else if (event.type === 'error') {
            message.error(`生成失败: ${event.message}`)
          }
        },
        onError: (err) => {
          message.error(`生成失败: ${err}`)
        }
      }
    )
  } catch (error) {
    message.error('生成章节失败')
    console.error(error)
  } finally {
    chapterListRef.value?.resetGenerating()
  }
}

const handleReviewChapter = async (chapterId: number) => {
  try {
    message.info(`开始审稿第${chapterId}章...`)
    const result = await workflowApi.reviewChapter(slug.value, chapterId)

    message.success(`审稿完成，评分: ${result.score}/100`)

    // 显示建议
    if (result.suggestions.length > 0) {
      console.log('审稿建议:', result.suggestions)
      // TODO: 在界面上显示建议
    }
  } catch (error: any) {
    if (error.response?.status === 501) {
      message.warning('审稿功能开发中')
    } else {
      message.error('审稿失败')
    }
    console.error(error)
  } finally {
    chapterListRef.value?.resetReviewing()
  }
}

const handleExtendOutline = async (fromChapterId: number) => {
  try {
    message.info(`从第${fromChapterId}章开始续写大纲...`)
    const result = await workflowApi.extendOutline(slug.value, fromChapterId, 5)

    if (result.success) {
      message.success(`成功添加 ${result.chapters_added} 章大纲`)
      await loadChapters()
    }
  } catch (error: any) {
    if (error.response?.status === 501) {
      message.warning('续写大纲功能开发中')
    } else {
      message.error('续写大纲失败')
    }
    console.error(error)
  } finally {
    chapterListRef.value?.resetExtending()
  }
}

const handleSaveChapter = async (chapterId: number, content: string) => {
  try {
    await bookApi.updateChapter(slug.value, chapterId, { content })
    message.success('保存成功')
    await loadChapters()
  } catch (error) {
    message.error('保存失败')
    console.error(error)
  }
}

const handleReloadChapter = async (chapterId: number) => {
  await handleSelectChapter(chapterId)
  message.info('已重新加载')
}

const handlePlan = async (mode: 'initial' | 'revise', dryRun: boolean) => {
  try {
    message.info(`开始${mode === 'initial' ? '首次' : '再'}规划...`)
    const result = await workflowApi.planNovel(slug.value, mode, dryRun)

    if (result.success) {
      message.success(result.message)
      await loadChapters()
    }
  } catch (error: any) {
    if (error.response?.status === 501) {
      message.warning('大纲规划功能开发中')
    } else {
      message.error('规划失败')
    }
    console.error(error)
  }
}

const handleStartHostedWrite = () => {
  message.info('托管连写功能待实现')
  // TODO: 打开托管连写对话框
}

const goHome = () => {
  router.push('/')
}
</script>

<style scoped>
.workbench {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--app-bg);
}

.workbench-spin {
  flex: 1;
  min-height: 0;
}

.workbench-inner {
  height: 100%;
}
</style>
