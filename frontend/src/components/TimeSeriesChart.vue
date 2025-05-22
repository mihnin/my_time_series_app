<template>
  <div class="time-series-chart">
    <div v-if="!data.length || !dateColumn || !targetColumn" class="no-data">
      Выберите колонки с датой и целевой переменной
    </div>
    <div v-else ref="chartContainer" class="chart-container"></div>
  </div>
</template>

<script lang="ts">
import { defineComponent, onMounted, watch, ref, onUnmounted } from 'vue'
import * as echarts from 'echarts'

export default defineComponent({
  name: 'TimeSeriesChart',
  props: {
    data: {
      type: Array,
      required: true
    },
    dateColumn: {
      type: String,
      required: true
    },
    targetColumn: {
      type: String,
      required: true
    },
    idColumn: {
      type: String,
      default: null
    }
  },
  setup(props) {
    const chartContainer = ref<HTMLElement | null>(null)
    let chart: echarts.ECharts | null = null

    const updateChart = () => {
      if (!chartContainer.value || !props.data.length) return

      if (!chart) {
        chart = echarts.init(chartContainer.value)
      }

      // Ограничиваем количество отображаемых строк до 1000
      let limitedData = (props.data as Record<string, any>[]).slice(0, 1000)

      let series = []
      if (props.idColumn) {
        // Группировка только по тем строкам, которые попали в первые 1000
        const groups = new Map<string, Record<string, any>[]>()
        limitedData.forEach((row: Record<string, any>) => {
          const id = row[props.idColumn]
          if (!groups.has(id)) {
            if (groups.size >= 5) return // Ограничиваем до 5 уникальных id
            groups.set(id, [])
          }
          if (groups.has(id)) {
            groups.get(id)!.push(row)
          }
        })
        series = Array.from(groups.entries()).map(([id, rows]) => ({
          name: `${props.idColumn}: ${id}`,
          type: 'line',
          data: rows.map((row: Record<string, any>) => [row[props.dateColumn], row[props.targetColumn]]),
          smooth: false,
          showSymbol: false
        }))
      } else {
        // Без idColumn — просто строим одну серию
        series = [{
          type: 'line',
          data: limitedData.map((row: Record<string, any>) => [row[props.dateColumn], row[props.targetColumn]]),
          smooth: false,
          showSymbol: false
        }]
      }

      const option = {
        title: {
          text: props.idColumn 
            ? `Временной ряд с группировкой по ${props.idColumn}`
            : 'Временной ряд',
          left: 'center',
          textStyle: {
            fontWeight: 'normal', // убираем жирность заголовка
            fontSize: 16
          }
        },
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'cross'
          }
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: 60, // увеличено для подписи оси X
          containLabel: true
        },
        xAxis: {
          type: 'time',
          name: 'Дата',
          nameLocation: 'middle', // по центру под осью
          nameGap: 65, // уменьшено для смещения подписи выше на 5px
          axisLabel: {
            formatter: '{yyyy}-{MM}-{dd}'
          },
          nameTextStyle: {
            fontSize: 14,
            fontWeight: 'bold'
          }
        },
        yAxis: {
          type: 'value',
          name: 'Значение',
          nameLocation: 'middle', // ECharts: подпись по центру вертикальной оси
          nameGap: 40, // Оптимальный отступ
          nameTextStyle: {
            fontSize: 14,
            fontWeight: 'bold',
            padding: [0, 0, 0, 0] // Без лишнего сдвига
          }
        },
        series,
        legend: {
          show: Boolean(props.idColumn),
          type: 'scroll',
          orient: 'horizontal',
          top: 25,
          textStyle: {
            fontWeight: 'normal', // убираем жирность id
            fontSize: 14
          },
          itemWidth: 24,
          itemHeight: 14
        },
        dataZoom: [{
          type: 'inside',
          xAxisIndex: 0
        }, {
          type: 'slider',
          xAxisIndex: 0,
          height: 20
        }]
      }

      chart.setOption(option)
    }

    // Обработчик изменения размера окна
    const handleResize = () => {
      chart?.resize()
    }

    watch(() => [props.data, props.dateColumn, props.targetColumn, props.idColumn], updateChart, { deep: true })

    onMounted(() => {
      if (chartContainer.value) {
        updateChart()
      }
      window.addEventListener('resize', handleResize)
    })

    onUnmounted(() => {
      window.removeEventListener('resize', handleResize)
      chart?.dispose()
    })

    return {
      chartContainer
    }
  }
})
</script>

<style scoped>
.time-series-chart {
  width: 100%;
  height: 440px; /* увеличено для подписи */
  background: white;
  border-radius: 8px;
  padding: 0.5rem 1rem 0.5rem 1rem; /* уменьшен нижний padding */
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
}

.chart-container {
  width: 100%;
  flex: 1;
  min-height: 340px; /* увеличено для подписи */
  height: 100%;
}

.no-data {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #666;
  font-size: 1.1rem;
}
</style>