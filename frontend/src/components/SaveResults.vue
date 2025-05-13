<template>
  <div class="save-results" v-if="isVisible">
    <h3 class="section-title">Сохранение результатов прогноза</h3>
    
    <div class="save-buttons">
      <button 
        @click="saveToCsv"
        class="save-button"
        :disabled="!canSaveResults"
      >
        💾 Сохранить результаты в CSV
      </button>

      <button 
        @click="saveToExcel"
        class="save-button"
        :disabled="!canSaveResults"
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
    }
  },

  setup() {
    const store = useMainStore()

    const canSaveResults = computed(() => {
      // TODO: Add condition when predictions are available
      return store.tableData.length > 0
    })

    const saveToCsv = () => {
      console.log('Saving to CSV...')
    }

    const saveToExcel = () => {
      console.log('Saving to Excel...')
    }

    return {
      canSaveResults,
      saveToCsv,
      saveToExcel
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
