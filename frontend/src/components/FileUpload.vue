<template>
  <div class="file-upload">
    <h3 class="section-title">Настройка обучения</h3>
    
    <details class="settings-panel" open>
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
    </details>

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
        <button @click="$refs.fileInput.click()">
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
        <span v-if="isLoading">Загрузка...</span>
        <span v-else>📂 Загрузить данные</span>
      </button>

      <!-- Колонки датасета -->
      <div class="dataset-columns" v-if="store.tableData.length">
        <h4 class="subsection-title">Колонки датасета</h4>
        
        <!-- Колонка с датой -->
        <div class="column-select">
          <label>Колонка с датой</label>
          <select v-model="selectedDateColumn">
            <option value="<нет>">&lt;нет&gt;</option>
            <option v-for="column in availableColumns" :key="column" :value="column">
              {{ column }}
            </option>
          </select>
        </div>

        <!-- Колонка target -->
        <div class="column-select">
          <label>Колонка target</label>
          <select v-model="selectedTargetColumn">
            <option value="<нет>">&lt;нет&gt;</option>
            <option v-for="column in availableColumns" :key="column" :value="column">
              {{ column }}
            </option>
          </select>
        </div>

        <!-- Колонка ID -->
        <div class="column-select">
          <label>Колонка ID (категориальный)</label>
          <select v-model="selectedIdColumn">
            <option value="<нет>">&lt;нет&gt;</option>
            <option v-for="column in availableColumns" :key="column" :value="column">
              {{ column }}
            </option>
          </select>
        </div>

        <!-- Статические признаки -->
        <div class="static-features">
          <h4>Статические признаки (до 3)</h4>
          <div class="selected-features">
            <div 
              v-for="feature in staticFeatures" 
              :key="feature" 
              class="feature-tag"
            >
              {{ feature }}
              <button @click="removeStaticFeature(feature)" class="remove-feature">×</button>
            </div>
          </div>
          <select 
            v-model="selectedFeature"
            :disabled="!store.tableData.length || staticFeatures.length >= 3"
            @change="addStaticFeature"
          >
            <option value="">Выберите признак</option>
            <option 
              v-for="column in availableStaticFeatures" 
              :key="column" 
              :value="column"
            >
              {{ column }}
            </option>
          </select>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, computed, ref } from 'vue'
import { useMainStore } from '../stores/mainStore'
import Papa from 'papaparse'
import * as XLSX from 'xlsx'

export default defineComponent({
  name: 'FileUpload',
  setup() {
    const store = useMainStore()
    const fileInput = ref<HTMLInputElement | null>(null)
    const selectedFile = ref<File | null>(null)
    const isLoading = ref(false)
    const selectedFeature = ref('')

    const chunkSize = computed({
      get: () => store.chunkSize,
      set: (value: number) => store.setChunkSize(value)
    })

    const selectedDateColumn = computed({
      get: () => store.dateColumn,
      set: (value: string) => store.setDateColumn(value)
    })

    const selectedTargetColumn = computed({
      get: () => store.targetColumn,
      set: (value: string) => store.setTargetColumn(value)
    })

    const selectedIdColumn = computed({
      get: () => store.idColumn,
      set: (value: string) => store.setIdColumn(value)
    })

    const staticFeatures = computed({
      get: () => store.staticFeatures,
      set: (value: string[]) => store.setStaticFeatures(value)
    })

    const processFile = async (file: File) => {
      try {
        const data = await readFileData(file)
        store.setTableData(data)
      } catch (error) {
        console.error('Error processing file:', error)
      }
    }

    const readFileData = (file: File): Promise<any[]> => {
      return new Promise((resolve, reject) => {
        const reader = new FileReader()
        
        reader.onload = (e) => {
          try {
            const data = e.target?.result
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
      }
    }

    const handleDrop = (event: DragEvent) => {
      const file = event.dataTransfer?.files[0]
      if (file) {
        processFile(file)
      }
    }

    const handleUpload = async () => {
      if (!selectedFile.value) return
      isLoading.value = true
      try {
        await processFile(selectedFile.value)
        // Сбрасываем выбранные колонки при успешной загрузке нового файла
        store.setDateColumn('<нет>')
        store.setTargetColumn('<нет>')
        store.setIdColumn('<нет>')
        store.setStaticFeatures([])
      } finally {
        isLoading.value = false
      }
    }

    const availableColumns = computed(() => {
      if (!store.tableData.length) return []
      return Object.keys(store.tableData[0])
    })

    const availableStaticFeatures = computed(() => {
      if (!store.tableData.length) return []
      return availableColumns.value.filter(column => 
        column !== selectedDateColumn.value &&
        column !== selectedTargetColumn.value &&
        column !== selectedIdColumn.value &&
        column !== '<нет>' &&
        !staticFeatures.value.includes(column)
      )
    })

    const addStaticFeature = () => {
      if (selectedFeature.value && staticFeatures.value.length < 3) {
        staticFeatures.value.push(selectedFeature.value)
        selectedFeature.value = ''
      }
    }

    const removeStaticFeature = (feature: string) => {
      staticFeatures.value = staticFeatures.value.filter(f => f !== feature)
    }

    const handleFileUpload = async (event: Event) => {
      const file = (event.target as HTMLInputElement).files?.[0]
      if (!file) return

      store.setFile(file)
      store.isLoading = true
      store.error = null

      try {
        let data: any[] = []

        if (file.name.endsWith('.csv')) {
          // Обработка CSV
          const text = await file.text()
          const result = Papa.parse(text, { header: true })
          data = result.data
        } else {
          // Обработка Excel
          const buffer = await file.arrayBuffer()
          const workbook = XLSX.read(buffer)
          const firstSheet = workbook.Sheets[workbook.SheetNames[0]]
          data = XLSX.utils.sheet_to_json(firstSheet)
        }

        store.setTableData(data)
      } catch (error) {
        store.error = `Ошибка при загрузке файла: ${error.message}`
      } finally {
        store.isLoading = false
      }
    }

    return {
      store,
      chunkSize,
      fileInput,
      selectedFile,
      isLoading,
      selectedDateColumn,
      selectedTargetColumn,
      selectedIdColumn,
      staticFeatures,
      selectedFeature,
      availableColumns,
      availableStaticFeatures,
      addStaticFeature,
      removeStaticFeature,
      handleFileChange,
      handleDrop,
      handleUpload,
      handleFileUpload
    }
  }
})
</script>

<style scoped>
.file-upload {
  margin-top: 1rem;
}

.section-title {
  font-size: 1.1rem;
  color: #333;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid #2196F3;
}

.subsection-title {
  font-size: 1rem;
  color: #666;
  margin: 1rem 0 0.5rem;
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

.settings-summary:hover {
  background-color: #f8f9fa;
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

.number-input:focus {
  outline: none;
  border-color: #2196F3;
  box-shadow: 0 0 0 2px rgba(33, 150, 243, 0.2);
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

.file-label {
  display: block;
  margin-bottom: 1rem;
  color: #666;
}

.file-input {
  margin-top: 0.5rem;
  width: 100%;
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

.error-message {
  margin-top: 0.5rem;
  padding: 0.5rem;
  background-color: #ffebee;
  border-radius: 4px;
  color: #c62828;
  font-size: 0.9rem;
}

p {
  margin: 0;
  color: #666;
}

.dataset-columns {
  margin-top: 2rem;
}

.column-select {
  margin-bottom: 1rem;
}

.column-select label {
  display: block;
  margin-bottom: 0.5rem;
  color: #666;
}

.column-select select,
.static-features select {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: white;
  font-size: 1rem;
}

.static-features {
  margin-top: 2rem;
}

.selected-features {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.feature-tag {
  display: inline-flex;
  align-items: center;
  background-color: #e3f2fd;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.9rem;
  color: #1976d2;
}

.remove-feature {
  background: none;
  border: none;
  color: #666;
  margin-left: 0.5rem;
  cursor: pointer;
  padding: 0 0.25rem;
}

.remove-feature:hover {
  color: #d32f2f;
}

select:disabled {
  background-color: #f5f5f5;
  cursor: not-allowed;
}

.loading {
  margin-top: 0.5rem;
  color: #666;
}

.error {
  margin-top: 0.5rem;
  color: #f44336;
}
</style>