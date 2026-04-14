<script setup lang="ts">
import { ref } from 'vue'
import {
  NConfigProvider,
  NMessageProvider,
  NDialogProvider,
  NButton,
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

        <transition name="llm-overlay">
          <div
            v-if="showLlmConfig"
            class="global-llm-overlay"
            @click.self="showLlmConfig = false"
          >
            <div class="global-llm-modal">
              <div class="global-llm-shell">
                <header class="global-llm-shell-header">
                  <div class="global-llm-shell-copy">
                    <p class="global-llm-shell-eyebrow">Model Access</p>
                    <h2 class="global-llm-shell-title">配置 LLM 大模型 Key</h2>
                    <p class="global-llm-shell-desc">
                      在这里维护 OpenAI 兼容协议的模型、网关地址和 API Key。保存后会同步到当前后端进程。
                    </p>
                  </div>
                  <button
                    class="global-llm-close"
                    type="button"
                    aria-label="关闭模型接入页面"
                    @click="showLlmConfig = false"
                  >
                    ×
                  </button>
                </header>
                <div class="global-llm-shell-body">
                  <ModelProviderConfigPanel embedded />
                </div>
              </div>
            </div>
          </div>
        </transition>
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

.global-llm-modal {
  width: min(920px, calc(100vw - 32px));
  height: min(780px, calc(100vh - 32px));
  border-radius: 24px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 30px 90px rgba(15, 23, 42, 0.22);
  border: 1px solid rgba(148, 163, 184, 0.22);
  backdrop-filter: blur(12px);
}

.global-llm-shell {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.global-llm-shell-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 22px 24px 18px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  background:
    linear-gradient(135deg, rgba(79, 70, 229, 0.08), rgba(99, 102, 241, 0.02)),
    #ffffff;
}

.global-llm-shell-copy {
  display: grid;
  gap: 6px;
}

.global-llm-shell-eyebrow {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #6366f1;
}

.global-llm-shell-title {
  margin: 0;
  font-size: 24px;
  line-height: 1.15;
  color: #0f172a;
}

.global-llm-shell-desc {
  margin: 0;
  max-width: 640px;
  color: #475569;
  line-height: 1.6;
}

.global-llm-shell-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 18px 20px 20px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.92), rgba(255, 255, 255, 0.98));
}

.global-llm-overlay {
  position: fixed;
  inset: 0;
  z-index: 1190;
  display: grid;
  place-items: center;
  padding: 16px;
  background: rgba(15, 23, 42, 0.38);
  backdrop-filter: blur(6px);
}

.global-llm-close {
  flex-shrink: 0;
  width: 42px;
  height: 42px;
  border: 0;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.06);
  color: #0f172a;
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
}

.global-llm-close:hover {
  background: rgba(15, 23, 42, 0.12);
}

.llm-overlay-enter-active,
.llm-overlay-leave-active {
  transition: opacity 0.18s ease;
}

.llm-overlay-enter-active .global-llm-modal,
.llm-overlay-leave-active .global-llm-modal {
  transition: transform 0.18s ease, opacity 0.18s ease;
}

.llm-overlay-enter-from,
.llm-overlay-leave-to {
  opacity: 0;
}

.llm-overlay-enter-from .global-llm-modal,
.llm-overlay-leave-to .global-llm-modal {
  opacity: 0;
  transform: translateY(10px) scale(0.985);
}

@media (max-width: 768px) {
  .global-llm-fab {
    right: 14px;
    bottom: 14px;
    width: 54px;
    height: 54px;
  }

  .global-llm-modal {
    width: calc(100vw - 16px);
    height: calc(100vh - 16px);
    border-radius: 18px;
  }

  .global-llm-shell-header {
    padding: 18px 18px 14px;
  }

  .global-llm-shell-title {
    font-size: 21px;
  }

  .global-llm-shell-body {
    padding: 14px;
  }
}
</style>
