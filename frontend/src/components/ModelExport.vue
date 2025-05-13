<template>
  <div class="model-export" v-if="isVisible">
    <h3 class="section-title">Выгрузка моделей и логов</h3>
    
    <button 
      @click="downloadModelsAndLogs"
      class="export-button"
      :disabled="!canExport"
    >
      📦 Скачать архив (модели + логи)
    </button>
  </div>
</template>

<script lang="ts">
import { defineComponent, computed } from 'vue'
import { useMainStore } from '../stores/mainStore'

export default defineComponent({
  name: 'ModelExport',
  
  props: {
    isVisible: {
      type: Boolean,
      default: false
    }
  },

  setup() {
    const store = useMainStore()

    const canExport = computed(() => {
      // TODO: Add condition when models are trained
      return store.tableData.length > 0
    })

    const downloadModelsAndLogs = () => {
      console.log('Downloading models and logs...')
    }

    return {
      canExport,
      downloadModelsAndLogs
    }
  }
})
</script>

<style scoped>
.model-export {
  margin-top: 2rem;
}

.section-title {
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 1.5rem;
  color: #333;
}

.export-button {
  width: 100%;
  padding: 0.75rem;
  font-size: 1rem;
  font-weight: 500;
  color: white;
  background-color: #1976d2;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.export-button:hover:not(:disabled) {
  background-color: #1565c0;
}

.export-button:disabled {
  background-color: #bbdefb;
  cursor: not-allowed;
}
</style>
