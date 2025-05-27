<template>
  <div class="file-uploader">
    <h3 class="section-title">Настройка обучения</h3>
    
    <!-- <details class="settings-panel">
      <summary class="settings-summary">Настройки для больших файлов</summary>
      <div class="settings-content">
        <label class="input-label">
          Размер чанка (строк):
          <input 
            type="number" 
            v-model="chunkSize"
            min="1000"
            max="1000000"
            step="10000"
            class="number-input"
          />
        </label>
      </div>
    </details> -->

    <div class="upload-section">
      <h4 class="subsection-title">Загрузка данных</h4>
      <div class="upload-zone" @dragover.prevent @drop.prevent="handleDrop">
        <input 
          type="file" 
          ref="fileInput"
          accept=".csv,.xlsx,.xls"
          @change="handleFileChange"
          style="display: none"
        >
        <button @click="fileInput && fileInput.click()" class="choose-file-btn">
          📂 Выбрать файл
        </button>
        <p>или перетащите файл сюда</p>
      </div>
      <div v-if="selectedFile" class="file-info">
        Выбран файл: {{ selectedFile.name }}
      </div>
      <button 
        @click="handleUpload" 
        class="upload-button" 
        :disabled="!selectedFile"
      >
        <span v-if="isLoading" class="spinner-wrap">
          <span class="spinner"></span>Загрузка...
        </span>
        <span v-else>📂 Загрузить данные из файла</span>
      </button>
      <button
        v-if="dbConnected"
        class="db-load-btn"
        @click="openDbModal"
        style="margin-top: 0.5rem; background: #388e3c;"
      >
        🗄️ Загрузить из БД
      </button>
      <button
        v-if="dbConnected && fileLoaded"
        class="upload-to-db-btn"
        @click="openUploadToDbModal"
        :disabled="isLoading"
        style="margin-top: 0.5rem;"
      >
        ⬆️ Загрузить файл в БД
      </button>
    </div>

    <!-- Модальное окно выбора таблицы из БД -->
    <Teleport to="body">
      <div v-if="dbModalVisible" class="db-modal-overlay" @click="closeDbModal">
        <div class="db-modal" @click.stop>
          <button class="close-btn" @click="closeDbModal">×</button>
          <h3 style="margin-bottom:1rem">Выберите таблицу из БД</h3>
          <div class="db-modal-table-area">
            <div v-if="dbTablesLoading" style="color:#888;">Загрузка таблиц...</div>
            <div v-else-if="dbTables.length === 0" style="color:#f44336;">Нет доступных таблиц</div>
            <div v-else class="db-modal-content">
              <div v-if="dbTableCountAvailable !== null && dbTableCountTotal !== null" style="margin-bottom:0.5rem;font-size:0.98rem;color:#1976d2;font-weight:500;">
                Доступно {{ dbTableCountAvailable }} таблиц из {{ dbTableCountTotal }}
              </div>
              <select v-model="selectedDbTable" class="db-input db-input-full" style="margin-bottom:1rem;">
                <option value="" disabled selected>Выберите таблицу...</option>
                <option v-for="table in dbTables" :key="table" :value="table">{{ table }}</option>
              </select>
              <div class="table-preview-fixed">
                <div v-if="tablePreviewLoading" class="table-preview-loader">
                  <span class="table-preview-spinner"></span>
                </div>
                <div v-else-if="tablePreviewError" class="error-message" style="display:flex;align-items:center;justify-content:center;height:100%;">{{ tablePreviewError }}</div>
                <div v-else-if="tablePreview && tablePreview.length" class="table-preview-scroll">
                  <table style="width:100%; border-collapse:collapse; font-size:0.95rem;">
                    <thead>
                      <tr>
                        <th v-for="key in Object.keys(tablePreview[0])" :key="key" style="border-bottom:1px solid #e0e0e0; padding:0.3rem 0.5rem; background:#f5f5f5;">{{ key }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(row, idx) in tablePreview" :key="idx">
                        <td v-for="key in Object.keys(tablePreview[0])" :key="key" style="padding:0.3rem 0.5rem; border-bottom:1px solid #f0f0f0;">{{ row[key] }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div v-else style="display:flex;align-items:center;justify-content:center;height:100%;color:#888;">Выберите таблицу для предпросмотра</div>
              </div>
            </div>
          </div>
          <div class="db-modal-footer">
            <button class="connect-btn" style="width:100%;" :disabled="!selectedDbTable || isLoadingFromDb" @click="loadTableFromDb">
              <span v-if="isLoadingFromDb" class="spinner-wrap"><span class="spinner"></span>Загрузка...</span>
              <span v-else>Загрузить таблицу</span>
            </button>
            <div v-if="dbError" class="error-message">{{ dbError }}</div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Модальное окно для загрузки файла в БД -->
    <Teleport to="body">
      <div v-if="uploadToDbModalVisible" class="db-modal-overlay" @click="closeUploadToDbModal">
        <div class="db-modal upload-to-db-modal" id="upload-to-db-modal" @click.stop>
          <button class="close-btn" @click="closeUploadToDbModal">×</button>
          <h3 style="margin-bottom:1rem">Загрузка файла в БД</h3>
          <!-- Выбор режима: новая таблица или существующая -->
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
            <input v-model="uploadTableName" class="db-input db-input-full" placeholder="Введите название таблицы" style="margin-bottom:1rem;" />
            <div v-if="tableData && tableData.length" style="margin-bottom:1rem;">
              <label style="font-weight:500; color:#333; margin-bottom:0.5rem; display:block;">Выберите первичные ключи (опционально):</label>
              <div style="display:flex; flex-wrap:wrap; gap:8px;">
                <label v-for="col in Object.keys(tableData[0])" :key="col" style="display:flex; align-items:center; gap:4px;">
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
            <select v-model="uploadTableName" class="db-input db-input-full" style="margin-bottom:1rem;">
              <option value="" disabled selected>Загрузка списка...</option>
              <option v-for="table in uploadDbTables" :key="table" :value="table">{{ table }}</option>
            </select>
          </div>
          <div class="upload-to-db-footer">
            <button class="upload-to-db-btn" :disabled="!uploadTableName || uploadToDbLoading" @click="uploadFileToDb">
              <span v-if="uploadToDbLoading" class="spinner-wrap"><span class="spinner"></span>Загрузка...</span>
              <span v-else>Загрузить в БД</span>
            </button>
            <div v-if="uploadToDbError" class="error-message upload-to-db-error-area">{{ uploadToDbError }}</div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Модальное окно успешной загрузки файла в БД -->
    <Teleport to="body">
      <div v-if="uploadSuccessModalVisible" class="success-modal-overlay">
        <div class="success-modal">
          <div class="success-icon">
            <svg width="80" height="80" viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="40" cy="40" r="40" fill="#4CAF50"/>
              <path d="M24 42L36 54L56 34" stroke="white" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
          <div class="success-text">Файл успешно загружен в БД</div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, watch } from 'vue'
import { useMainStore } from '../stores/mainStore'
import * as XLSX from 'xlsx'

export default defineComponent({
  name: 'FileUploader',
  emits: ['file-loaded'],

  setup(props, { emit }) {
    const store = useMainStore()
    const fileInput = ref<HTMLInputElement | null>(null)
    const selectedFile = ref<File | null>(null)
    const isLoading = ref(false)
    const fileLoaded = ref(false)
    // --- DB upload modal state ---
    const dbModalVisible = ref(false)
    const dbTablesLoading = ref(false) // <--- add loading state
    const selectedDbTable = ref('')
    const isLoadingFromDb = ref(false)
    const dbError = ref('')
    const tablePreview = ref<any[] | null>(null)
    const tablePreviewLoading = ref(false)
    const tablePreviewError = ref('')
    // --- Upload to DB modal state ---
    const uploadToDbModalVisible = ref(false)
    const uploadTableName = ref('')
    const uploadToDbLoading = ref(false)
    const uploadToDbError = ref('')
    const uploadSuccessModalVisible = ref(false)
    const selectedPrimaryKeys = ref<string[]>([]) // <--- новое состояние для выбранных первичных ключей
    const dbSaveMode = ref<'new' | 'existing'>('new') // <--- состояние для режима сохранения в БД
    const tableData = computed(() => store.tableData)
    const uploadDbTables = ref<string[]>([])
    const uploadDbTablesLoading = ref(false)
    const dbTableCountAvailable = ref<number | null>(null)
    const dbTableCountTotal = ref<number | null>(null)

    // Для шаблона
    const dbConnected = computed(() => store.dbConnected)
    const dbTables = computed(() => store.dbTables)

    const chunkSize = computed({
      get: () => store.chunkSize,
      set: (value: number) => store.setChunkSize(value)
    })

    // Преобразование Excel serial date в строку (YYYY-MM-DD или с временем)
    function convertExcelDates(
      data: any[],
      xlsxModule?: typeof import('xlsx')
    ): any[] {
      if (!Array.isArray(data) || data.length === 0) return data;
      // Найти все колонки, которые могут быть датой
      const dateLikeColumns = Object.keys(data[0]).filter(
        key => key.toLowerCase().includes('date') || key.toLowerCase().includes('timestamp')
      );
      if (dateLikeColumns.length === 0) return data;
      // Попробовать преобразовать только если значение - число и похоже на Excel serial
      return data.map(row => {
        const newRow = { ...row };
        dateLikeColumns.forEach(col => {
          const value = row[col];
          if (
            typeof value === 'number' &&
            value > 20000 && value < 90000 &&
            xlsxModule &&
            (xlsxModule as any).SSF &&
            typeof (xlsxModule as any).SSF.parse_date_code === 'function'
          ) {
            const dateObj = (xlsxModule as any).SSF.parse_date_code(value);
            if (dateObj) {
              const pad = (n: number) => n.toString().padStart(2, '0');
              // Если есть время и оно не полуночь, добавлять только часы (без минут и секунд)
              let str = `${dateObj.y}-${pad(dateObj.m)}-${pad(dateObj.d)}`;
              if (
                dateObj.H !== undefined &&
                (dateObj.H !== 0 || dateObj.M !== 0 || dateObj.S !== 0)
              ) {
                str += ` ${pad(dateObj.H)}`;
              }
              newRow[col] = str;
            }
          }
        });
        return newRow;
      });
    }

    const processFile = async (file: File) => {
      try {
        store.setFile(file)
        // Используем Web Worker для Excel
        if (file.name.endsWith('.xlsx') || file.name.endsWith('.xls')) {
          await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => {
              // Вставляем код воркера как строку
              const workerCode = `importScripts('https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js');\nself.onmessage = ${String(function(e) { const { fileData, fileName, maxRows } = e.data; try { const workbook = XLSX.read(fileData, { type: 'binary' }); const firstSheet = workbook.Sheets[workbook.SheetNames[0]]; let jsonData = XLSX.utils.sheet_to_json(firstSheet, { header: 1 }); if (maxRows && jsonData.length > maxRows) { jsonData = jsonData.slice(0, maxRows); } const [header, ...rows] = jsonData; const result = rows.map(row => { const obj = {}; header.forEach((key, idx) => { obj[key] = row[idx]; }); return obj; }); self.postMessage({ success: true, data: result }); } catch (error) { self.postMessage({ success: false, error: error.message }); } })}`;
              const blob = new Blob([workerCode], { type: 'application/javascript' });
              const worker = new Worker(URL.createObjectURL(blob));
              worker.onmessage = function(event) {
                if (event.data.success) {
                  // Преобразуем даты после получения данных
                  import('xlsx').then(XLSX => {
                    const converted = convertExcelDates(event.data.data, XLSX);
                    store.setTableData(converted)
                    emit('file-loaded', converted)
                    resolve(null)
                  });
                } else {
                  reject(event.data.error)
                }
                worker.terminate();
              };
              worker.postMessage({
                fileData: e.target?.result ?? '',
                fileName: file.name,
                maxRows: 1000000 // или chunkSize.value, если нужно ограничение
              });
            };
            reader.onerror = (err) => reject(err);
            reader.readAsBinaryString(file);
          });
        } else {
          const data = await readFileData(file)
          // Преобразуем даты после получения данных
          const XLSX = await import('xlsx');
          const converted = convertExcelDates(data, XLSX);
          store.setTableData(converted)
          emit('file-loaded', converted)
        }
      } catch (error) {
        console.error('Error processing file:', error)
      }
    }

    const readFileData = (file: File): Promise<any[]> => {
      return new Promise((resolve, reject) => {
        const reader = new FileReader()
        
        reader.onload = (e) => {
          try {
            const data = e.target?.result ?? ''
            const workbook = XLSX.read(data, { type: 'binary' })
            const firstSheet = workbook.Sheets[workbook.SheetNames[0]]
            const jsonData = XLSX.utils.sheet_to_json(firstSheet)
            resolve(jsonData)
          } catch (error) {
            reject(error)
          }
        }
        
        reader.onerror = (error) => reject(error)
        reader.readAsBinaryString(file)
      })
    }

    const handleFileChange = (event: Event) => {
      const target = event.target as HTMLInputElement
      const file = target.files?.[0]
      if (file) {
        selectedFile.value = file
        store.setFile(file) // Сохраняем файл в хранилище
        fileLoaded.value = false // сброс при выборе нового файла
      }
    }

    const handleDrop = (event: DragEvent) => {
      const file = event.dataTransfer?.files[0]
      if (file) {
        selectedFile.value = file
        store.setFile(file) // Сохраняем файл в хранилище
        fileLoaded.value = false // сброс при выборе нового файла
      }
    }

    const handleUpload = async () => {
      if (!selectedFile.value) return
      isLoading.value = true
      try {
        store.setFile(selectedFile.value) // Убедимся, что файл сохранен в хранилище перед загрузкой
        await processFile(selectedFile.value)
        fileLoaded.value = true // только после успешной загрузки
      } finally {
        isLoading.value = false
      }
    }

    const openDbModal = async () => {
      dbModalVisible.value = true
      dbError.value = ''
      selectedDbTable.value = '' // По умолчанию ничего не выбрано
      // Загружаем таблицы при открытии модального окна
      if (store.dbConnected && store.authToken) {
        dbTablesLoading.value = true
        try {
          const response = await fetch('http://localhost:8000/get-tables', {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${store.authToken}`
            },
          });
          const result = await response.json();
          if (result.success) {
            store.setDbTables(result.tables);
            dbTableCountAvailable.value = result.count_available ?? result.tables.length;
            dbTableCountTotal.value = result.count_total ?? result.tables.length;
            dbError.value = '';
          } else {
            dbError.value = result.detail || 'Не удалось загрузить таблицы из БД.';
            store.setDbTables([]);
            dbTableCountAvailable.value = null;
            dbTableCountTotal.value = null;
          }
        } catch (e: any) {
          dbError.value = 'Ошибка при загрузке таблиц: ' + (e && typeof e === 'object' && 'message' in e ? (e as any).message : String(e));
          store.setDbTables([]);
          dbTableCountAvailable.value = null;
          dbTableCountTotal.value = null;
        } finally {
          dbTablesLoading.value = false
        }
      }
    }
    function closeDbModal() {
      dbModalVisible.value = false
      dbError.value = ''
    }

    async function loadTableFromDb() {
      if (!selectedDbTable.value) return
      dbError.value = ''
      isLoadingFromDb.value = true
      try {
        const response = await fetch('http://localhost:8000/download-table-from-db', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${store.authToken}`
          },
          body: JSON.stringify({ table: selectedDbTable.value })
        })
        if (!response.ok) {
          const err = await response.json().catch(() => ({}))
          dbError.value = err.detail || 'Ошибка загрузки файла из БД.'
          return
        }
        // Получаем blob Excel-файла
        const blob = await response.blob()
        const file = new File([blob], `${selectedDbTable.value}.xlsx`, { type: blob.type })
        selectedFile.value = file
        store.setFile(file)
        // Обрабатываем файл как обычную загрузку (Excel)
        await processFile(file)
        fileLoaded.value = true
        emit('file-loaded', store.tableData)
        closeDbModal()
      } catch (error: any) {
        dbError.value = 'Ошибка загрузки данных из БД: ' + (error?.message || error)
      } finally {
        isLoadingFromDb.value = false
      }
    }

    async function fetchTablePreview(tableName: string) {
      if (!tableName) {
        tablePreview.value = null
        return
      }
      tablePreviewLoading.value = true
      tablePreviewError.value = ''
      try {
        const response = await fetch('http://localhost:8000/get-table-preview', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${store.authToken}`
          },
          body: JSON.stringify({ table: tableName })
        })
        const result = await response.json()
        if (result.success && Array.isArray(result.data)) {
          tablePreview.value = result.data
        } else {
          tablePreview.value = null
          tablePreviewError.value = result.detail || 'Не удалось получить предпросмотр.'
        }
      } catch (e: any) {
        tablePreview.value = null
        tablePreviewError.value = 'Ошибка предпросмотра: ' + (e?.message || e)
      } finally {
        tablePreviewLoading.value = false
      }
    }

    // Следим за изменением выбранной таблицы
    watch(selectedDbTable, (val) => {
      if (val) fetchTablePreview(val)
      else tablePreview.value = null
    })

    // Добавляем обработчик для загрузки файла в БД
    async function uploadFileToDb() {
      if (!selectedFile.value || !uploadTableName.value) return
      uploadToDbLoading.value = true
      uploadToDbError.value = ''
      try {
        const formData = new FormData()
        formData.append('file', selectedFile.value)
        formData.append('table_name', uploadTableName.value)
        formData.append('primary_keys', JSON.stringify(selectedPrimaryKeys.value))
        formData.append('dbSaveMode', dbSaveMode.value) // Передаем режим new/existing
        const response = await fetch('http://localhost:8000/upload-excel-to-db', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${store.authToken}`
          },
          body: formData
        })
        const result = await response.json()
        if (result.success) {
          closeUploadToDbModal()
          uploadSuccessModalVisible.value = true
          setTimeout(() => { uploadSuccessModalVisible.value = false }, 1800)
        } else {
          uploadToDbError.value = result.detail || 'Ошибка при загрузке файла в БД.'
        }
      } catch (e: any) {
        uploadToDbError.value = 'Ошибка: ' + (e?.message || e)
      } finally {
        uploadToDbLoading.value = false
      }
    }

    function openUploadToDbModal() {
      uploadToDbModalVisible.value = true
      uploadTableName.value = ''
      uploadToDbError.value = ''
      selectedPrimaryKeys.value = [] // Сбрасываем выбранные первичные ключи при открытии модального окна
      dbSaveMode.value = 'new' // По умолчанию новая таблица
      // Загруем список таблиц для модалки загрузки в БД
      if (store.dbConnected && store.authToken) {
        uploadDbTablesLoading.value = true
        fetch('http://localhost:8000/get-tables', {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${store.authToken}`
          },
        })
          .then(res => res.json())
          .then(result => {
            if (result.success) {
              uploadDbTables.value = result.tables
              dbTableCountAvailable.value = result.count_available ?? result.tables.length
              dbTableCountTotal.value = result.count_total ?? result.tables.length
            } else {
              uploadDbTables.value = []
              dbTableCountAvailable.value = null
              dbTableCountTotal.value = null
            }
          })
          .catch(() => {
            uploadDbTables.value = []
            dbTableCountAvailable.value = null
            dbTableCountTotal.value = null
          })
          .finally(() => { uploadDbTablesLoading.value = false })
      } else {
        uploadDbTables.value = []
        dbTableCountAvailable.value = null
        dbTableCountTotal.value = null
      }
    }
    function closeUploadToDbModal() {
      uploadToDbModalVisible.value = false
      uploadTableName.value = ''
      uploadToDbError.value = ''
      selectedPrimaryKeys.value = [] // Сбрасываем выбранные первичные ключи при закрытии модального окна
    }

    return {
      fileInput,
      selectedFile,
      isLoading,
      chunkSize,
      handleDrop,
      handleFileChange,
      handleUpload,
      dbModalVisible,
      openDbModal,
      closeDbModal,
      selectedDbTable,
      isLoadingFromDb,
      dbError,
      loadTableFromDb,
      dbConnected,
      dbTables,
      dbTablesLoading, // <--- export
      tablePreview,
      tablePreviewLoading,
      tablePreviewError,
      uploadToDbModalVisible,
      uploadTableName,
      uploadToDbLoading,
      uploadToDbError,
      openUploadToDbModal,
      closeUploadToDbModal,
      uploadFileToDb,
      fileLoaded,
      uploadSuccessModalVisible,
      selectedPrimaryKeys,
      dbSaveMode,
      tableData,
      uploadDbTables,
      uploadDbTablesLoading,
      dbTableCountAvailable,
      dbTableCountTotal,
    }
  }
})
</script>

<style scoped>
.file-uploader {
  margin-top: 1rem;
}

.section-title {
  font-size: 1.1rem;
  color: #333;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid #2196F3;
}

.settings-panel {
  margin-bottom: 1rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: white;
}

.settings-summary {
  padding: 0.75rem;
  cursor: pointer;
  font-weight: 500;
  color: #333;
}

.settings-content {
  padding: 1rem;
  border-top: 1px solid #ddd;
}

.input-label {
  display: block;
  color: #666;
  margin-bottom: 0.5rem;
}

.number-input {
  width: 100%;
  padding: 0.5rem;
  margin-top: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.upload-zone {
  border: 2px dashed #ccc;
  border-radius: 4px;
  padding: 20px;
  text-align: center;
  background-color: #fafafa;
  cursor: pointer;
  transition: all 0.3s ease;
}

.upload-zone:hover {
  border-color: #2196F3;
  background-color: #f0f7ff;
}

.file-info {
  margin: 0.5rem 0;
  padding: 0.5rem;
  background-color: #e3f2fd;
  border-radius: 4px;
  color: #1976d2;
  font-size: 0.9rem;
}

.upload-button {
  width: 100%;
  padding: 0.75rem;
  background-color: #2196F3;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  transition: background-color 0.2s;
}

.upload-button:hover:not(:disabled) {
  background-color: #1976d2;
}

.upload-button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

button {
  padding: 10px 20px;
  background-color: #2196F3;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  margin-bottom: 10px;
  transition: background-color 0.2s;
}

.choose-file-btn {
  padding: 10px 20px;
  background-color: #2196F3;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  margin-bottom: 10px;
  transition: background-color 0.2s;
}
.choose-file-btn:hover {
  background-color: #1976D2;
}

button:hover {
  /* убираем глобальный hover-стиль */
  background-color: unset;
}

.subsection-title {
  font-size: 1rem;
  color: #666;
  margin: 1rem 0 0.5rem;
}

.spinner-wrap {
  display: inline-flex;
  align-items: center;
  vertical-align: middle;
}

.spinner {
  display: inline-block;
  width: 20px;
  height: 20px;
  border: 3px solid #f3f3f3;
  border-top: 3px solid #2196F3;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-right: 8px;
  vertical-align: middle;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

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
  max-width: 700px;
  min-width: 500px;
  width: 100%;
  min-height: 600px;
  max-height: 100vh;
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
  /* убираем любые эффекты фона */
}
.close-btn:active, .close-btn:focus {
  background: none !important;
  outline: none;
  box-shadow: none;
}

.db-input {
  width: 100%;
  padding: 0.75rem;
  margin-top: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.connect-btn {
  width: 100%;
  padding: 0.75rem;
  background-color: #2196F3;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  transition: background-color 0.2s;
}

.connect-btn:hover {
  background-color: #1976d2;
}

.error-message {
  margin-top: 1rem;
  color: #f44336;
  font-size: 0.9rem;
}

.db-load-btn {
  width: 100%;
  padding: 0.75rem;
  background-color: #388e3c;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  margin-bottom: 10px;
  transition: background-color 0.2s;
}
.db-load-btn:hover {
  background-color: #256b27 !important;
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
  margin-bottom: 10px;
  transition: background-color 0.2s;
}
.upload-to-db-btn:hover {
  background-color: #0d47a1 !important;
}

/* Стили для анимации загрузки */
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

/* Новые стили для модального окна */
.db-modal-content {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.table-preview-fixed {
  min-height: 420px;
  max-height: 420px;
  height: 420px;
  width: 100%;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  position: relative;
}
.table-preview-scroll {
  flex: 1 1 auto;
  overflow-y: auto;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background: #fafbfc;
}

.db-modal-footer {
  flex-shrink: 0;
  margin-top: auto;
  padding-top: 1rem;
  background: white;
  position: sticky;
  bottom: 0;
  left: 0;
  width: 100%;
  z-index: 2;
}

.db-modal-table-area {
  min-height: 110px;
  max-height: 110px;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  margin-bottom: 1rem;
}

/* Стили для модального окна успешной загрузки */
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

#upload-to-db-modal {
  min-width: 320px;
  max-width: 420px;
  min-height: 220px;
  max-height: 90vh;
  padding: 1.2rem 1.2rem 1rem 1.2rem;
  box-sizing: border-box;
  font-size: 0.98rem;
  display: flex;
  flex-direction: column;
}
.upload-to-db-footer {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  min-height: 48px;
}
.upload-to-db-btn {
  margin-bottom: 0;
}
.upload-to-db-error-area {
  min-height: 1.5em;
  margin-top: 0.7rem;
  font-size: 0.95rem;
  color: #f44336;
  text-align: center;
  word-break: break-word;
}
</style>