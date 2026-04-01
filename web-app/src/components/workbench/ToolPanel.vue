<template>
  <div class="tool-panel">
    <n-tabs type="line" animated>
      <n-tab-pane name="plan" tab="大纲规划">
        <div class="panel-content">
          <n-space vertical :size="16">
            <n-text depth="3">
              首次生成适用于尚无圣经与大纲；「再规划」会结合已完成章节信息，修订 Bible 与分章大纲。
            </n-text>

            <n-radio-group v-model:value="planMode">
              <n-space vertical :size="8">
                <n-radio value="initial">首次生成圣经与分章大纲</n-radio>
                <n-radio value="revise">基于进度再规划</n-radio>
              </n-space>
            </n-radio-group>

            <n-checkbox v-model:checked="planDryRun">
              预演（dry-run，不调用模型）
            </n-checkbox>

            <n-button type="primary" block @click="handlePlan">
              开始规划
            </n-button>
          </n-space>
        </div>
      </n-tab-pane>

      <n-tab-pane name="hosted" tab="托管连写">
        <div class="panel-content">
          <n-space vertical :size="16">
            <n-text depth="3">
              托管模式：自动生成多章，无需人工干预。
            </n-text>

            <n-form-item label="起始章节">
              <n-input-number v-model:value="hostedFrom" :min="1" />
            </n-form-item>

            <n-form-item label="结束章节">
              <n-input-number v-model:value="hostedTo" :min="1" />
            </n-form-item>

            <n-checkbox v-model:checked="hostedAutoSave">
              自动保存
            </n-checkbox>

            <n-checkbox v-model:checked="hostedAutoOutline">
              自动生成大纲
            </n-checkbox>

            <n-button type="primary" block @click="handleStartHostedWrite">
              开始托管连写
            </n-button>
          </n-space>
        </div>
      </n-tab-pane>

      <n-tab-pane name="bible" tab="Bible">
        <div class="panel-content">
          <n-text depth="3">人物、世界观设定</n-text>
          <!-- TODO: Bible 编辑器 -->
        </div>
      </n-tab-pane>

      <n-tab-pane name="outline" tab="大纲">
        <div class="panel-content">
          <n-text depth="3">章节大纲列表</n-text>
          <!-- TODO: 大纲列表 -->
        </div>
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  plan: [mode: 'initial' | 'revise', dryRun: boolean]
  startHostedWrite: [from: number, to: number, autoSave: boolean, autoOutline: boolean]
}>()

const planMode = ref<'initial' | 'revise'>('initial')
const planDryRun = ref(false)

const hostedFrom = ref(1)
const hostedTo = ref(5)
const hostedAutoSave = ref(true)
const hostedAutoOutline = ref(true)

const handlePlan = () => {
  emit('plan', planMode.value, planDryRun.value)
}

const handleStartHostedWrite = () => {
  emit('startHostedWrite', hostedFrom.value, hostedTo.value, hostedAutoSave.value, hostedAutoOutline.value)
}
</script>

<style scoped>
.tool-panel {
  height: 100%;
  background: var(--app-surface);
  border-left: 1px solid var(--aitext-split-border);
}

.panel-content {
  padding: 20px;
}
</style>
