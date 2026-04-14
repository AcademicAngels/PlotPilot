<template>
  <div class="provider-panel">
    <header class="panel-header">
      <div class="header-main">
        <div class="title-row">
          <h3 class="panel-title">模型接入</h3>
          <n-tag size="small" round :bordered="false">OpenAI Compatible</n-tag>
        </div>
        <p class="panel-lead">
          管理 OpenAI 兼容协议接入。保存后会写入仓库根目录 <code>.env</code>，并同步到当前后端进程。
        </p>
      </div>
      <n-space class="header-actions" :size="8" align="center">
        <n-button size="small" tertiary @click="loadConfig" :disabled="loading">刷新</n-button>
        <n-button size="small" type="primary" :loading="saving" @click="save">保存</n-button>
      </n-space>
    </header>

    <div class="panel-content">
      <n-spin :show="loading">
        <n-space vertical :size="16" class="provider-stack">
          <n-alert type="info" :bordered="false">
            <code>chat</code> 适合只开放 <code>/chat/completions</code> 的网关，
            <code>responses</code> 适合原生 Responses API，
            <code>auto</code> 会在常规文本和 reasoning / previous_response_id 之间自动分流。
          </n-alert>

          <n-card size="small" :bordered="true" class="provider-card">
            <template #header>
              <div class="card-header">
                <div>
                  <div class="card-title">运行时配置</div>
                  <div class="card-desc">配置当前工作台实际使用的 OpenAI 兼容协议参数</div>
                </div>
              </div>
            </template>

            <n-form label-placement="top" :model="form" class="provider-form">
              <n-grid :cols="2" :x-gap="12">
                <n-form-item-gi label="LLM Provider">
                  <n-select
                    v-model:value="form.llm_provider"
                    :options="providerOptions"
                  />
                </n-form-item-gi>
                <n-form-item-gi label="协议模式">
                  <n-select
                    v-model:value="form.api_mode"
                    :options="apiModeOptions"
                  />
                </n-form-item-gi>
              </n-grid>

              <n-form-item label="Base URL">
                <n-input
                  v-model:value="form.base_url"
                  placeholder="https://your-gateway.example.com/v1"
                />
              </n-form-item>

              <n-grid :cols="2" :x-gap="12">
                <n-form-item-gi label="主模型">
                  <n-input v-model:value="form.model" placeholder="gpt-5.4" />
                </n-form-item-gi>
                <n-form-item-gi label="Embedding 模型">
                  <n-input v-model:value="form.embedding_model" placeholder="text-embedding-3-small" />
                </n-form-item-gi>
              </n-grid>

              <n-grid :cols="3" :x-gap="12">
                <n-form-item-gi label="超时（秒）">
                  <n-input-number v-model:value="form.timeout" :min="1" :max="600" style="width:100%" />
                </n-form-item-gi>
                <n-form-item-gi label="最大重试">
                  <n-input-number v-model:value="form.max_retries" :min="0" :max="10" style="width:100%" />
                </n-form-item-gi>
                <n-form-item-gi label="Embedding 维度">
                  <n-input-number v-model:value="form.embedding_dimension" :min="1" :max="32768" clearable style="width:100%" />
                </n-form-item-gi>
              </n-grid>

              <n-form-item label="API Key">
                <n-input
                  v-model:value="form.api_key"
                  type="password"
                  show-password-on="click"
                  placeholder="留空则保留现有密钥"
                />
              </n-form-item>

              <div class="key-row">
                <n-checkbox v-model:checked="form.clear_api_key">清除当前 API Key</n-checkbox>
                <n-text depth="3" v-if="maskedKey">当前已存：{{ maskedKey }}</n-text>
              </div>
            </n-form>
          </n-card>

          <n-card size="small" :bordered="true" class="provider-card">
            <template #header>
              <div class="card-header">
                <div>
                  <div class="card-title">标准示例</div>
                  <div class="card-desc">根据兼容能力选择合适的协议模式和模型入口</div>
                </div>
              </div>
            </template>

            <n-space vertical :size="12">
              <n-card
                v-for="example in examples"
                :key="example.name"
                size="small"
                embedded
                class="example-card"
              >
                <div class="example-head">
                  <strong>{{ example.name }}</strong>
                  <n-tag size="small" round>{{ example.api_mode }}</n-tag>
                </div>
                <div class="example-grid">
                  <div><span>Provider</span><code>{{ example.llm_provider }}</code></div>
                  <div><span>Base URL</span><code>{{ example.base_url }}</code></div>
                  <div><span>模型</span><code>{{ example.model }}</code></div>
                  <div><span>说明</span><span>{{ example.notes }}</span></div>
                </div>
              </n-card>
            </n-space>
          </n-card>
        </n-space>
      </n-spin>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { llmConfigApi, type LlmProviderExample, type LlmProviderConfigResponse } from '../../api/llmConfig'

const message = useMessage()

const loading = ref(false)
const saving = ref(false)
const examples = ref<LlmProviderExample[]>([])
const maskedKey = ref<string | null>(null)

const providerOptions = [
  { label: 'Anthropic（保留现状）', value: 'anthropic' },
  { label: 'OpenAI Compatible', value: 'openai' },
]

const apiModeOptions = [
  { label: 'auto', value: 'auto' },
  { label: 'chat', value: 'chat' },
  { label: 'responses', value: 'responses' },
]

const form = reactive({
  llm_provider: 'anthropic' as 'anthropic' | 'openai',
  api_key: '',
  clear_api_key: false,
  base_url: '',
  model: 'gpt-5.4',
  api_mode: 'auto' as 'auto' | 'chat' | 'responses',
  timeout: 120,
  max_retries: 2,
  embedding_model: 'text-embedding-3-small',
  embedding_dimension: null as number | null,
})

function applyConfig(config: LlmProviderConfigResponse) {
  form.llm_provider = config.llm_provider
  form.api_key = ''
  form.clear_api_key = false
  form.base_url = config.base_url
  form.model = config.model
  form.api_mode = config.api_mode
  form.timeout = config.timeout
  form.max_retries = config.max_retries
  form.embedding_model = config.embedding_model
  form.embedding_dimension = config.embedding_dimension
  examples.value = config.examples
  maskedKey.value = config.api_key_masked
}

async function loadConfig() {
  loading.value = true
  try {
    const config = await llmConfigApi.getConfig()
    applyConfig(config)
  } catch (error) {
    console.error(error)
    message.error('加载模型接入配置失败')
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const config = await llmConfigApi.updateConfig({
      llm_provider: form.llm_provider,
      api_key: form.api_key || undefined,
      clear_api_key: form.clear_api_key,
      base_url: form.base_url,
      model: form.model,
      api_mode: form.api_mode,
      timeout: form.timeout,
      max_retries: form.max_retries,
      embedding_model: form.embedding_model,
      embedding_dimension: form.embedding_dimension,
    })
    applyConfig(config)
    message.success('模型接入配置已保存')
  } catch (error) {
    console.error(error)
    message.error('保存模型接入配置失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadConfig()
})
</script>

<style scoped>
.provider-panel {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  padding: 12px 14px;
  border-bottom: 1px solid var(--aitext-split-border);
  background: var(--app-surface);
}

.header-main {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-title {
  margin: 0;
  font-size: 16px;
}

.panel-lead {
  margin: 0;
  color: var(--aitext-text-secondary, #666);
  line-height: 1.5;
}

.panel-content {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 14px;
}

.provider-stack {
  width: 100%;
}

.provider-card {
  background: var(--app-surface);
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.card-title {
  font-weight: 600;
}

.card-desc {
  font-size: 12px;
  color: var(--aitext-text-secondary, #666);
}

.provider-form {
  width: 100%;
}

.key-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.example-card {
  border: 1px solid var(--aitext-split-border);
}

.example-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
  margin-bottom: 10px;
}

.example-grid {
  display: grid;
  gap: 8px;
}

.example-grid div {
  display: grid;
  gap: 4px;
}

.example-grid span:first-child {
  font-size: 12px;
  color: var(--aitext-text-secondary, #666);
}

code {
  font-family: 'JetBrains Mono', 'SFMono-Regular', monospace;
}
</style>
