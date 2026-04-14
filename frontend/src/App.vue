<script setup lang="ts">
import { ref } from 'vue'
import {
  NConfigProvider,
  NMessageProvider,
  NDialogProvider,
  NButton,
  NDrawer,
  NDrawerContent,
  NTooltip,
  zhCN,
  dateZhCN,
} from 'naive-ui'
import type { GlobalThemeOverrides } from 'naive-ui'
import ModelProviderConfigPanel from './components/workbench/ModelProviderConfigPanel.vue'

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#4f46e5',
    primaryColorHover: '#6366f1',
    primaryColorPressed: '#4338ca',
    primaryColorSuppl: '#818cf8',
    borderRadius: '10px',
    borderRadiusSmall: '8px',
    fontSize: '14px',
    fontSizeMedium: '15px',
    lineHeight: '1.55',
    heightMedium: '38px',
  },
  Card: {
    borderRadius: '14px',
    paddingMedium: '20px',
  },
  Button: {
    borderRadiusMedium: '10px',
  },
  Input: {
    borderRadius: '10px',
  },
  Scrollbar: {
    width: '8px',
    height: '8px',
    borderRadius: '4px',
  },
}

const showLlmConfig = ref(false)
</script>

<template>
  <n-config-provider :locale="zhCN" :date-locale="dateZhCN" :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-dialog-provider>
        <router-view v-slot="{ Component }">
          <transition name="app-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>

        <n-tooltip trigger="hover" placement="left">
          <template #trigger>
            <n-button
              class="global-llm-fab"
              type="primary"
              circle
              strong
              size="large"
              @click="showLlmConfig = true"
            >
              LLM
            </n-button>
          </template>
          配置 LLM 大模型 Key
        </n-tooltip>

        <n-drawer v-model:show="showLlmConfig" :width="520" placement="right" resizable>
          <n-drawer-content body-content-style="padding: 0">
            <ModelProviderConfigPanel />
          </n-drawer-content>
        </n-drawer>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<style>
.app-fade-enter-active,
.app-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.app-fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}
.app-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.global-llm-fab {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 1200;
  width: 58px;
  height: 58px;
  border-radius: 999px;
  box-shadow: 0 16px 36px rgba(79, 70, 229, 0.28);
}

.global-llm-fab:hover {
  transform: translateY(-1px);
  box-shadow: 0 20px 40px rgba(79, 70, 229, 0.32);
}

@media (max-width: 768px) {
  .global-llm-fab {
    right: 14px;
    bottom: 14px;
    width: 54px;
    height: 54px;
  }
}
</style>
