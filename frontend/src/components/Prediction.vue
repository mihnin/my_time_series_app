<template>
  <div class="prediction" v-if="isVisible">
    <h3 class="section-title">Прогноз</h3>
    
    <button 
      @click="makePrediction"
      class="predict-button"
      :disabled="!canMakePrediction"
    >
      📊 Сделать прогноз
    </button>
  </div>
</template>

<script lang="ts">
import { defineComponent, computed } from 'vue'
import { useMainStore } from '../stores/mainStore'

export default defineComponent({
  name: 'Prediction',
  
  props: {
    isVisible: {
      type: Boolean,
      default: false
    }
  },

  setup() {
    const store = useMainStore()

    const canMakePrediction = computed(() => {
      return store.tableData.length > 0 && 
             store.dateColumn !== '<нет>' && 
             store.targetColumn !== '<нет>'
    })

    const makePrediction = () => {
      console.log('Making prediction...')
    }

    return {
      canMakePrediction,
      makePrediction
    }
  }
})
</script>

<style scoped>
.prediction {
  margin-top: 2rem;
}

.section-title {
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 1.5rem;
  color: #333;
}

.predict-button {
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

.predict-button:hover:not(:disabled) {
  background-color: #1565c0;
}

.predict-button:disabled {
  background-color: #bbdefb;
  cursor: not-allowed;
}
</style>
