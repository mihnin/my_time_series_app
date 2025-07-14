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
    <!-- Кнопка настроек БД теперь отдельный компонент -->
  </div>
</template>

<script lang="ts">
import { defineComponent, computed, ref } from 'vue'
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
    const showDbModal = ref(false)
    const secretWord = ref('')

    const canExport = computed(() => {
      // TODO: Add condition when models are trained
      return store.tableData.length > 0
    })

    const downloadModelsAndLogs = () => {
      // Download models and logs functionality
    }

    return {
      canExport,
      downloadModelsAndLogs,
      showDbModal,
      secretWord,
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

.db-connect-button {
  width: 100%;
  margin-top: 1rem;
  padding: 0.75rem;
  font-size: 1rem;
  font-weight: 500;
  color: white;
  background-color: #388e3c;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.db-connect-button:hover {
  background-color: #2e7031;
}

.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  position: relative;
  background: #fff;
  padding: 2rem;
  border-radius: 8px;
  min-width: 320px;
  box-shadow: 0 2px 16px rgba(0,0,0,0.15);
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.modal-close {
  position: absolute;
  top: 0.5rem;
  right: 0.7rem;
  background: none;
  border: none;
  font-size: 2rem;
  color: #888;
  cursor: pointer;
  z-index: 10;
}

.modal-close:active, .modal-close:focus {
  background: none !important;
  outline: none;
  box-shadow: none;
}

.modal-close:hover {
  color: #888;
}

.secret-input {
  width: 100%;
  padding: 0.5rem;
  font-size: 1rem;
  border: 1px solid #ccc;
  border-radius: 4px;
}

.modal-actions {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
}

.connect-btn {
  background: #388e3c;
  color: #fff;
  border: none;
  border-radius: 4px;
  padding: 0.5rem 1.2rem;
  font-weight: 500;
  cursor: pointer;
}

.connect-btn:hover {
  background: #2e7031;
}

.full-width {
  width: 100%;
  margin-top: 1rem;
}
</style>
