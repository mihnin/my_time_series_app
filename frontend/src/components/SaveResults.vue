<template>
  <div class="save-results" v-if="isVisible">
    <h3 class="section-title">Сохранение результатов прогноза</h3>
    
    <div class="save-buttons">
      <button 
        @click="saveToCsv"
        class="save-button"
        :disabled="!canSaveButton"
      >
        💾 Сохранить результаты в CSV
      </button>

      <button 
        @click="saveToExcel"
        class="save-button"
        :disabled="!canSaveButton"
      >
        💾 Сохранить результаты в Excel
      </button>
      <button
        v-if="dbConnected"
        @click="openSaveToDbModal"
        class="save-button"
        :disabled="!canSaveButton"
      >
        🗄️ Сохранить в БД
      </button>
    </div>

    <!-- Модальное окно сохранения в БД -->
    <Teleport to="body">
      <div v-if="saveToDbModalVisible" class="db-modal-overlay" @click="closeSaveToDbModal">
        <div class="db-modal upload-to-db-modal" @click.stop style="max-width: 420px;">
          <button class="close-btn" @click="closeSaveToDbModal">×</button>
          <h3 class="section-title" style="margin-bottom:1.5rem; border-bottom: none; font-size: 1.3rem;">Сохранить результаты в БД</h3>
          <div style="margin-bottom:1rem; display:flex; gap:1.5rem; align-items:center;">
            <label style="display:flex; align-items:center; gap:6px; font-weight:500;">
              <input type="radio" value="new" v-model="dbSaveMode" />
              Создать новую таблицу
            </label>
            <label style="display:flex; align-items:center; gap:6px; font-weight:500;">
              <input type="radio" value="existing" v-model="dbSaveMode" />
              Сохранить в существующую
            </label>
          </div>
          <!-- Новая таблица -->
          <div v-if="dbSaveMode === 'new'">
            <div>
              <label class="input-label">Выберите схему:</label>
              <select v-model="selectedDbSchema" class="db-input">
                <option v-for="schema in dbSchemas" :key="schema" :value="schema">{{ schema }}</option>
              </select>
            </div>
            <div style="margin-top:0.7rem;">
              <label class="input-label">Название таблицы:</label>
              <input v-model="newTableName" class="db-input db-input-full" placeholder="Введите название таблицы" />
            </div>
            <div v-if="predictionRows && predictionRows.length" style="margin-bottom:1rem;">
              <label class="primary-keys-label" style="font-weight:500; color:#333; margin-bottom:0.5rem; display:block; margin-top:1.2rem;">Выберите первичные ключи (опционально):</label>
              <div style="display:flex; flex-wrap:wrap; gap:8px;">
                <label v-for="col in Object.keys(predictionRows[0]).filter(c => !/^0\.[1-9]$/.test(c))" :key="col" style="display:flex; align-items:center; gap:4px;">
                  <input type="checkbox" :value="col" v-model="selectedPrimaryKeys" />
                  <span>{{ col }}</span>
                </label>
              </div>
            </div>
          </div>
          <!-- Существующая таблица -->
          <div v-if="dbSaveMode === 'existing'">
            <div style="margin-bottom: 1rem;">
              <label class="input-label" style="display:block; margin-bottom:0.5rem;">Выберите схему:</label>
              <select v-model="selectedDbSchema" class="db-input" style="width:100%;margin-bottom:1rem;">
                <option v-for="schema in dbSchemas" :key="schema" :value="schema">{{ schema }}</option>
              </select>
            </div>
            <label class="input-label" style="display:block; margin-bottom:0.5rem;">Выберите таблицу:</label>
            <div v-if="dbTableCountAvailable !== null && dbTableCountTotal !== null" class="table-count-info">
              Доступно {{ dbTableCountAvailable }} таблиц из {{ dbTableCountTotal }}
            </div>
            <select v-model="selectedDbTable" class="db-input db-input-full">
              <option value="" disabled selected>Выберите таблицу...</option>
              <option v-for="table in filteredDbTables" :key="table" :value="table">{{ table }}</option>
            </select>
          </div>
          <div class="upload-to-db-footer">
            <button class="connect-btn" :disabled="saveToDbLoading || (dbSaveMode==='new' ? !newTableName : !selectedDbTable)" @click="saveResultsToDb">
              <span v-if="saveToDbLoading" class="spinner-wrap"><span class="spinner"></span>Сохранение...</span>
              <span v-else>Сохранить</span>
            </button>
            <div v-if="saveToDbError" class="error-message upload-to-db-error-area">{{ saveToDbError }}</div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Success Modal -->
    <Teleport to="body">
      <div v-if="saveSuccessModalVisible" class="success-modal-overlay">
        <div class="success-modal">
          <div class="success-icon">
            <svg width="80" height="80" viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="40" cy="40" r="40" fill="#4CAF50"/>
              <path d="M24 42L36 54L56 34" stroke="white" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
          <div class="success-text">Результаты успешно сохранены в БД</div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script lang="ts">
import { defineComponent, computed, ref, onMounted } from 'vue'
import { useMainStore } from '../stores/mainStore'
import { API_BASE_URL } from '@/apiConfig'

export default defineComponent({
  name: 'SaveResults',
  
  props: {
    isVisible: {
      type: Boolean,
      default: false
    },
    canSave: {
      type: Boolean,
      default: false
    }
  },

  setup(props) {
    const store = useMainStore()

    const canSaveButton = computed(() => {
      // Кнопки должны быть активны, если есть sessionId и predictionRows (даже если canSave всегда true)
      return !!store.sessionId && store.predictionRows.length > 0
    })

    // --- DB Save Modal State ---
    const dbConnected = computed(() => store.dbConnected)
    const saveToDbModalVisible = ref(false)
    const dbSaveMode = ref<'new' | 'existing'>('new')
    const newTableName = ref('')
    const selectedDbTable = ref('')
    const selectedDbSchema = ref('')
    const dbTables = computed(() => store.dbTables)
    const saveToDbLoading = ref(false)
    const saveToDbError = ref('')
    const saveSuccessModalVisible = ref(false)
    const dbTableCountAvailable = ref<number | null>(null)
    const dbTableCountTotal = ref<number | null>(null)
    const dbSchemas = ref<string[]>([])
    const dbTablesBySchema = ref<{[schema: string]: string[]}>({})
    const filteredDbTables = computed(() => {
      if (!selectedDbSchema.value) return []
      return dbTablesBySchema.value[selectedDbSchema.value] || []
    })
    const selectedPrimaryKeys = ref<string[]>([])
    const predictionRows = computed(() => store.predictionRows)

    // Получить список таблиц при открытии модалки
    const fetchDbTables = async () => {
      if (!store.dbConnected || !store.authToken) return
      try {
        const response = await fetch(`${API_BASE_URL}/get-tables`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${store.authToken}`
          },
        })
        const result = await response.json()
        // --- DEBUG LOG ---
        console.log('result.tables', result.tables)
        console.log('dbSchemas', Object.keys(result.tables))
        console.log('count_available', result.count_available)
        console.log('count_total', result.count_total)
        // --- END DEBUG LOG ---
        if (result.success) {
          dbSchemas.value = Object.keys(result.tables)
          dbTablesBySchema.value = result.tables
          selectedDbSchema.value = dbSchemas.value[0] || ''
          store.setDbTables(result.tables)
          dbTableCountAvailable.value = result.count_available ?? 0
          dbTableCountTotal.value = result.count_total ?? 0
        } else {
          dbSchemas.value = []
          dbTablesBySchema.value = {}
          store.setDbTables([])
          dbTableCountAvailable.value = null
          dbTableCountTotal.value = null
        }
      } catch (e) {
        dbSchemas.value = []
        dbTablesBySchema.value = {}
        store.setDbTables([])
        dbTableCountAvailable.value = null
        dbTableCountTotal.value = null
      }
    }

    const openSaveToDbModal = async () => {
      saveToDbModalVisible.value = true
      dbSaveMode.value = 'new'
      newTableName.value = ''
      selectedDbTable.value = ''
      selectedDbSchema.value = ''
      saveToDbError.value = ''
      dbTableCountAvailable.value = null
      dbTableCountTotal.value = null
      await fetchDbTables()
    }
    const closeSaveToDbModal = () => {
      saveToDbModalVisible.value = false
      saveToDbError.value = ''
    }

    // Сохранить результаты в БД
    const saveResultsToDb = async () => {
      if (!store.sessionId || !store.predictionRows.length) return
      saveToDbLoading.value = true
      saveToDbError.value = ''
      let tableName = ''
      let schema = selectedDbSchema.value
      if (!schema) {
        saveToDbError.value = 'Выберите схему.'
        saveToDbLoading.value = false
        return
      }
      if (dbSaveMode.value === 'new') {
        tableName = newTableName.value.trim()
        if (!tableName) {
          saveToDbError.value = 'Введите название новой таблицы.'
          saveToDbLoading.value = false
          return
        }
      } else {
        tableName = selectedDbTable.value
        if (!tableName) {
          saveToDbError.value = 'Выберите таблицу.'
          saveToDbLoading.value = false
          return
        }
      }
      try {
        const response = await fetch(`${API_BASE_URL}/save-prediction-to-db`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${store.authToken}`
          },
          body: JSON.stringify({
            schema,
            session_id: store.sessionId,
            table_name: tableName,
            create_new: dbSaveMode.value === 'new'
          })
        })
        const result = await response.json()
        if (result.success) {
          closeSaveToDbModal()
          saveSuccessModalVisible.value = true
          setTimeout(() => { saveSuccessModalVisible.value = false }, 1800)
        } else {
          saveToDbError.value = result.detail || 'Ошибка при сохранении в БД.'
        }
      } catch (e) {
        saveToDbError.value = 'Ошибка: ' + (e instanceof Error ? e.message : e)
      } finally {
        saveToDbLoading.value = false
      }
    }

    const saveToCsv = async () => {
      if (!store.sessionId) return
      const url = `${API_BASE_URL}/download_prediction_csv/${store.sessionId}`
      try {
        const response = await fetch(url)
        if (!response.ok) throw new Error('Ошибка скачивания CSV')
        const blob = await response.blob()
        const link = document.createElement('a')
        link.href = window.URL.createObjectURL(blob)
        link.download = `prediction_${store.sessionId}.csv`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
      } catch (e) {
        alert('Ошибка при скачивании CSV')
      }
    }

    const saveToExcel = async () => {
      if (!store.sessionId) return
      const url = `${API_BASE_URL}/download_prediction/${store.sessionId}`
      try {
        const response = await fetch(url)
        if (!response.ok) throw new Error('Ошибка скачивания Excel')
        const blob = await response.blob()
        const link = document.createElement('a')
        link.href = window.URL.createObjectURL(blob)
        link.download = `prediction_${store.sessionId}.xlsx`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
      } catch (e) {
        alert('Ошибка при скачивании Excel')
      }
    }

    return {
      saveToCsv,
      saveToExcel,
      canSaveButton,
      dbConnected,
      saveToDbModalVisible,
      dbSaveMode,
      newTableName,
      selectedDbTable,
      selectedDbSchema,
      dbTables,
      saveToDbLoading,
      saveToDbError,
      saveSuccessModalVisible,
      dbTableCountAvailable,
      dbTableCountTotal,
      dbSchemas,
      dbTablesBySchema,
      filteredDbTables,
      openSaveToDbModal,
      closeSaveToDbModal,
      saveResultsToDb,
      selectedPrimaryKeys,
      predictionRows,
    }
  }
})
</script>

<style scoped>
.save-results {
  margin-top: 2rem;
}

.section-title {
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 1.5rem;
  color: #333;
}

.save-buttons {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.save-button {
  width: 100%;
  padding: 0.75rem;
  font-size: 1rem;
  font-weight: 500;
  color: white;
  background-color: #1976d2;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s ease;
  margin-bottom: 0;
}

.save-button:hover:not(:disabled) {
  background-color: #1565c0;
}

.save-button:disabled {
  background-color: #bbdefb;
  cursor: not-allowed;
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
  z-index: 1000;
}

.db-modal {
  background: white;
  padding: 2rem;
  border-radius: 8px;
  width: 90%;
  max-width: 500px;
  position: relative;
}

.close-btn {
  position: absolute;
  top: 1rem;
  right: 1rem;
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
}

.db-input {
  width: 100%;
  padding: 0.75rem;
  font-size: 1rem;
  border: 1px solid #ccc;
  border-radius: 4px;
  margin-bottom: 0.5rem;
}

.error-message {
  color: red;
  margin-top: 1rem;
}

.success-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.success-modal {
  background: white;
  padding: 2rem;
  border-radius: 8px;
  width: 90%;
  max-width: 500px;
  text-align: center;
  animation: fadeIn 0.5s, fadeOut 0.5s 1.3s;
}

.success-icon {
  margin-bottom: 1rem;
}

.success-text {
  color: #4CAF50;
  font-weight: bold;
  font-size: 1.2rem;
  margin-top: 0.5rem;
}

.table-count-info {
  font-size: 0.88rem;
  color: #1976d2;
  font-weight: 500;
  margin-bottom: 0.5rem;
}

.connect-btn {
  margin-bottom: 0px;
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

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes fadeOut {
  from { opacity: 1; }
  to { opacity: 0; }
}

/* Ensure modal label/field spacing and section headers are consistent */
.db-modal .input-label {
  margin-top: 0;
  font-size: 0.97rem;
  padding: 0;
}

.db-modal .db-input {
  padding: 0.45rem 0.6rem;
  margin-bottom: 0.5rem;
}

.db-input-full {
  margin-bottom: 1rem !important;
}

/* Increase margin above primary keys label if present */
.primary-keys-label {
  margin-top: 1.2rem !important;
}
</style>
