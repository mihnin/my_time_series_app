<template>
  <div class="data-display">
    <div v-if="data && data.length" class="success-banner">
      Train-файл загружен! Строк: {{ totalRows }}, колонок: {{ columns.length }}
    </div>

    <div v-if="data && data.length" class="table-container">
      <table>
        <thead>
          <tr>
            <th v-for="column in columns" :key="column">{{ column }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in previewData" :key="index">
            <td v-for="column in columns" :key="column">{{ formatCellValue(row[column]) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="showPreviewInfo" class="preview-info">
      Показаны первые 1000 из {{ totalRows }} строк
    </div>

    <div v-if="numericStats" class="stats-container">
      <h3>Статистика Train</h3>
      <h4>Основная статистика для числовых столбцов:</h4>
      <table class="stats-table">
        <thead>
          <tr>
            <th></th>
            <th v-for="column in numericColumns" :key="column">{{ column }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="stat in ['count', 'mean', 'std', 'min', '25%', '50%', '75%', 'max']" :key="stat">
            <td>{{ stat }}</td>
            <td v-for="column in numericColumns" :key="column">
              {{ formatStatValue(numericStats[column][stat]) }}
            </td>
          </tr>
        </tbody>
      </table>
      
      <h4 class="missing-values-title">Количество пропусков (NaN) по столбцам:</h4>
      <table class="missing-values-table">
        <thead>
          <tr>
            <th>Столбец</th>
            <th>Пропуски</th>
          </tr>
        </thead>
        <tbody v-if="Object.keys(missingValues || {}).length">
          <tr v-for="(count, column) in missingValues" :key="column">
            <td>{{ column }}</td>
            <td>{{ formatCellValue(count) }}</td>
          </tr>
        </tbody>
        <tbody v-else>
          <tr v-for="column in columns" :key="column">
            <td>{{ column }}</td>
            <td>0</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, computed } from 'vue'

export default defineComponent({
  name: 'DataTable',
  props: {
    data: {
      type: Array,
      required: true
    }
  },
  setup(props) {
    const columns = computed(() => {
      return props.data.length > 0 ? Object.keys(props.data[0] as Record<string, any>) : []
    })

    const numericColumns = computed(() => {
      if (!props.data.length) return []
      return columns.value.filter(column => {
        const value = (props.data[0] as Record<string, any>)[column]
        return typeof value === 'number' || !isNaN(Number(value))
      })
    })

    const numericStats = computed(() => {
      if (!props.data.length || !numericColumns.value.length) return null
      
      const stats: Record<string, any> = {}
      numericColumns.value.forEach(column => {
        const values = (props.data as Record<string, any>[])
          .map(row => Number(row[column]))
          .filter(val => !isNaN(val))
        
        if (values.length === 0) return
        
        const sorted = [...values].sort((a, b) => a - b)
        const count = values.length
        const mean = values.reduce((a, b) => a + b, 0) / count
        const variance = values.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / count
        const std = Math.sqrt(variance)
        const min = sorted[0]
        const max = sorted[count - 1]
        const q25 = sorted[Math.floor(count * 0.25)]
        const q50 = sorted[Math.floor(count * 0.5)]
        const q75 = sorted[Math.floor(count * 0.75)]
        
        stats[column] = {
          count,
          mean,
          std,
          min,
          '25%': q25,
          '50%': q50,
          '75%': q75,
          max
        }
      })
      
      return stats
    })

    const formatStatValue = (value: number) => {
      if (typeof value !== 'number') return value
      if (Number.isInteger(value)) return value
      return value.toFixed(2)
    }

    // Форматирование дробных значений до 2 знаков после запятой
    const formatCellValue = (val: any) => {
      if (typeof val === 'number' && !Number.isInteger(val)) {
        return val.toFixed(2)
      }
      return val
    }

    const totalRows = computed(() => props.data.length)

    const previewData = computed(() => {
      return (props.data as Record<string, any>[]).slice(0, 1000)
    })

    const showPreviewInfo = computed(() => {
      return props.data.length > 1000
    })

    const missingValues = computed(() => {
      if (!props.data.length) return null
      const missing: Record<string, number> = {}
      columns.value.forEach(column => {
        const nullCount = (props.data as Record<string, any>[]).filter(row => 
          row[column] === null || 
          row[column] === undefined || 
          row[column] === '' || 
          (typeof row[column] === 'number' && isNaN(row[column]))
        ).length
        if (nullCount > 0) {
          missing[column] = nullCount
        }
      })
      return missing
    })

    return {
      columns,
      numericColumns,
      numericStats,
      totalRows,
      previewData,
      showPreviewInfo,
      formatStatValue,
      formatCellValue,
      missingValues
    }
  }
})
</script>

<style scoped>
.data-display {
  width: 100%;
}

.success-banner {
  width: 100%;
  padding: 1rem;
  background-color: #4CAF50;
  color: white;
  text-align: center;
  font-size: 1rem;
  font-weight: 500;
  margin-bottom: 1rem;
  border-radius: 4px;
  box-sizing: border-box;
}

.table-container {
  width: 100%;
  height: 400px;
  overflow: auto;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
  box-sizing: border-box;
}

table {
  width: 100%;
  min-width: max-content;
  border-collapse: collapse;
  table-layout: auto;
}

th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: #f5f5f5;
  padding: 0.75rem;
  text-align: left;
  border-bottom: 2px solid #ddd;
  font-weight: 600;
  white-space: nowrap;
}

td {
  padding: 0.75rem;
  border-bottom: 1px solid #eee;
  white-space: nowrap;
}

tr:hover {
  background-color: #f8f9fa;
}

.preview-info {
  width: 100%;
  padding: 1rem;
  background-color: #2196F3;
  color: white;
  text-align: center;
  margin-top: 1rem;
  border-radius: 4px;
  font-size: 1rem;
  font-weight: 500;
  box-sizing: border-box;
}

.stats-container {
  margin-top: 2rem;
  width: 100%;
  background: white;
  padding: 1rem;
  border-radius: 4px;
  border: 1px solid #ddd;
}

.stats-container h3 {
  font-size: 1.5rem;
  color: #333;
  margin-bottom: 0.5rem;
}

.stats-container h4 {
  font-size: 1rem;
  color: #666;
  margin-bottom: 1rem;
}

.stats-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 1rem;
}

.stats-table th,
.stats-table td {
  padding: 0.5rem;
  text-align: left;
  border: none;
  white-space: nowrap;
}

.stats-table th {
  background: #f5f5f5;
  font-weight: 600;
  position: sticky;
  top: 0;
}

.stats-table tr:nth-child(even) {
  background: #f9f9f9;
}

.stats-table tr:hover {
  background: #f0f0f0;
}

.missing-values-container {
  margin: 2rem 0;
  width: 100%;
  background: white;
  padding: 1rem;
  border-radius: 4px;
  border: 1px solid #ddd;
}

.missing-values-title {
  font-size: 1.1rem;
  color: #333;
  margin: 2rem 0 1rem;
}

.missing-values-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 0.5rem;
}

.missing-values-table th,
.missing-values-table td {
  padding: 0.5rem;
  text-align: left;
  border: none;
}

.missing-values-table th {
  background: #f5f5f5;
  font-weight: 600;
}

.missing-values-table tr:nth-child(even) {
  background: #f9f9f9;
}

.missing-values-table tr:hover {
  background: #f0f0f0;
}
</style>