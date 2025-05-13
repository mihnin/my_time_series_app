<template>
  <div class="missing-value-handler" v-if="isVisible">
    <h3 class="section-title">Обработка пропусков</h3>
    
    <!-- Способ заполнения пропусков -->
    <div class="fill-method-select">
      <label>Способ заполнения пропусков</label>
      <select v-model="selectedFillMethod">
        <option 
          v-for="option in fillOptions" 
          :key="option" 
          :value="option"
        >
          {{ option }}
        </option>
      </select>
    </div>

    <!-- Колонки для группировки -->
    <div class="grouping-columns" v-if="selectedFillMethod === 'Group mean (среднее по группе)'">
      <label>Колонки для группировки</label>
      <div class="selected-columns">
        <div 
          v-for="column in groupingColumns" 
          :key="column" 
          class="column-tag"
        >
          {{ column }}
          <button @click="removeGroupingColumn(column)" class="remove-column">×</button>
        </div>
      </div>
      <select 
        v-model="selectedGroupingColumn"
        @change="addGroupingColumn"
        :disabled="groupingColumns.length >= availableStaticFeatures.length"
      >
        <option value="">Выберите колонку</option>
        <option 
          v-for="column in availableStaticFeatures" 
          :key="column" 
          :value="column"
          v-if="!groupingColumns.includes(column)"
        >
          {{ column }}
        </option>
      </select>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed } from 'vue'
import { useMainStore } from '../stores/mainStore'

export default defineComponent({
  name: 'MissingValueHandler',
  
  props: {
    isVisible: {
      type: Boolean,
      default: false
    },
    availableStaticFeatures: {
      type: Array as () => string[],
      required: true
    }
  },

  setup(props) {
    const store = useMainStore()
    const selectedGroupingColumn = ref('')
    
    const fillOptions = [
      "None (оставить как есть)",
      "Constant=0 (заменить на нули)", 
      "Group mean (среднее по группе)", 
      "Forward fill (протянуть значения)", 
      "Interpolate (линейная интерполяция)", 
      "KNN imputer (k ближайших соседей)"
    ]

    const selectedFillMethod = computed({
      get: () => store.fillMethod,
      set: (value: string) => store.setFillMethod(value)
    })

    const groupingColumns = computed({
      get: () => store.groupingColumns,
      set: (value: string[]) => store.setGroupingColumns(value)
    })

    const addGroupingColumn = () => {
      if (selectedGroupingColumn.value) {
        store.setGroupingColumns([...groupingColumns.value, selectedGroupingColumn.value])
        selectedGroupingColumn.value = ''
      }
    }

    const removeGroupingColumn = (column: string) => {
      store.setGroupingColumns(groupingColumns.value.filter(c => c !== column))
    }

    return {
      fillOptions,
      selectedFillMethod,
      selectedGroupingColumn,
      groupingColumns,
      addGroupingColumn,
      removeGroupingColumn
    }
  }
})
</script>

<style scoped>
.missing-value-handler {
  margin-top: 2rem;
}

.section-title {
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 1.5rem;
  color: #333;
}

.fill-method-select {
  margin-bottom: 1rem;
}

.fill-method-select label,
.grouping-columns label {
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

.grouping-columns {
  margin-top: 1rem;
}

.selected-columns {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.column-tag {
  display: inline-flex;
  align-items: center;
  background-color: #e3f2fd;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.9rem;
  color: #1976d2;
}

.remove-column {
  background: none;
  border: none;
  color: #666;
  margin-left: 0.5rem;
  cursor: pointer;
  padding: 0 0.25rem;
}

.remove-column:hover {
  color: #d32f2f;
}

select:disabled {
  background-color: #f5f5f5;
  cursor: not-allowed;
}
</style>
