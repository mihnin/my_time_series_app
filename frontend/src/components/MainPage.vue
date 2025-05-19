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
      <div v-if="store.sessionId && store.trainingStatus && store.trainingStatus.leaderboard && Array.isArray(store.trainingStatus.leaderboard)">
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
                <td v-for="(value, key) in row" :key="key">{{ formatCellValue(value) }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty-leaderboard-message" style="padding: 1rem; color: #f44336; text-align: center;">
            Никакая модель не обучилась. Попробуйте увеличить лимит по времени.
          </div>
        </div>
      </div>

      <!-- Уведомление об успешном прогнозе -->
      <div v-if="Array.isArray(store.predictionRows) && store.predictionRows.length > 0 && typeof store.predictionRows[0] === 'object' && store.predictionRows[0] !== null" class="success-banner">
        Прогноз успешно выполнен! Можете скачать таблицу с прогнозом в панели слева.
      </div>

      <div v-if="Array.isArray(store.predictionRows) && store.predictionRows.length > 0 && typeof store.predictionRows[0] === 'object' && store.predictionRows[0] !== null" ref="predictionTableBlock">
        <div class="prediction-table limited-height">
          <h4>Первые 10 строк прогноза</h4>
          <table>
            <thead>
              <tr>
                <th v-for="headerKey in Object.keys(store.predictionRows[0])" :key="headerKey" style="text-align: center;">{{ headerKey }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in store.predictionRows" :key="row.item_id + '-' + row.timestamp">
                <td v-for="cellHeaderKey in Object.keys(row)" :key="cellHeaderKey"
                    :style="{ minWidth: (getColWidth(cellHeaderKey) * 1.1) + 'ch', textAlign: 'center' }">
                  <template v-if="cellHeaderKey.toLowerCase().includes('date') || cellHeaderKey.toLowerCase().includes('timestamp')">
                    {{ typeof row[cellHeaderKey] === 'string' ? row[cellHeaderKey].split(' ')[0] : row[cellHeaderKey] }}
                  </template>
                  <template v-else>
                    {{ formatCellValue(row[cellHeaderKey]) }}
                  </template>
                </td>
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
import { defineComponent, nextTick, ref, watch } from 'vue'
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
    const predictionTableBlock = ref<HTMLElement | null>(null)

    // Функция для оценки ширины столбца по длине заголовка и первой строки
    function getColWidth(headerKey: string): number {
      const firstRow = store.predictionRows[0]?.[headerKey];
      const headerLen = headerKey.length;
      const valueLen = firstRow ? String(firstRow).length : 0;
      return Math.max(headerLen, valueLen, 8); // минимум 8 символов
    }

    // Форматирование дробных значений до 2 знаков после запятой
    function formatCellValue(val: any) {
      if (typeof val === 'number' && !Number.isInteger(val)) {
        return val.toFixed(2)
      }
      return val
    }

    // Скроллим к таблице прогноза при появлении новых predictionRows
    watch(
      () => store.predictionRows,
      (val) => {
        if (val && val.length > 0) {
          nextTick(() => {
            if (predictionTableBlock.value) {
              predictionTableBlock.value.scrollIntoView({ behavior: 'smooth', block: 'start' })
            }
          })
        }
      },
      { deep: true }
    )
    return { store, predictionTableBlock, getColWidth, formatCellValue }
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
.success-banner {
  width: 100%;
  padding: 1rem;
  background-color: #4CAF50;
  color: white;
  text-align: center;
  font-size: 1rem;
  font-weight: 500;
  margin: 1.5rem 0 1.5rem 0;
  border-radius: 4px;
  box-sizing: border-box;
}
</style>
