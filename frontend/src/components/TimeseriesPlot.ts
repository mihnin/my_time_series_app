import { defineComponent, ref, watch, onMounted } from 'vue';
import { Line } from 'vue-chartjs';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

export default defineComponent({
  name: 'TimeseriesPlot',
  components: {
    Line
  },
  props: {
    data: {
      type: Object,
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
      default: ''
    }
  },
  setup(props) {
    const chartData = ref({
      labels: [],
      datasets: []
    });

    const chartOptions = ref({
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top' as const,
        },
        title: {
          display: true,
          text: 'Временной ряд'
        }
      }
    });

    const prepareData = () => {
      if (!props.data || !props.dateColumn || !props.targetColumn) return;

      const sortedData = [...props.data].sort((a, b) => 
        new Date(a[props.dateColumn]).getTime() - new Date(b[props.dateColumn]).getTime()
      );

      if (props.idColumn) {
        // Группируем данные по ID
        const groupedData = {};
        sortedData.forEach(row => {
          const id = row[props.idColumn];
          if (!groupedData[id]) {
            groupedData[id] = {
              dates: [],
              values: []
            };
          }
          groupedData[id].dates.push(new Date(row[props.dateColumn]).toLocaleDateString());
          groupedData[id].values.push(parseFloat(row[props.targetColumn]));
        });

        chartData.value = {
          labels: Object.values(groupedData)[0]?.dates || [],
          datasets: Object.entries(groupedData).map(([id, data]) => ({
            label: `ID: ${id}`,
            data: data.values,
            fill: false,
            borderColor: getRandomColor(),
            tension: 0.1
          }))
        };
      } else {
        // Без группировки по ID
        const dates = sortedData.map(row => new Date(row[props.dateColumn]).toLocaleDateString());
        const values = sortedData.map(row => parseFloat(row[props.targetColumn]));

        chartData.value = {
          labels: dates,
          datasets: [{
            label: props.targetColumn,
            data: values,
            fill: false,
            borderColor: '#2196F3',
            tension: 0.1
          }]
        };
      }

      // Обновляем заголовок
      chartOptions.value.plugins.title.text = props.idColumn ? 
        `Временной ряд по ${props.targetColumn} (группировка по ${props.idColumn})` :
        `Временной ряд по ${props.targetColumn}`;
    };

    const getRandomColor = () => {
      const letters = '0123456789ABCDEF';
      let color = '#';
      for (let i = 0; i < 6; i++) {
        color += letters[Math.floor(Math.random() * 16)];
      }
      return color;
    };

    watch(() => props.data, prepareData, { deep: true });
    watch(() => props.dateColumn, prepareData);
    watch(() => props.targetColumn, prepareData);
    watch(() => props.idColumn, prepareData);

    onMounted(prepareData);

    return {
      chartData,
      chartOptions
    };
  },
  template: `
    <div class="timeseries-plot" style="height: 400px;">
      <Line
        v-if="chartData.labels.length > 0"
        :data="chartData"
        :options="chartOptions"
      />
    </div>
  `
});