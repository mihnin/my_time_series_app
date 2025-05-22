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
          v-for="(description, key) in agModels" 
          :key="key" 
          :value="key"
          :disabled="selectedModels.includes(key)"
        >
          {{ description }}
        </option>
      </select>
    </div>

    <!-- Выбор моделей PyCaret -->
    <div class="models-select">
      <label>Модели PyCaret</label>
      <div class="selected-models">
        <div 
          v-for="model in selectedPycaretModels" 
          :key="model" 
          class="model-tag"
        >
          {{ model === '*' ? 'Все модели' : getPycaretModelDescription(model) }}
          <button @click="removePycaretModel(model)" class="remove-model">×</button>
        </div>
      </div>
      <select 
        v-model="selectedPycaretModel"
        @change="addPycaretModel"
      >
        <option value="">Выберите модель</option>
        <option value="*" v-if="!selectedPycaretModels.includes('*')">Все модели</option>
        <option 
          v-for="(description, key) in pycaretModels" 
          :key="key" 
          :value="key"
          :disabled="selectedPycaretModels.includes(key)"
        >
          {{ description }}
        </option>
      </select>
    </div>

    <!-- Пресет -->
    <div class="preset-select">
      <label>Пресет AutoGluon</label>
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
    const selectedPycaretModel = ref('')
    const metricsDict = {
      "MAE (Mean absolute error)": "MAE",
      "MAPE (Mean absolute percentage error)": "MAPE",
      "MASE (Mean absolute scaled error)": "MASE",
      "MSE (Mean squared error)": "MSE",
      "RMSE (Root mean squared error)": "RMSE",
      "RMSSE (Root mean squared scaled error)": "RMSSE",
      "SMAPE (Symmetric mean absolute percentage error)": "SMAPE"
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

    // PyCaret models (id: display name)
    const pycaretModels: Record<string, string> = {
      '*': 'Все модели',
      'naive': 'Naive Forecaster',
      'grand_means': 'Grand Means Forecaster',
      'snaive': 'Seasonal Naive Forecaster',
      'polytrend': 'Polynomial Trend Forecaster',
      'arima': 'ARIMA',
      'exp_smooth': 'Exponential Smoothing',
      'ets': 'ETS',
      'theta': 'Theta Forecaster',
      'stlf': 'STLF',
      'croston': 'Croston',
      'bats': 'BATS',
      'tbats': 'TBATS',
      'lr_cds_dt': 'Linear w/ Cond. Deseasonalize & Detrending',
      'en_cds_dt': 'Elastic Net w/ Cond. Deseasonalize & Detrending',
      'ridge_cds_dt': 'Ridge w/ Cond. Deseasonalize & Detrending',
      'lasso_cds_dt': 'Lasso w/ Cond. Deseasonalize & Detrending',
      'llar_cds_dt': 'Lasso Least Angular Regressor w/ Cond. Deseasonalize & Detrending',
      'br_cds_dt': 'Bayesian Ridge w/ Cond. Deseasonalize & Detrending',
      'huber_cds_dt': 'Huber w/ Cond. Deseasonalize & Detrending',
      'omp_cds_dt': 'Orthogonal Matching Pursuit w/ Cond. Deseasonalize & Detrending',
      'knn_cds_dt': 'K Neighbors w/ Cond. Deseasonalize & Detrending',
      'dt_cds_dt': 'Decision Tree w/ Cond. Deseasonalize & Detrending',
      'rf_cds_dt': 'Random Forest w/ Cond. Deseasonalize & Detrending',
      'et_cds_dt': 'Extra Trees w/ Cond. Deseasonalize & Detrending',
      'gbr_cds_dt': 'Gradient Boosting w/ Cond. Deseasonalize & Detrending',
      'ada_cds_dt': 'AdaBoost w/ Cond. Deseasonalize & Detrending',
      'xgboost_cds_dt': 'Extreme Gradient Boosting w/ Cond. Deseasonalize & Detrending',
      'lightgbm_cds_dt': 'Light Gradient Boosting w/ Cond. Deseasonalize & Detrending',
      'catboost_cds_dt': 'CatBoost Regressor w/ Cond. Deseasonalize & Detrending',
    }

    const presetsList = [
      "fast_training",
      "medium_quality",
      "high_quality",
      "best_quality"
    ]

    const selectedMetric = computed({
      get: () => {
        console.log('Current selectedMetric from store:', store.selectedMetric); // Add this line
        return store.selectedMetric || 'MAE (Mean absolute error)';
      },
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

    const addPycaretModel = () => {
      if (selectedPycaretModel.value) {
        if (selectedPycaretModel.value === '*') {
          store.setSelectedPycaretModels(['*'])
        } else if (selectedPycaretModels.value.includes('*')) {
          store.setSelectedPycaretModels([selectedPycaretModel.value])
        } else {
          store.setSelectedPycaretModels([...selectedPycaretModels.value, selectedPycaretModel.value])
        }
        selectedPycaretModel.value = ''
      }
    }
    const removePycaretModel = (model: string) => {
      store.setSelectedPycaretModels(selectedPycaretModels.value.filter(m => m !== model))
    }
    const getPycaretModelDescription = (modelId: string): string => {
      return modelId in pycaretModels ? pycaretModels[modelId] : modelId
    }

    const selectedPycaretModels = computed({
      get: () => store.selectedPycaretModels,
      set: (value: string[]) => store.setSelectedPycaretModels(value)
    })

    return {
      metricsDict,
      agModels,
      pycaretModels,
      presetsList,
      selectedMetric,
      selectedModel,
      selectedModels,
      selectedPycaretModel,
      selectedPreset,
      predictionHorizon,
      timeLimit,
      meanOnly,
      isValidHorizon,
      frequencyOptions,
      selectedHorizonUnit,
      getModelDescription,
      addModel,
      removeModel,
      getPycaretModelDescription,
      addPycaretModel,
      removePycaretModel,
      selectedPycaretModels
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
