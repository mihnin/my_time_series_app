<template>
  <div class="training" v-if="isVisible">
    <h3 class="section-title">Обучение модели</h3>
    
    <!-- Чекбокс для комплексного действия -->
    <div class="training-checkbox">
      <label>
        <input 
          type="checkbox" 
          v-model="trainPredictSave"
        > Обучение, Прогноз и Сохранение
      </label>
    </div>

    <!-- Блок с прогрессом обучения -->
    <div v-if="trainingStatus" class="training-status">
      <div class="progress-container">
        <div 
          class="progress-bar" 
          :style="{ width: `${trainingStatus.progress}%` }"
          :class="{ 'progress-error': trainingStatus.status === 'failed' }"
        ></div>
      </div>
      <div class="status-text">
        {{ getStatusMessage }}
      </div>
      <div v-if="trainingStatus.status === 'failed'" class="error-message">
        {{ trainingStatus.error }}
      </div>
    </div>

    <!-- Кнопка обучения -->
    <button 
      @click="startTraining"
      class="train-button"
      :disabled="!canStartTraining || isTraining"
    >
     {{ buttonText }}
    </button>
  </div>
</template>

<script lang="ts">
import { defineComponent, computed, ref } from 'vue'
import { useMainStore } from '../stores/mainStore'

export default defineComponent({
  name: 'Training',
  
  props: {
    isVisible: {
      type: Boolean,
      default: false
    }
  },

  setup() {
    const store = useMainStore()
    const currentSessionId = ref<string | null>(null)
    const trainingStatus = ref<any>(null)
    const statusCheckInterval = ref<number | null>(null)

    const trainPredictSave = computed({
      get: () => store.trainPredictSave,
      set: (value: boolean) => store.setTrainPredictSave(value)
    })

    const isTraining = computed(() => {
      return trainingStatus.value && ['initializing', 'running'].includes(trainingStatus.value.status)
    })

    const buttonText = computed(() => {
      if (!isTraining.value) return '🚀 Обучить модель'
      return '⏳ Обучение...'
    })

    const getStatusMessage = computed(() => {
      if (!trainingStatus.value) return ''
      
      const status = trainingStatus.value.status
      if (status === 'initializing') return 'Инициализация обучения...'
      if (status === 'running') return `Обучение в процессе (${trainingStatus.value.progress}%)`
      if (status === 'completed') return 'Обучение успешно завершено!'
      if (status === 'failed') return 'Ошибка при обучении'
      return status
    })

    const canStartTraining = computed(() => {
      return store.selectedFile !== null && 
             store.tableData.length > 0 && 
             store.dateColumn !== '<нет>' && 
             store.targetColumn !== '<нет>' &&
             !isTraining.value
    })

    const checkTrainingStatus = async () => {
      if (!currentSessionId.value) return
      
      try {
        const response = await fetch(`http://localhost:8000/training_status/${currentSessionId.value}`)
        if (!response.ok) {
          throw new Error('Failed to fetch training status')
        }
        
        const status = await response.json()
        trainingStatus.value = status

        // Stop checking if training is complete or failed
        if (['completed', 'failed'].includes(status.status)) {
          if (statusCheckInterval.value) {
            clearInterval(statusCheckInterval.value)
            statusCheckInterval.value = null
          }

          // Show final status
          if (status.status === 'completed') {
            alert('Обучение модели успешно завершено!')
          } else if (status.status === 'failed') {
            alert(`Ошибка при обучении: ${status.error}`)
          }
        }
      } catch (error) {
        console.error('Error checking training status:', error)
      }
    }

    const startTraining = async () => {
      try {
        const formData = new FormData();
        
        if (store.selectedFile) {
          formData.append('training_file', store.selectedFile);
        } else {
          console.error('No file selected - please upload a file first');
          alert('Ошибка: Файл не выбран. Пожалуйста, загрузите файл перед обучением модели.');
          return;
        }

        const params = {
          datetime_column: store.dateColumn,
          target_column: store.targetColumn,
          item_id_column: store.idColumn,
          frequency: store.frequency === 'auto (угадать)' ? 'auto' : store.frequency,
          fill_missing_method: store.fillMethod === 'None (оставить как есть)' ? 'None' : store.fillMethod,
          fill_group_columns: store.groupingColumns,
          use_russian_holidays: store.considerRussianHolidays,
          evaluation_metric: store.selectedMetric.split(' ')[0],
          models_to_train: store.selectedModels[0] === '*' ? null : store.selectedModels,
          autogluon_preset: store.selectedPreset,
          predict_mean_only: store.meanOnly,
          prediction_length: store.predictionHorizon,
          training_time_limit: store.timeLimit,
          static_feature_columns: store.staticFeatures
        };

        const paramsJson = JSON.stringify(params);
        formData.append('params', paramsJson);

        const response = await fetch('http://localhost:8000/train_timeseries_model/', {
          method: 'POST',
          body: formData,
          headers: {
            'Accept': 'application/json',
          }
        });

        if (!response.ok) {
          const errorText = await response.text();
          let errorData;
          try {
            errorData = JSON.parse(errorText);
          } catch (e) {
            errorData = { detail: errorText };
          }
          
          const errorMessage = errorData.detail || 'Failed to train model';
          console.error('Training error:', errorMessage);
          alert(`Ошибка обучения: ${errorMessage}`);
          throw new Error(errorMessage);
        }

        const result = await response.json();
        console.log('Training started successfully:', result);
        
        // Save session ID and start status checking
        currentSessionId.value = result.session_id
        trainingStatus.value = { status: 'initializing', progress: 0 }
        
        // Start checking status periodically
        if (statusCheckInterval.value) {
          clearInterval(statusCheckInterval.value)
        }
        statusCheckInterval.value = setInterval(checkTrainingStatus, 2000) as unknown as number

      } catch (error) {
        console.error('Error during training:', error);
        if (error instanceof Error && !error.message.includes('Файл не выбран')) {
          alert('Произошла ошибка при обучении модели. Подробности в консоли.');
        }
      }
    }

    return {
      trainPredictSave,
      canStartTraining,
      startTraining,
      trainingStatus,
      isTraining,
      buttonText,
      getStatusMessage
    }
  }
})
</script>

<style scoped>
.training {
  margin-top: 2rem;
}

.section-title {
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 1.5rem;
  color: #333;
}

.training-checkbox {
  margin-bottom: 1rem;
}

.training-checkbox label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  color: #666;
}

.training-checkbox input[type="checkbox"] {
  width: 1rem;
  height: 1rem;
  cursor: pointer;
}

.train-button {
  width: 100%;
  padding: 0.75rem;
  font-size: 1rem;
  font-weight: 500;
  color: white;
  background-color: #d32f2f;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.train-button:hover:not(:disabled) {
  background-color: #b71c1c;
}

.train-button:disabled {
  background-color: #ffcdd2;
  cursor: not-allowed;
}

.progress-container {
  width: 100%;
  height: 8px;
  background-color: #f5f5f5;
  border-radius: 4px;
  margin: 1rem 0;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background-color: #4caf50;
  transition: width 0.3s ease;
}

.progress-bar.progress-error {
  background-color: #f44336;
}

.status-text {
  text-align: center;
  color: #666;
  margin-bottom: 1rem;
}

.error-message {
  color: #f44336;
  margin-top: 0.5rem;
  text-align: center;
  font-size: 0.9rem;
}

.training-status {
  margin: 1rem 0;
  padding: 1rem;
  background-color: #f8f9fa;
  border-radius: 4px;
  border: 1px solid #e9ecef;
}
</style>
