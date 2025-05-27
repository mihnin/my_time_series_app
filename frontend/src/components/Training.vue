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

    <!-- Новая кнопка автосохранения в БД -->
    <div v-if="showAutoSaveButton" style="margin-bottom: 16px; text-align: left;">
      <button 
        class="train-button" 
        style="margin-top:0; width:100%; min-width:unset; display:flex; align-items:center; justify-content:center; gap:8px;"
        :disabled="!canAutoSaveToDb"
        @click="openAutoSaveModal"
      >
        <svg xmlns="http://www.w3.org/2000/svg" height="20" viewBox="0 0 20 20" width="20" style="vertical-align:middle;"><g><ellipse cx="10" cy="5.5" rx="8" ry="3.5" fill="#fff" stroke="#007bff" stroke-width="1.2"/><ellipse cx="10" cy="5.5" rx="8" ry="3.5" fill="#007bff" fill-opacity=".15"/><rect x="2" y="5.5" width="16" height="7" rx="4" fill="#fff" stroke="#007bff" stroke-width="1.2"/><rect x="2" y="5.5" width="16" height="7" rx="4" fill="#007bff" fill-opacity=".10"/><rect x="2" y="12.5" width="16" height="3" rx="1.5" fill="#fff" stroke="#007bff" stroke-width="1.2"/><rect x="2" y="12.5" width="16" height="3" rx="1.5" fill="#007bff" fill-opacity=".10"/></g></svg>
        Автоматическое сохранение в БД
      </button>
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

    <!-- Модальное окно для автосохранения в БД -->
    <Teleport to="body">
      <div v-if="autoSaveModalVisible" class="db-modal-overlay" @click="closeAutoSaveModal">
        <div class="db-modal upload-to-db-modal" id="auto-save-db-modal" @click.stop style="max-width:420px;min-width:320px;min-height:220px;box-sizing:border-box;font-size:0.98rem;">
          <button class="close-btn" @click="closeAutoSaveModal">×</button>
          <h3 style="margin-bottom:1rem">Сохранить прогноз в БД</h3>
          <div style="margin-bottom:1rem; display:flex; gap:1.5rem; align-items:center;">
            <label style="display:flex; align-items:center; gap:6px; font-weight:500;">
              <input type="radio" value="new" v-model="dbSaveMode" />
              Создать новую таблицу
            </label>
            <label style="display:flex; align-items:center; gap:6px; font-weight:500;">
              <input type="radio" value="existing" v-model="dbSaveMode" />
              Загрузить в существующую
            </label>
          </div>
          <!-- Новая таблица -->
          <div v-if="dbSaveMode === 'new'">
            <input v-model="newTableName" class="db-input db-input-full" placeholder="Введите название таблицы" style="margin-bottom:1rem;width:100%;padding:0.75rem;" />
            <div v-if="tableData && tableData.length && Object.keys(tableData[0] || {}).length" style="margin-bottom:1rem;">
              <label style="font-weight:500; color:#333; margin-bottom:0.5rem; display:block;">Выберите первичные ключи (опционально):</label>
              <div style="display:flex; flex-wrap:wrap; gap:8px;">
                <label v-for="col in Object.keys(tableData[0] || {})" :key="col" style="display:flex; align-items:center; gap:4px;">
                  <input type="checkbox" :value="col" v-model="selectedPrimaryKeys" />
                  <span>{{ col }}</span>
                </label>
              </div>
            </div>
          </div>
          <!-- Существующая таблица -->
          <div v-if="dbSaveMode === 'existing'">
            <div v-if="dbTableCountAvailable !== null && dbTableCountTotal !== null" style="margin-bottom:0.5rem;font-size:0.98rem;color:#1976d2;font-weight:500;">
              Доступно {{ dbTableCountAvailable }} таблиц из {{ dbTableCountTotal }}
            </div>
            <select v-model="selectedTable" class="db-input db-input-full" style="margin-bottom:1rem;">
              <option value="" disabled selected>Загрузка списка...</option>
              <option v-for="table in dbTableNames" :key="table" :value="table">{{ table }}</option>
            </select>
          </div>
          <div class="upload-to-db-footer">
            <button class="upload-to-db-btn" :disabled="(dbSaveMode==='new' && !newTableName) || (dbSaveMode==='existing' && !selectedTable) || dbLoading" @click="handleSaveToDb">
              <span v-if="dbLoading" class="spinner-wrap"><span class="spinner"></span></span>
              Сохранить в эту таблицу после обучения
            </button>
            <div v-if="dbError" class="error-message upload-to-db-error-area">{{ dbError }}</div>
          </div>
        </div>
      </div>
    </Teleport>
    <!-- Модальное окно успешного сохранения -->
    <Teleport to="body">
      <div v-if="saveSuccessModalVisible" class="success-modal-overlay">
        <div class="success-modal">
          <div class="success-icon">
            <svg width="80" height="80" viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="40" cy="40" r="40" fill="#4CAF50"/>
              <path d="M24 42L36 54L56 34" stroke="white" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
          <div class="success-text">Изменения сохранены</div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script lang="ts">
import { defineComponent, computed, ref, watch } from 'vue'
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
    let statusCheckInterval: number | null = null

    const trainPredictSave = computed({
      get: () => store.trainPredictSave,
      set: (value: boolean) => store.setTrainPredictSave(value)
    })

    const showAutoSaveButton = computed(() => {
      return store.dbConnected && trainPredictSave.value
    })
    const canAutoSaveToDb = computed(() => {
      return (
        store.targetColumn !== '<нет>' &&
        store.dateColumn !== '<нет>' &&
        store.idColumn !== '<нет>'
      )
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

    // --- Модальное окно автосохранения в БД ---
    const autoSaveModalVisible = ref(false)
    const dbTableNames = ref<string[]>([])
    const dbLoading = ref(false)
    const dbError = ref('')
    const selectedTable = ref<string>('')
    const newTableName = ref<string>('')
    const dbTableCountAvailable = ref<number|null>(null)
    const dbTableCountTotal = ref<number|null>(null)
    const dbSaveMode = ref<'new' | 'existing'>('new')
    const selectedPrimaryKeys = ref<string[]>([])
    const predictionRows = computed(() => store.predictionRows)
    const tableData = computed(() => store.tableData)
    
    // Для авторизации используем store.authToken
    const dbToken = computed(() => store.authToken || '')

    const openAutoSaveModal = async () => {
      autoSaveModalVisible.value = true
      dbLoading.value = true
      dbError.value = ''
      selectedTable.value = ''
      newTableName.value = ''
      dbTableCountAvailable.value = null
      dbTableCountTotal.value = null
      try {
        const resp = await fetch('http://localhost:8000/get-tables', {
          headers: {
            'Authorization': `Bearer ${dbToken.value}`
          }
        })
        if (!resp.ok) throw new Error('Ошибка загрузки таблиц')
        const data = await resp.json()
        dbTableNames.value = data.tables || []
        dbTableCountAvailable.value = data.count_available ?? (data.tables ? data.tables.length : 0)
        dbTableCountTotal.value = data.count_total ?? (data.tables ? data.tables.length : 0)
      } catch (e: any) {
        dbError.value = e.message || 'Ошибка'
        dbTableNames.value = []
        dbTableCountAvailable.value = null
        dbTableCountTotal.value = null
      } finally {
        dbLoading.value = false
      }
    }
    const closeAutoSaveModal = () => {
      autoSaveModalVisible.value = false
    }

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
        // --- добавляем upload_table_name если trainPredictSave и имя таблицы есть ---
        if (trainPredictSave.value && store.uploadDbName) {
          params.upload_table_name = store.uploadDbName;
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

    // --- Создание таблицы в БД по первой строке файла ---
    const createTableFromFile = async () => {
      if (!newTableName.value || !store.selectedFile) return;
      dbLoading.value = true;
      dbError.value = '';
      try {
        const formData = new FormData();
        formData.append('file', store.selectedFile);
        formData.append('table_name', newTableName.value);
        formData.append('primary_keys', JSON.stringify(selectedPrimaryKeys.value));
        // Специальный режим: только создание таблицы по первой строке
        formData.append('create_table_only', 'true');
        const resp = await fetch('http://localhost:8000/create-table-from-file', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${dbToken.value}`
          },
          body: formData
        });
        const data = await resp.json();
        if (!resp.ok || !data.success) {
          dbError.value = data.detail || 'Ошибка создания таблицы';
        } else {
          dbError.value = '';
          // Можно показать уведомление или закрыть модалку
        }
      } catch (e: any) {
        dbError.value = (e as any).message || 'Ошибка';
      } finally {
        dbLoading.value = false;
      }
    }

    const saveSuccessModalVisible = ref(false)

    // --- Сохранение в БД после обучения ---
    const handleSaveToDb = async () => {
      dbLoading.value = true;
      dbError.value = '';
      try {
        let tableName = '';
        if (dbSaveMode.value === 'new') {
          tableName = newTableName.value.trim();
          if (!tableName) {
            dbError.value = 'Введите название новой таблицы.';
            dbLoading.value = false;
            return;
          }
          // 1. Создать таблицу
          const formData = new FormData();
          if (!store.selectedFile) {
            dbError.value = 'Файл не выбран.';
            dbLoading.value = false;
            return;
          }
          formData.append('file', store.selectedFile);
          formData.append('table_name', tableName);
          formData.append('primary_keys', JSON.stringify(selectedPrimaryKeys.value));
          formData.append('create_table_only', 'true');
          const resp = await fetch('http://localhost:8000/create-table-from-file', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${dbToken.value}`
            },
            body: formData
          });
          const data = await resp.json();
          if (!resp.ok || !data.success) {
            dbError.value = data.detail || 'Ошибка создания таблицы';
            dbLoading.value = false;
            return;
          }
        } else {
          tableName = selectedTable.value;
          if (!tableName || !store.selectedFile) {
            dbError.value = 'Не выбрана таблица или не загружен файл';
            dbLoading.value = false;
            return;
          }
          // 2. Проверить структуру
          const formData = new FormData();
          formData.append('file', store.selectedFile);
          formData.append('table_name', tableName);
          const resp = await fetch('http://localhost:8000/check-df-matches-table-schema', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${dbToken.value}`
            },
            body: formData
          });
          const data = await resp.json();
          if (!data.success) {
            dbError.value = data.detail || 'Структура файла не совпадает с таблицей';
            dbLoading.value = false;
            return;
          }
        }
        // Сохраняем название таблицы в store.uploadDbName
        store.setUploadDbName(tableName);
        // Скрываем модалку автосохранения
        closeAutoSaveModal();
        // Показываем модалку успеха
        saveSuccessModalVisible.value = true;
        setTimeout(() => { saveSuccessModalVisible.value = false; }, 1800);
      } catch (e: any) {
        dbError.value = (e as any).message || 'Ошибка';
      } finally {
        dbLoading.value = false;
      }
    }

    // Очищать ошибку при смене radio button
    watch(dbSaveMode, () => {
      dbError.value = ''
    })

    return {
      trainPredictSave,
      canStartTraining,
      startTraining,
      trainingStatus: computed(() => store.trainingStatus),
      isTraining,
      buttonText,
      getStatusMessage,
      showAutoSaveButton,
      canAutoSaveToDb,
      // modal
      autoSaveModalVisible,
      openAutoSaveModal,
      closeAutoSaveModal,
      dbTableNames,
      dbLoading,
      dbError,
      selectedTable,
      newTableName,
      dbSaveMode,
      selectedPrimaryKeys,
      tableData,
      dbTableCountAvailable,
      dbTableCountTotal,
      createTableFromFile,
      saveSuccessModalVisible,
      handleSaveToDb
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
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.train-button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.train-button:not(:disabled):hover {
  background-color: #0056b3;
}

/* Стили для модального окна автосохранения в БД */
.db-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  isolation: isolate;
}
.db-modal {
  background: white;
  padding: 2rem;
  border-radius: 8px;
  max-width: 500px;
  min-width: 340px;
  width: 100%;
  min-height: 220px;
  max-height: 90vh;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.close-btn {
  position: absolute;
  top: 0.5rem;
  right: 0.7rem;
  background: none;
  border: none;
  font-size: 2rem;
  color: #888;
  cursor: pointer;
  z-index: 10;
}
.close-btn:active, .close-btn:focus {
  background: none !important;
  outline: none;
  box-shadow: none;
}
.table-preview-loader {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 120px;
  width: 100%;
}
.table-preview-spinner {
  width: 36px;
  height: 36px;
  border: 4px solid #e3e3e3;
  border-top: 4px solid #2196F3;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
.upload-to-db-btn {
  width: 100%;
  padding: 0.75rem;
  background-color: #1976d2;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  margin-bottom: 0;
  transition: background-color 0.2s;
}
.upload-to-db-btn:hover {
  background-color: #0d47a1 !important;
}
.error-message {
  color: #f44336;
  margin-top: 10px;
  text-align: center;
}

.db-input,
.db-input-full {
  width: 100%;
  padding: 0.75rem;
  font-size: 1rem;
  font-family: inherit;
  border: 1px solid #ccc;
  border-radius: 4px;
  box-sizing: border-box;
}

/* Стили для модального окна успешного сохранения */
.success-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  isolation: isolate;
}
.success-modal {
  background: #fff;
  border-radius: 16px;
  padding: 2.5rem 2.5rem 2rem 2.5rem;
  min-width: 340px;
  max-width: 90vw;
  box-shadow: 0 8px 32px rgba(76, 175, 80, 0.18);
  display: flex;
  flex-direction: column;
  align-items: center;
  animation: pop-in 0.18s cubic-bezier(.4,2,.6,1) 1;
}
.success-icon {
  margin-bottom: 1.2rem;
}
.success-text {
  color: #388e3c;
  font-size: 1.25rem;
  font-weight: 600;
  text-align: center;
}
@keyframes pop-in {
  0% { transform: scale(0.7); opacity: 0; }
  100% { transform: scale(1); opacity: 1; }
}
</style>
