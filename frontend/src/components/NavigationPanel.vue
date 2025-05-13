<template>
  <div class="navigation-panel">
    <div class="column-select">
      <h3>Выбор колонок</h3>
      
      <div class="select-group">
        <label>Колонка с датой:</label>
        <select v-model="store.dateColumn">
          <option value="<нет>">&lt;нет&gt;</option>
          <option v-for="col in availableColumns" :key="col" :value="col">{{ col }}</option>
        </select>
      </div>

      <div class="select-group">
        <label>Целевая колонка:</label>
        <select v-model="store.targetColumn">
          <option value="<нет>">&lt;нет&gt;</option>
          <option v-for="col in availableColumns" :key="col" :value="col">{{ col }}</option>
        </select>
      </div>

      <div class="select-group">
        <label>Колонка ID:</label>
        <select v-model="store.idColumn">
          <option value="<нет>">&lt;нет&gt;</option>
          <option v-for="col in availableColumns" :key="col" :value="col">{{ col }}</option>
        </select>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, computed } from 'vue'
import { useMainStore } from '../stores/mainStore'

export default defineComponent({
  name: 'NavigationPanel',
  setup() {
    const store = useMainStore()

    const availableColumns = computed(() => {
      if (!store.tableData.length) return []
      return Object.keys(store.tableData[0])
    })

    return {
      store,
      availableColumns
    }
  }
})
</script>

<style scoped>
.navigation-panel {
  padding: 1rem;
}

.column-select {
  margin-bottom: 2rem;
}

h3 {
  margin-bottom: 1rem;
  color: #333;
  font-size: 1.1rem;
}

.select-group {
  margin-bottom: 1rem;
}

label {
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
}

select:focus {
  outline: none;
  border-color: #4CAF50;
}
</style>