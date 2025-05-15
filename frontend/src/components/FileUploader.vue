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
        <button @click="fileInput && fileInput.click()">
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
        <span v-else>📂 Загрузить данные</span>
      </button>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed } from 'vue'
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

    const chunkSize = computed({
      get: () => store.chunkSize,
      set: (value: number) => store.setChunkSize(value)
    })

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
                  store.setTableData(event.data.data)
                  emit('file-loaded', event.data.data)
                  resolve(null)
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
          store.setTableData(data)
          emit('file-loaded', data)
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
      }
    }

    const handleDrop = (event: DragEvent) => {
      const file = event.dataTransfer?.files[0]
      if (file) {
        selectedFile.value = file
        store.setFile(file) // Сохраняем файл в хранилище
      }
    }

    const handleUpload = async () => {
      if (!selectedFile.value) return
      isLoading.value = true
      try {
        store.setFile(selectedFile.value) // Убедимся, что файл сохранен в хранилище перед загрузкой
        await processFile(selectedFile.value)
      } finally {
        isLoading.value = false
      }
    }

    return {
      fileInput,
      selectedFile,
      isLoading,
      chunkSize,
      handleFileChange,
      handleDrop,
      handleUpload
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

button:hover {
  background-color: #1976D2;
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
</style>