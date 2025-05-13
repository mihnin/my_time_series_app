<template>
  <div class="app-logs" v-if="isVisible">
    <h3 class="section-title">Логи приложения</h3>
    
    <div class="log-buttons">
      <button 
        @click="showLogs"
        class="log-button"
      >
        👁️ Показать логи
      </button>

      <button 
        @click="downloadLogs"
        class="log-button"
      >
        📥 Скачать логи
      </button>

      <button 
        @click="clearLogs"
        class="log-button clear-button"
      >
        🗑️ Очистить логи
      </button>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'AppLogs',
  
  props: {
    isVisible: {
      type: Boolean,
      default: false
    }
  },

  setup() {
    const showLogs = () => {
      console.log('Showing logs...')
    }

    const downloadLogs = () => {
      console.log('Downloading logs...')
    }

    const clearLogs = () => {
      console.log('Clearing logs...')
    }

    return {
      showLogs,
      downloadLogs,
      clearLogs
    }
  }
})
</script>

<style scoped>
.app-logs {
  margin-top: 2rem;
}

.section-title {
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 1.5rem;
  color: #333;
}

.log-buttons {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.log-button {
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

.log-button:hover {
  background-color: #1565c0;
}

.clear-button {
  background-color: #f44336;
}

.clear-button:hover {
  background-color: #d32f2f;
}
</style>
