<template>
  <div class="app">
    <Sidebar :currentPage="currentPage" :handlePageChange="handlePageChange" />
    <div class="main-content">
      <div class="header">
        <h1>Версия 3.0</h1>
        <h2>Бизнес-приложение для прогнозирования временных рядов</h2>
      </div>
      <div class="page-content">

        <template v-if="store.predictionRows.length && store.predictionRows[0]">
          <div class="prediction-table">
            <h4>Первые 10 строк прогноза</h4>
            <table>
              <thead>
                <tr>
                  <th v-for="headerKey in Object.keys(store.predictionRows[0])" :key="headerKey">{{ headerKey }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in store.predictionRows" :key="row.item_id + '-' + row.timestamp">
                  <td v-for="cellHeaderKey in Object.keys(row)" :key="cellHeaderKey">{{ row[cellHeaderKey] }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>

        <template v-else-if="store.tableData.length && store.dateColumn !== '<нет>' && store.targetColumn !== '<нет>'">
          <TimeSeriesChart
            :data="store.tableData.slice(0, 1000)"
            :dateColumn="store.dateColumn"
            :targetColumn="store.targetColumn"
            :idColumn="store.idColumn !== '<нет>' ? store.idColumn : undefined"
          />
          <div v-if="store.sessionId && store.trainingStatus && store.trainingStatus.status === 'completed' && store.trainingStatus.leaderboard" class="leaderboard-table-main">
             <h4>Лидерборд моделей</h4>
            <table>
              <thead>
                <tr>
                  <th v-for="(value, key) in store.trainingStatus.leaderboard[0]" :key="key">{{ key }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, idx) in store.trainingStatus.leaderboard" :key="idx">
                  <td v-for="(value, key) in row" :key="key">{{ value }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>

        <template v-else-if="store.tableData.length">
           <DataTable :data="store.tableData" />
        </template>

        </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, watch } from 'vue'
import { useMainStore } from './stores/mainStore'
import Sidebar from './components/Sidebar.vue'
import DataTable from './components/DataTable.vue'
import TimeSeriesChart from './components/TimeSeriesChart.vue'

export default defineComponent({
  name: 'App',
  components: {
    Sidebar,
    DataTable,
    TimeSeriesChart
  },
  setup() {
    const store = useMainStore()
    const currentPage = ref('Главная')

    const handlePageChange = (page: string) => {
      currentPage.value = page
    }

    watch(
      () => store.predictionRows,
      (val) => {
        console.log('App.vue predictionRows watch triggered:', val);
      },
      { deep: true } // Add deep watch to detect changes in array elements
    )

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

.leaderboard-table-main {
  margin-top: 2rem;
  background-color: #fff;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  overflow-x: auto;
  padding: 1.5rem 1rem 1.5rem 1rem;
}
.leaderboard-table-main h4 {
  margin: 0 0 1rem 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: #1976d2;
  letter-spacing: 0.5px;
}
.leaderboard-table-main table {
  width: 100%;
  border-collapse: collapse;
  font-size: 1rem;
}
.leaderboard-table-main th, .leaderboard-table-main td {
  padding: 0.75rem 1rem;
  text-align: left;
  border-bottom: 1px solid #e0e0e0;
}
.leaderboard-table-main th {
  background-color: #f5f7fa;
  font-weight: 700;
  color: #333;
  border-top: 1px solid #e0e0e0;
}
.leaderboard-table-main tr:hover {
  background-color: #f0f7ff;
}
.leaderboard-table-main td {
  color: #222;
}

.prediction-table {
  margin-top: 2rem;
  background-color: #fff;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  overflow-x: auto;
  padding: 1.5rem 1rem 1.5rem 1rem;
}
.prediction-table h4 {
  margin: 0 0 1rem 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: #1976d2;
  letter-spacing: 0.5px;
}
.prediction-table table {
  width: 100%;
  border-collapse: collapse;
  font-size: 1rem;
}
.prediction-table th, .prediction-table td {
  padding: 0.75rem 1rem;
  text-align: left;
  border-bottom: 1px solid #e0e0e0;
}
.prediction-table th {
  background-color: #f5f7fa;
  font-weight: 700;
  color: #333;
  border-top: 1px solid #e0e0e0;
}
.prediction-table tr:hover {
  background-color: #f0f7ff;
}
.prediction-table td {
  color: #222;
}
</style>
