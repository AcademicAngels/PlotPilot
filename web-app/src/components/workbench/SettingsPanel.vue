<template>
  <div class="right-panel">
    <BiblePanel v-if="currentPanel === 'bible'" :key="bibleKey" :slug="slug" />
    <KnowledgePanel v-else :slug="slug" />
  </div>
</template>

<script setup lang="ts">
import BiblePanel from '../BiblePanel.vue'
import KnowledgePanel from '../KnowledgePanel.vue'

interface Props {
  slug: string
  currentPanel?: 'bible' | 'knowledge'
  bibleKey?: number
}

withDefaults(defineProps<Props>(), {
  currentPanel: 'knowledge',
  bibleKey: 0,
})
</script>

<style scoped>
.right-panel {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--aitext-panel-muted);
  border-left: 1px solid var(--aitext-split-border);
}
</style>