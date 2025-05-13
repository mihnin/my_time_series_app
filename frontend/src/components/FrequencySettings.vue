<template>
  <div class="frequency-settings" v-if="isVisible">
    <h3 class="section-title">Сезонность</h3>
    
    <!-- Выбор сезонности -->
    <div class="frequency-select">
      <label>Сезонность</label>
      <select v-model="selectedFrequency">
        <option 
          v-for="option in frequencyOptions" 
          :key="option" 
          :value="option"
        >
          {{ option }}
        </option>
      </select>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, computed } from 'vue'
import { useMainStore } from '../stores/mainStore'

export default defineComponent({
  name: 'FrequencySettings',
  
  props: {
    isVisible: {
      type: Boolean,
      default: false
    }
  },

  setup() {
    const store = useMainStore()
    
    const frequencyOptions = [
      "auto (угадать)", 
      "D (день)", 
      "H (час)", 
      "M (месяц)", 
      "B (рабочие дни)", 
      "W (неделя)", 
      "Q (квартал)"
    ]

    const selectedFrequency = computed({
      get: () => store.frequency,
      set: (value: string) => store.setFrequency(value)
    })

    return {
      frequencyOptions,
      selectedFrequency
    }
  }
})
</script>

<style scoped>
.frequency-settings {
  margin-top: 2rem;
}

.section-title {
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 1.5rem;
  color: #333;
}

.frequency-select {
  margin-bottom: 1rem;
}

.frequency-select label {
  display: block;
  margin-bottom: 0.5rem;
  color: #666;
}

select {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: white;
  font-size: 1rem;
}

select:disabled {
  background-color: #f5f5f5;
  cursor: not-allowed;
}
</style>
