<template>
  <div class="metrics-and-models" v-if="isVisible">
    <h3 class="section-title">Метрика и модели</h3>
    
    <!-- Выбор метрики -->
    <div class="metric-select">
      <label>Метрика</label>
      <select v-model="selectedMetric">
        <option 
          v-for="(shortName, fullName) in metricsDict" 
          :key="fullName" 
          :value="fullName"
        >
          {{ fullName }}
        </option>
      </select>
    </div>

    <!-- Выбор моделей -->
    <div class="models-select">
      <label>Модели AutoGluon</label>
      <div class="selected-models">
        <div 
          v-for="model in selectedModels" 
          :key="model" 
          class="model-tag"
        >
          {{ model === '*' ? 'Все модели' : getModelDescription(model) }}
          <button @click="removeModel(model)" class="remove-model">×</button>
        </div>
      </div>
      <select 
        v-model="selectedModel"
        @change="addModel"
      >
        <option value="">Выберите модель</option>
        <option value="*" v-if="!selectedModels.includes('*')">Все модели</option>
        <option 
          v-for="(description, name) in agModels" 
          :key="name" 
          :value="name"
          v-if="!selectedModels.includes(name)"
        >
          {{ description }}
        </option>
      </select>
    </div>

    <!-- Пресет -->
    <div class="preset-select">
      <label>Пресет</label>
      <select v-model="selectedPreset">
        <option 
          v-for="preset in presetsList" 
          :key="preset" 
          :value="preset"
        >
          {{ preset }}
        </option>
      </select>
    </div>

    <!-- Лимит по времени -->
    <div class="time-limit-input">
      <label>Лимит по времени (сек)</label>
      <input 
        type="number" 
        v-model.number="timeLimit"
        min="1"
        placeholder="Без лимита"
      >
    </div>

    <!-- Чекбокс для mean -->
    <div class="mean-only-checkbox">
      <label>
        <input 
          type="checkbox" 
          v-model="meanOnly"
        > Прогнозировать только среднее (mean)
      </label>
    </div>

    <!-- Горизонт прогнозирования -->
    <div class="horizon-settings">
      <h3 class="section-title">Горизонт прогнозирования</h3>
      <div class="horizon-fields-vertical">
        <div class="horizon-input">
          <label>Горизонт</label>
          <input 
            type="number" 
            v-model.number="predictionHorizon"
            min="1"
            :class="{ invalid: !isValidHorizon }"
          >
        </div>
        <div class="horizon-unit-select">
          <label>Единица измерения</label>
          <select v-model="selectedHorizonUnit">
            <option v-for="option in frequencyOptions" :key="option" :value="option">{{ option }}</option>
          </select>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed } from 'vue'
import { useMainStore } from '../stores/mainStore'

export default defineComponent({
  name: 'MetricsAndModels',
  
  props: {
    isVisible: {
      type: Boolean,
      default: false
    }
  },

  setup() {
    const store = useMainStore()
    const selectedModel = ref('')

    const metricsDict = {
      "SQL (Scaled quantile loss)": "SQL",
      "WQL (Weighted quantile loss)": "WQL",
      "MAE (Mean absolute error)": "MAE",
      "MAPE (Mean absolute percentage error)": "MAPE",
      "MASE (Mean absolute scaled error)": "MASE",
      "MSE (Mean squared error)": "MSE",
      "RMSE (Root mean squared error)": "RMSE",
      "RMSLE (Root mean squared logarithmic error)": "RMSLE",
      "RMSSE (Root mean squared scaled error)": "RMSSE",
      "SMAPE (Symmetric mean absolute percentage error)": "SMAPE",
      "WAPE (Weighted absolute percentage error)": "WAPE"
    }

    const agModels: Record<string, string> = {
      "NaiveModel": "Базовая модель: прогноз = последнее наблюдение",
      "SeasonalNaiveModel": "Прогноз = последнее значение той же фазы сезона",
      "AverageModel": "Прогноз = среднее/квантиль",
      "SeasonalAverageModel": "Прогноз = среднее по тем же фазам сезона",
      "ZeroModel": "Прогноз = 0",
      "ETSModel": "Экспоненциальное сглаживание (ETS)",
      "AutoARIMAModel": "Автоматическая ARIMA",
      "AutoETSModel": "Автоматическая ETS",
      "AutoCESModel": "Комплексное экспоненциальное сглаживание (AIC)",
      "ThetaModel": "Theta",
      "ADIDAModel": "Intermittent demand (ADIDA)",
      "CrostonModel": "Intermittent demand (Croston)",
      "IMAPAModel": "Intermittent demand (IMAPA)",
      "NPTSModel": "Non-Parametric Time Series",
      "DeepARModel": "RNN (DeepAR)",
      "DLinearModel": "DLinear (убирает тренд)",
      "PatchTSTModel": "PatchTST (Transformer)",
      "SimpleFeedForwardModel": "Простая полносвязная сеть",
      "TemporalFusionTransformerModel": "LSTM + Transformer (TFT)",
      "TiDEModel": "Time series dense encoder",
      "WaveNetModel": "WaveNet (CNN)",
      "DirectTabularModel": "AutoGluon-Tabular (Direct)",
      "RecursiveTabularModel": "AutoGluon-Tabular (Recursive)",
      "Chronos": "Chronos Bolt model pretrained"
    }

    const presetsList = ["fast_training", "medium_quality", "high_quality", "best_quality"]

    const selectedMetric = computed({
      get: () => store.selectedMetric,
      set: (value: string) => store.setSelectedMetric(value)
    })

    const selectedModels = computed({
      get: () => store.selectedModels,
      set: (value: string[]) => store.setSelectedModels(value)
    })

    const selectedPreset = computed({
      get: () => store.selectedPreset,
      set: (value: string) => store.setSelectedPreset(value)
    })

    const predictionHorizon = computed({
      get: () => store.predictionHorizon,
      set: (value: number) => store.setPredictionHorizon(value)
    })

    const timeLimit = computed({
      get: () => store.timeLimit,
      set: (value: number | null) => store.setTimeLimit(value)
    })

    const meanOnly = computed({
      get: () => store.meanOnly,
      set: (value: boolean) => store.setMeanOnly(value)
    })

    const isValidHorizon = computed(() => {
      const value = predictionHorizon.value
      return Number.isInteger(value) && value > 0
    })

    const frequencyOptions = [
      "D (день)",
      "H (час)",
      "M (месяц)",
      "B (рабочие дни)",
      "W (неделя)",
      "Q (квартал)",
      "Y (год)"
    ]

    const selectedHorizonUnit = computed({
      get: () => store.horizonUnit,
      set: (value: string) => store.setHorizonUnit(value)
    })

    const getModelDescription = (modelName: string): string => {
      return modelName in agModels ? agModels[modelName] : modelName
    }

    const addModel = () => {
      if (selectedModel.value) {
        if (selectedModel.value === '*') {
          store.setSelectedModels(['*'])
        } else if (selectedModels.value.includes('*')) {
          store.setSelectedModels([selectedModel.value])
        } else {
          store.setSelectedModels([...selectedModels.value, selectedModel.value])
        }
        selectedModel.value = ''
      }
    }

    const removeModel = (model: string) => {
      store.setSelectedModels(selectedModels.value.filter(m => m !== model))
    }

    return {
      metricsDict,
      agModels,
      presetsList,
      selectedMetric,
      selectedModel,
      selectedModels,
      selectedPreset,
      predictionHorizon,
      timeLimit,
      meanOnly,
      isValidHorizon,
      frequencyOptions,
      selectedHorizonUnit,
      getModelDescription,
      addModel,
      removeModel
    }
  }
})
</script>

<style scoped>
.metrics-and-models {
  margin-top: 2rem;
}

.section-title {
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 1.5rem;
  color: #333;
}

.metric-select,
.models-select,
.preset-select,
.horizon-input,
.time-limit-input {
  margin-bottom: 1rem;
}

.metric-select label,
.models-select label,
.preset-select label,
.horizon-input label,
.time-limit-input label,
.mean-only-checkbox label {
  display: block;
  margin-bottom: 0.5rem;
  color: #666;
}

select,
input[type="number"] {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: white;
  font-size: 1rem;
}

input[type="number"].invalid {
  border-color: #d32f2f;
}

.selected-models {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.model-tag {
  display: inline-flex;
  align-items: center;
  background-color: #e3f2fd;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.9rem;
  color: #1976d2;
}

.remove-model {
  background: none;
  border: none;
  color: #666;
  margin-left: 0.5rem;
  cursor: pointer;
  padding: 0 0.25rem;
}

.remove-model:hover {
  color: #d32f2f;
}

select:disabled,
input:disabled {
  background-color: #f5f5f5;
  cursor: not-allowed;
}

.mean-only-checkbox {
  margin-top: 1rem;
}

.mean-only-checkbox label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.mean-only-checkbox input[type="checkbox"] {
  width: 1rem;
  height: 1rem;
  cursor: pointer;
}

.horizon-settings {
  margin-top: 1.5rem;
}

.horizon-fields {
  display: flex;
  gap: 0.5rem;
}

.horizon-fields-vertical {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.horizon-input,
.horizon-unit-select {
  flex: 1;
}

.horizon-unit-select {
  display: flex;
  flex-direction: column;
}

.horizon-unit-select label {
  display: block;
  margin-bottom: 0.5rem;
  color: #666;
}

.horizon-unit-select select {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: white;
  font-size: 1rem;
}
</style>
