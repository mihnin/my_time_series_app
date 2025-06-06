<template>
  <div class="column-selector" v-if="isVisible">
    <h3 class="section-title">Колонки датасета</h3>
    
    <!-- Колонка с датой -->
    <div class="column-select">
      <label>Колонка с датой</label>
      <select v-model="selectedDateColumn">
        <option value="<нет>">&lt;нет&gt;</option>
        <option v-for="column in availableColumns" :key="column" :value="column">
          {{ column }}
        </option>
      </select>
    </div>

    <!-- Колонка target -->
    <div class="column-select">
      <label>Колонка target</label>
      <select v-model="selectedTargetColumn">
        <option value="<нет>">&lt;нет&gt;</option>
        <option v-for="column in availableColumns" :key="column" :value="column">
          {{ column }}
        </option>
      </select>
    </div>

    <!-- Колонка ID -->
    <div class="column-select">
      <label>Колонка ID (категориальный)</label>
      <select v-model="selectedIdColumn">
        <option value="<нет>">&lt;нет&gt;</option>
        <option v-for="column in availableColumns" :key="column" :value="column">
          {{ column }}
        </option>
      </select>
    </div>

    <!-- Статические признаки -->
    <div class="static-features">
      <h3>Статические признаки (до 3)</h3>
      <div class="selected-features">
        <div 
          v-for="feature in staticFeatures" 
          :key="feature" 
          class="feature-tag"
        >
          {{ feature }}
          <button @click="removeStaticFeature(feature)" class="remove-feature">×</button>
        </div>
      </div>
      <select 
        v-model="selectedFeature"
        :disabled="staticFeatures.length >= 3"
        @change="addStaticFeature"
      >
        <option value="">Выберите признак</option>
        <option 
          v-for="column in availableStaticFeatures" 
          :key="column" 
          :value="column"
        >
          {{ column }}
        </option>
      </select>
      
      <!-- Чекбокс для праздников -->
      <div class="holidays-checkbox">
        <label>
          <input 
            type="checkbox" 
            v-model="considerHolidays"
          > Учитывать праздники РФ?
        </label>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed } from 'vue'
import { useMainStore } from '../stores/mainStore'

export default defineComponent({
  name: 'ColumnSelector',
  
  props: {
    isVisible: {
      type: Boolean,
      default: false
    }
  },

  setup() {
    const store = useMainStore()
    const selectedFeature = ref('')

    const selectedDateColumn = computed({
      get: () => store.dateColumn,
      set: (value: string) => store.setDateColumn(value)
    })

    const selectedTargetColumn = computed({
      get: () => store.targetColumn,
      set: (value: string) => store.setTargetColumn(value)
    })

    const selectedIdColumn = computed({
      get: () => store.idColumn,
      set: (value: string) => store.setIdColumn(value)
    })

    const staticFeatures = computed({
      get: () => store.staticFeatures,
      set: (value: string[]) => store.setStaticFeatures(value)
    })

    const availableColumns = computed(() => {
      if (!store.tableData.length) return []
      return Object.keys(store.tableData[0])
    })

    const availableStaticFeatures = computed(() => {
      if (!store.tableData.length) return []
      return availableColumns.value.filter(column => 
        column !== selectedDateColumn.value &&
        column !== selectedTargetColumn.value &&
        column !== selectedIdColumn.value &&
        column !== '<нет>' &&
        !staticFeatures.value.includes(column)
      )
    })

    const addStaticFeature = () => {
      if (selectedFeature.value && staticFeatures.value.length < 3) {
        store.setStaticFeatures([...staticFeatures.value, selectedFeature.value])
        selectedFeature.value = ''
      }
    }

    const removeStaticFeature = (feature: string) => {
      store.setStaticFeatures(staticFeatures.value.filter(f => f !== feature))
    }

    const considerHolidays = computed({
      get: () => store.considerRussianHolidays,
      set: (value: boolean) => store.setConsiderRussianHolidays(value)
    })

    return {
      selectedDateColumn,
      selectedTargetColumn,
      selectedIdColumn,
      staticFeatures,
      selectedFeature,
      availableColumns,
      availableStaticFeatures,
      addStaticFeature,
      removeStaticFeature,
      considerHolidays
    }
  }
})
</script>

<style scoped>
.column-selector {
  margin-top: 2rem;
}

.section-title {
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 1.5rem;
  color: #333;
}

.column-select {
  margin-bottom: 1rem;
}

.column-select label {
  display: block;
  margin-bottom: 0.5rem;
  color: #666;
}

.column-select select,
.static-features select {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: white;
  font-size: 1rem;
}

.static-features {
  margin-top: 2rem;
}

.static-features h3 {
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 1.5rem;
  color: #333;
}

.selected-features {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.feature-tag {
  display: inline-flex;
  align-items: center;
  background-color: #e3f2fd;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.9rem;
  color: #1976d2;
}

.remove-feature {
  background: none;
  border: none;
  color: #666;
  margin-left: 0.5rem;
  cursor: pointer;
  padding: 0 0.25rem;
}

.remove-feature:hover {
  color: #d32f2f;
}

select:disabled {
  background-color: #f5f5f5;
  cursor: not-allowed;
}

.subsection-title {
  font-size: 1rem;
  color: #666;
  margin: 1rem 0 0.5rem;
}

.holidays-checkbox {
  margin-top: 1rem;
  font-size: 0.9rem;
  color: #333;
}

.holidays-checkbox label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.holidays-checkbox input[type="checkbox"] {
  width: 1rem;
  height: 1rem;
  cursor: pointer;
}
</style>