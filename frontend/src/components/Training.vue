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
import { defineComponent, computed, watch } from 'vue'
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
    // statusCheckInterval должен быть глобальным для компонента
    let statusCheckInterval: number | null = null

    const trainPredictSave = computed({
      get: () => store.trainPredictSave,
      set: (value: boolean) => store.setTrainPredictSave(value)
    })

    const isTraining = computed(() => {
      return store.trainingStatus && ['initializing', 'running'].includes(store.trainingStatus.status)
    })

    const buttonText = computed(() => {
      if (!isTraining.value) return '🚀 Обучить модель'
      return '⏳ Обучение...'
    })

    const getStatusMessage = computed(() => {
      if (!store.trainingStatus) return ''
      const status = store.trainingStatus.status
      if (status === 'initializing') return 'Инициализация обучения...'
      if (status === 'running') return `Обучение в процессе (${store.trainingStatus.progress ?? 0}%)`
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
      if (!store.sessionId) return
      try {
        const response = await fetch(`http://localhost:8000/training_status/${store.sessionId}`)
        if (!response.ok) {
          throw new Error('Failed to fetch training status')
        }
        const status = await response.json()
        console.log(status)
        store.setTrainingStatus(status)
        // Обновляем прогресс даже если статус initializing
        if (["completed", "failed", "complete"].includes(status.status)) {
          if (statusCheckInterval) {
            clearInterval(statusCheckInterval)
            statusCheckInterval = null
          }
        }
      } catch (error) {
        console.error('Error checking training status:', error)
      }
    }

    const startTraining = async () => {
      try {
        // Полностью сбрасываем trainingStatus, predictionRows и sessionId перед новым обучением
        store.setTrainingStatus(null)
        store.setPredictionRows([])
        store.setSessionId(null)
        if (statusCheckInterval) {
          clearInterval(statusCheckInterval)
          statusCheckInterval = null
        }
        // Сразу выставляем статус initializing и progress 0
        store.setTrainingStatus({ status: 'initializing', progress: 0 })

        const formData = new FormData();
        if (store.selectedFile) {
          formData.append('training_file', store.selectedFile);
        } else {
          console.error('No file selected - please upload a file first');
          alert('Ошибка: Файл не выбран. Пожалуйста, загрузите файл перед обучением модели.');
          // Сбрасываем статус, так как обучение не началось
          store.setTrainingStatus(null);
          if (statusCheckInterval) {
            clearInterval(statusCheckInterval);
            statusCheckInterval = null;
          }
          return;
        }
        // Detect if file was loaded from DB (by extension)
        let downloadTableName = null;
        if (store.selectedFile && store.selectedFile.name.endsWith('.fromdb.json')) {
          // Extract table name from file name: <table>.fromdb.json
          const match = store.selectedFile.name.match(/^(.*)\.fromdb\.json$/);
          if (match) {
            downloadTableName = match[1];
          }
        }
        // Формируем параметры для обучения
        interface TrainingParams {
          [key: string]: any;
          datetime_column: string;
          target_column: string;
          item_id_column: string;
          frequency: string;
          fill_missing_method: string;
          fill_group_columns: string[];
          use_russian_holidays: boolean;
          evaluation_metric: string;
          models_to_train: string | string[] | null;
          autogluon_preset: string;
          predict_mean_only: boolean;
          prediction_length: number;
          training_time_limit: number | null;
          static_feature_columns: string[];
          pycaret_models: string | string[] | null;
        };
        const params: TrainingParams = {
          datetime_column: store.dateColumn,
          target_column: store.targetColumn,
          item_id_column: store.idColumn,
          frequency: store.horizonUnit.split(' ')[0],
          fill_missing_method: store.fillMethod === 'None (оставить как есть)' ? 'None' : store.fillMethod,
          fill_group_columns: store.groupingColumns,
          use_russian_holidays: store.considerRussianHolidays,
          evaluation_metric: store.selectedMetric.split(' ')[0],
          models_to_train: store.selectedModels[0] === '*' && store.selectedModels.length === 1 ? '*' : (store.selectedModels.length === 0 ? null : store.selectedModels),
          autogluon_preset: store.selectedPreset,
          predict_mean_only: store.meanOnly,
          prediction_length: store.predictionHorizon,
          training_time_limit: store.timeLimit,
          static_feature_columns: store.staticFeatures,
          pycaret_models: store.selectedPycaretModels[0] === '*' && store.selectedPycaretModels.length === 1 ? '*' : (store.selectedPycaretModels.length === 0 ? null : store.selectedPycaretModels)
        };
        if (downloadTableName) {
          params.download_table_name = downloadTableName;
        }
        const paramsJson = JSON.stringify(params);
        formData.append('params', paramsJson);

        if (trainPredictSave.value) {
          // Новый сценарий: обучение+прогноз+сохранение
          const fetchOptions: RequestInit = {
            method: 'POST',
            body: formData,
            headers: {
              'Accept': 'application/json',
              ...(store.authToken ? { 'Authorization': `Bearer ${store.authToken}` } : {})
            }
          };
          const response = await fetch('http://localhost:8000/train_prediction_save/', fetchOptions);
          if (!response.ok) {
            const errorText = await response.text();
            let errorData;
            try {
              errorData = JSON.parse(errorText);
            } catch (e) {
              errorData = { detail: errorText };
            }
            const errorMessage = errorData.detail || 'Failed to train and predict';
            console.error('Training+Prediction error:', errorMessage);
            alert(`Ошибка обучения+прогноза: ${errorMessage}`);
            store.setTrainingStatus({ status: 'failed', progress: 0, error: errorMessage });
            return;
          }
          const result = await response.json();
          store.setSessionId(result.session_id)
          store.setTrainingStatus({ status: 'running', progress: 0 })

          // Опрос статуса
          const pollStatus = async () => {
            if (!store.sessionId) return;
            try {
              const statusResp = await fetch(`http://localhost:8000/training_status/${store.sessionId}`);
              if (!statusResp.ok) throw new Error('Failed to fetch training status');
              const status = await statusResp.json();
              store.setTrainingStatus(status);
              if (["completed", "complete", "failed"].includes(status.status)) {
                if (statusCheckInterval) {
                  clearInterval(statusCheckInterval);
                  statusCheckInterval = null;
                }
                if (["completed", "complete"].includes(status.status)) {
                  // Получаем прогноз
                  try {
                    const fileResp = await fetch(`http://localhost:8000/download_prediction/${store.sessionId}`);
                    if (!fileResp.ok) throw new Error('Ошибка скачивания прогноза');
                    const blob = await fileResp.blob();
                    // Парсим первые 10 строк xlsx
                    const arrayBuffer = await blob.arrayBuffer();
                    const XLSX = await import('xlsx');
                    const workbook = XLSX.read(arrayBuffer, { type: 'array' });
                    const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
                    const rows = XLSX.utils.sheet_to_json(firstSheet, { header: 1 });
                    const headers = rows[0];
                    const dataRows = rows.slice(1, 11); // первые 10 строк

                    // Найти индекс и имя колонки с датой (обычно timestamp/date)
                    const dateHeader = headers.find(h => h.toLowerCase().includes('timestamp') || h.toLowerCase().includes('date'));
                    const dateIdx = dateHeader ? headers.indexOf(dateHeader) : -1;

                    const parsedRows = dataRows.map(row => {
                      const obj: Record<string, any> = {};
                      headers.forEach((h: string, idx: number) => {
                        let value = row[idx];
                        // Если это колонка даты и значение — число, преобразуем в строку даты
                        if (idx === dateIdx && typeof value === 'number' && XLSX.SSF) {
                          const dateObj = XLSX.SSF.parse_date_code(value);
                          if (dateObj) {
                            const pad = (n: number) => n.toString().padStart(2, '0');
                            value = `${dateObj.y}-${pad(dateObj.m)}-${pad(dateObj.d)}`;
                            if (dateObj.H !== undefined && dateObj.M !== undefined && dateObj.S !== undefined) {
                              value += ` ${pad(dateObj.H)}:${pad(dateObj.M)}:${pad(Math.floor(dateObj.S))}`;
                            }
                          }
                        }
                        obj[h] = value;
                      });
                      return obj;
                    });
                    store.setPredictionRows(parsedRows);
                    // Автоматическая загрузка файла
                    const url = window.URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = url;
                    link.setAttribute('download', `prediction_${store.sessionId}.xlsx`);
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                  } catch (e) {
                    alert('Ошибка при обработке прогноза: ' + (e instanceof Error ? e.message : e));
                  }
                }
              }
            } catch (error) {
              console.error('Error checking training+prediction status:', error);
            }
          };
          // Запускаем опрос статуса
          statusCheckInterval = setInterval(pollStatus, 2000) as unknown as number;
          // Первый вызов сразу
          pollStatus();
          return;
        }
        // --- Обычная логика (старая) ---
        statusCheckInterval = setInterval(checkTrainingStatus, 2000) as unknown as number
        const fetchOptions: RequestInit = {
          method: 'POST',
          body: formData,
          headers: {
            'Accept': 'application/json',
            ...(store.authToken ? { 'Authorization': `Bearer ${store.authToken}` } : {})
          }
        };
        const response = await fetch('http://localhost:8000/train_timeseries_model/', fetchOptions);
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
          // Устанавливаем статус ошибки
          store.setTrainingStatus({ status: 'failed', progress: 0, error: errorMessage });
          if (statusCheckInterval) {
            clearInterval(statusCheckInterval);
            statusCheckInterval = null;
          }
          throw new Error(errorMessage);
        }
        const result = await response.json();
        console.log('Training started successfully:', result);
        store.setSessionId(result.session_id)
        // Обновляем статус на running после успешного старта
        store.setTrainingStatus({ status: 'running', progress: 0 })
      } catch (error) {
        console.error('Error during training:', error);
        if (error instanceof Error && !error.message.includes('Файл не выбран')) {
          alert('Произошла ошибка при обучении модели. Подробности в консоли.');
          // Устанавливаем статус ошибки, если что-то пошло не так
          store.setTrainingStatus({ 
            status: 'failed', 
            progress: 0, 
            error: error instanceof Error ? error.message : 'Неизвестная ошибка' 
          });
          if (statusCheckInterval) {
            clearInterval(statusCheckInterval);
            statusCheckInterval = null;
          }
        }
      }
    }

    return {
      trainPredictSave,
      canStartTraining,
      startTraining,
      trainingStatus: computed(() => store.trainingStatus),
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
  /* убираем рамку, фон и паддинг */
  max-width: none;
  padding: 0;
  border: none;
  border-radius: 0;
  background-color: transparent;
}

.section-title {
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 1.5rem;
  color: #333;
  text-align: left;
}

.training-checkbox {
  margin-bottom: 20px;
}

.training-status {
  margin-bottom: 20px;
}

.progress-container {
  width: 100%;
  height: 10px;
  background-color: #f3f3f3;
  border-radius: 5px;
  overflow: hidden;
  position: relative;
}

.progress-bar {
  height: 100%;
  background-color: #4caf50;
  transition: width 0.4s ease;
}

.progress-error {
  background-color: #f44336 !important;
}

.status-text {
  margin-top: 5px;
  text-align: center;
}

.error-message {
  color: #f44336;
  margin-top: 10px;
  text-align: center;
}

.train-button {
  width: 100%;
  padding: 10px;
  font-size: 16px;
  color: #fff;
  background-color: #007bff;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  transition: background-color 0.3s ease;
}

.train-button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.train-button:not(:disabled):hover {
  background-color: #0056b3;
}
</style>
