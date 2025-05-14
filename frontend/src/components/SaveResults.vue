<template>
  <div class="save-results" v-if="isVisible">
    <h3 class="section-title">Сохранение результатов прогноза</h3>
    
    <div class="save-buttons">
      <button 
        @click="saveToCsv"
        class="save-button"
        :disabled="!canSaveButton"
      >
        💾 Сохранить результаты в CSV
      </button>

      <button 
        @click="saveToExcel"
        class="save-button"
        :disabled="!canSaveButton"
      >
        💾 Сохранить результаты в Excel
      </button>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, computed } from 'vue'
import { useMainStore } from '../stores/mainStore'

export default defineComponent({
  name: 'SaveResults',
  
  props: {
    isVisible: {
      type: Boolean,
      default: false
    },
    canSave: {
      type: Boolean,
      default: false
    }
  },

  setup(props) {
    const store = useMainStore()

    const canSaveButton = computed(() => {
      // Кнопки должны быть активны, если есть sessionId и predictionRows (даже если canSave всегда true)
      return !!store.sessionId && store.predictionRows.length > 0
    })

    const saveToCsv = async () => {
      if (!store.sessionId) return
      const url = `http://localhost:8000/download_prediction_csv/${store.sessionId}`
      try {
        const response = await fetch(url)
        if (!response.ok) throw new Error('Ошибка скачивания CSV')
        const blob = await response.blob()
        const link = document.createElement('a')
        link.href = window.URL.createObjectURL(blob)
        link.download = `prediction_${store.sessionId}.csv`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
      } catch (e) {
        alert('Ошибка при скачивании CSV')
      }
    }

    const saveToExcel = async () => {
      if (!store.sessionId) return
      const url = `http://localhost:8000/download_prediction/${store.sessionId}`
      try {
        const response = await fetch(url)
        if (!response.ok) throw new Error('Ошибка скачивания Excel')
        const blob = await response.blob()
        const link = document.createElement('a')
        link.href = window.URL.createObjectURL(blob)
        link.download = `prediction_${store.sessionId}.xlsx`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
      } catch (e) {
        alert('Ошибка при скачивании Excel')
      }
    }

    return {
      saveToCsv,
      saveToExcel,
      canSaveButton
    }
  }
})
</script>

<style scoped>
.save-results {
  margin-top: 2rem;
}

.section-title {
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 1.5rem;
  color: #333;
}

.save-buttons {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.save-button {
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

.save-button:hover:not(:disabled) {
  background-color: #1565c0;
}

.save-button:disabled {
  background-color: #bbdefb;
  cursor: not-allowed;
}
</style>
