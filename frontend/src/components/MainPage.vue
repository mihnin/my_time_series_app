<template>
  <div class="page-content">
    <template v-if="store.dateColumn !== '<нет>' && store.targetColumn !== '<нет>' && store.tableData.length">
      <TimeSeriesChart
        :data="store.tableData.slice(0, 1000)"
        :dateColumn="store.dateColumn"
        :targetColumn="store.targetColumn"
        :idColumn="store.idColumn !== '<нет>' ? store.idColumn : undefined"
      />

      <!-- Лидерборд показываем если нет прогноза ИЛИ если trainPredictSave включён -->
      <div v-if="((!Array.isArray(store.predictionRows) || store.predictionRows.length === 0) || store.trainPredictSave) && store.sessionId && store.trainingStatus && store.trainingStatus.leaderboard && Array.isArray(store.trainingStatus.leaderboard)">
        <div class="leaderboard-table-main">
          <h4>Лидерборд моделей</h4>
          <table v-if="store.trainingStatus.leaderboard.length > 0 && typeof store.trainingStatus.leaderboard[0] === 'object' && store.trainingStatus.leaderboard[0] !== null">
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
          <div v-else class="empty-leaderboard-message" style="padding: 1rem; color: #f44336; text-align: center;">
            Никакая модель не обучилась. Попробуйте увеличить лимит по времени.
          </div>
        </div>
      </div>

      <div v-if="Array.isArray(store.predictionRows) && store.predictionRows.length > 0 && typeof store.predictionRows[0] === 'object' && store.predictionRows[0] !== null">
        <div class="prediction-table limited-height">
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
      </div>
    </template>

    <template v-else-if="store.tableData.length && (store.dateColumn === '<нет>' || store.targetColumn === '<нет>')">
      <DataTable :data="store.tableData" />
    </template>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue'
import { useMainStore } from '../stores/mainStore'
import DataTable from '../components/DataTable.vue'
import TimeSeriesChart from '../components/TimeSeriesChart.vue'

export default defineComponent({
  name: 'MainPage',
  components: {
    DataTable,
    TimeSeriesChart
  },
  setup() {
    const store = useMainStore()
    // watch для очистки leaderboard больше не нужен
    return { store }
  }
})
</script>

<style scoped>
.page-content {
  flex: 1;
  width: 100%;
  min-width: 0;
  padding: 1rem;
}
.page-content > div {
  display: flex;
  flex-direction: column;
}
</style>
