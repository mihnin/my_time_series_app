<template>
  <div class="app">
    <div class="sidebar">
      <Navigation @page-change="handlePageChange" />
      <TrainingSettings v-if="currentPage === 'Главная'" />
    </div>
    
    <div class="main-content">
      <div class="header">
        <h1>Версия 3.0</h1>
        <h2>Бизнес-приложение для прогнозирования временных рядов</h2>
      </div>
      
      <div class="page-content">
        <TimeSeriesChart
          v-if="store.tableData.length && store.dateColumn !== '<нет>' && store.targetColumn !== '<нет>'"
          :data="store.tableData"
          :dateColumn="store.dateColumn"
          :targetColumn="store.targetColumn"
          :idColumn="store.idColumn !== '<нет>' ? store.idColumn : null"
        />
        <div v-else>
          <DataTable v-if="store.tableData.length" :data="store.tableData" />
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref } from 'vue'
import { useMainStore } from './stores/mainStore'
import Navigation from './components/Navigation.vue'
import TrainingSettings from './components/TrainingSettings.vue'
import DataTable from './components/DataTable.vue'
import TimeSeriesChart from './components/TimeSeriesChart.vue'

export default defineComponent({
  name: 'App',
  components: {
    Navigation,
    TrainingSettings,
    DataTable,
    TimeSeriesChart
  },
  setup() {
    const store = useMainStore()
    const currentPage = ref('Главная')

    const handlePageChange = (page: string) => {
      currentPage.value = page
    }

    return {
      store,
      currentPage,
      handlePageChange
    }
  }
})
</script>

<style>
html, body {
  margin: 0;
  padding: 0;
  height: 100%;
  width: 100%;
  overflow-x: hidden;
}

.app {
  display: flex;
  min-height: 100vh;
  width: 100%;
}

.sidebar {
  width: 400px;
  min-width: 400px;
  background-color: #f5f5f5;
  padding: 1rem;
  border-right: 1px solid #ddd;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  overflow-y: auto;
  z-index: 10;
  box-sizing: border-box;
}

.main-content {
  position: absolute;
  left: 400px;
  right: 0;
  top: 0;
  bottom: 0;
  padding: 1rem;
  overflow-y: auto;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

.header {
  margin-bottom: 2rem;
  flex-shrink: 0;
}

.header h1 {
  font-size: 1rem;
  color: #666;
  margin: 0;
}

.header h2 {
  font-size: 1.5rem;
  color: #333;
  margin: 0.5rem 0 0;
}

.page-content {
  flex: 1;
  width: 100%;
  min-width: 0;
  padding: 1rem;
}

.page-content > div {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.data-container {
  display: flex;
  gap: 1rem;
  height: 100%;
}

.data-table-section {
  flex: 1;
  min-width: 0;
}

.chart-section {
  flex: 1;
  min-width: 0;
}
</style>
