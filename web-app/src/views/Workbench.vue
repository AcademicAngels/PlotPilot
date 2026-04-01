<template>
  <div class="workbench">
    <StatsTopBar :slug="slug" />

    <n-spin :show="pageLoading" class="workbench-spin" description="加载工作台…">
      <div class="workbench-inner">
        <n-split direction="horizontal" :min="0.12" :max="0.30" :default-size="0.18">
          <template #1>
            <ChapterList
              :slug="slug"
              :chapters="chapters"
              :current-chapter-id="currentChapterId"
              @select="goToChapter"
              @back="goHome"
            />
          </template>

          <template #2>
            <n-split direction="horizontal" :min="0.40" :max="0.75" :default-size="0.60">
              <template #1>
                <WorkArea
                  ref="workAreaRef"
                  :slug="slug"
                  :book-title="bookTitle"
                  :chapters="chapters"
                  :current-chapter-id="currentChapterId"
                  @set-right-panel="setRightPanel"
                  @open-plan-modal="openPlanModal"
                  @start-write="openWorkflowGenerate"
                  @chapter-updated="handleChapterUpdated"
                />
              </template>

              <template #2>
                <SettingsPanel :slug="slug" :current-panel="rightPanel" :bible-key="biblePanelKey" />
              </template>
            </n-split>
          </template>
        </n-split>
      </div>
    </n-spin>

    <n-modal
      v-model:show="showPlanModal"
      preset="card"
      style="width: min(460px, 94vw)"
      :mask-closable="false"
      title="结构规划"
    >
      <n-space vertical :size="16">
        <n-text depth="3">
          首次生成适用于尚无圣经与大纲；「再规划」会结合滚动摘要、编务远期摘要与已完成章节信息，修订 bible 与分章大纲。
        </n-text>
        <n-radio-group v-model:value="planMode">
          <n-space vertical :size="8">
            <n-radio value="initial">首次生成圣经与分章大纲</n-radio>
            <n-radio value="revise" :disabled="!hasStructure">基于进度再规划（需已有 bible / outline）</n-radio>
          </n-space>
        </n-radio-group>
        <n-checkbox v-model:checked="planDryRun">预演（dry-run，不调用模型）</n-checkbox>
        <n-space justify="end" :size="10">
          <n-button @click="showPlanModal = false">取消</n-button>
          <n-button type="primary" @click="confirmPlan">开始</n-button>
        </n-space>
      </n-space>
    </n-modal>

    <n-modal
      v-model:show="showTaskModal"
      preset="card"
      style="width: min(420px, 92vw)"
      :mask-closable="false"
      :segmented="{ content: true }"
      title="任务进行中"
    >
      <n-space vertical :size="16">
        <n-progress type="line" :percentage="taskProgress" :processing="taskProgress < 100" :height="10" />
        <n-text>{{ taskMessage }}</n-text>
        <n-button size="small" secondary @click="cancelRunningTask">终止任务</n-button>
      </n-space>
    </n-modal>

    <GenerateChapterWorkflowModal
      v-model:show="showWorkflowModal"
      :slug="slug"
      :chapters="chapters"
      :default-chapter-id="currentChapterId"
      @saved="onWorkflowChapterSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { useWorkbench } from '../composables/useWorkbench'
import StatsTopBar from '../components/stats/StatsTopBar.vue'
import ChapterList from '../components/workbench/ChapterList.vue'
import WorkArea from '../components/workbench/WorkArea.vue'
import SettingsPanel from '../components/workbench/SettingsPanel.vue'
import GenerateChapterWorkflowModal from '../components/workbench/GenerateChapterWorkflowModal.vue'

const route = useRoute()
const message = useMessage()

const slug = route.params.slug as string
const workAreaRef = ref<InstanceType<typeof WorkArea> | null>(null)
const showWorkflowModal = ref(false)

const openWorkflowGenerate = () => {
  showWorkflowModal.value = true
}

const onWorkflowChapterSaved = async () => {
  await loadDesk()
  biblePanelKey.value += 1
}

const handleChapterUpdated = async () => {
  await loadDesk()
  biblePanelKey.value += 1
}

const {
  bookTitle,
  chapters,
  rightPanel,
  biblePanelKey,
  pageLoading,
  showPlanModal,
  planMode,
  planDryRun,
  bookMeta,
  showTaskModal,
  taskProgress,
  taskMessage,
  currentJobId,
  hasStructure,
  setRightPanel,
  onMessagesUpdated,
  loadDesk,
  openPlanModal,
  confirmPlan,
  startPolling,
  cancelRunningTask,
  stopPolling,
  goHome,
  goToChapter,
} = useWorkbench({ slug, chatAreaRef: workAreaRef })

// Override currentChapterId with route-based computation
const currentChapterId = computed(() => {
  if (route.name === 'Chapter') return Number(route.params.id)
  return null
})

onMounted(async () => {
  try {
    await loadDesk()
  } catch {
    message.error('加载失败，请检查网络与后端是否已启动')
    bookTitle.value = slug
  } finally {
    pageLoading.value = false
  }
})
</script>

<style scoped>
.workbench {
  height: 100vh;
  min-height: 0;
  background: var(--app-page-bg, #f0f2f8);
  display: flex;
  flex-direction: column;
}

.workbench-spin {
  flex: 1;
  min-height: 0;
}

.workbench-spin :deep(.n-spin-content) {
  min-height: 100%;
  height: 100%;
}

.workbench-inner {
  height: 100%;
  min-height: 0;
}

.workbench-inner :deep(.n-split) {
  height: 100%;
}

.workbench-inner :deep(.n-split-pane-1) {
  min-height: 0;
  overflow: hidden;
}
</style>
