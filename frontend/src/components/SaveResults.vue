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
    <div v-if="saveToDbModalVisible" class="db-modal-overlay" @click="closeSaveToDbModal">
      <div class="db-modal" @click.stop>
        <button class="close-btn" @click="closeSaveToDbModal">×</button>
        <h3 style="margin-bottom:1rem">Сохранить результаты в БД</h3>
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
        <div v-if="dbSaveMode==='new'">
          <input v-model="newTableName" class="db-input db-input-full" placeholder="Название новой таблицы" style="margin-bottom:1rem;" />
        </div>
        <div v-if="dbSaveMode==='existing'">
          <div v-if="dbTableCountAvailable !== null && dbTableCountTotal !== null" style="margin-bottom:0.5rem;font-size:0.98rem;color:#1976d2;font-weight:500;">
            Доступно {{ dbTableCountAvailable }} таблиц из {{ dbTableCountTotal }}
          </div>
          <select v-model="selectedDbTable" class="db-input db-input-full" style="margin-bottom:1rem;">
            <option value="" disabled>Выберите таблицу...</option>
            <option v-for="table in dbTables" :key="table" :value="table">{{ table }}</option>
          </select>
        </div>
        <button class="save-button" style="margin-bottom:0;" :disabled="saveToDbLoading || (dbSaveMode==='new' ? !newTableName : !selectedDbTable)" @click="saveResultsToDb">
          <span v-if="saveToDbLoading" class="spinner-wrap"><span class="spinner"></span>Сохранение...</span>
          <span v-else>Сохранить</span>
        </button>
        <div v-if="saveToDbError" class="error-message">{{ saveToDbError }}</div>
      </div>
    </div>

    <!-- Success Modal -->
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
  </div>
</template>

<script lang="ts">
import { defineComponent, computed, ref, onMounted } from 'vue'
import { useMainStore } from '../stores/mainStore'

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
    const dbTables = computed(() => store.dbTables)
    const saveToDbLoading = ref(false)
    const saveToDbError = ref('')
    const saveSuccessModalVisible = ref(false)
    const dbTableCountAvailable = ref<number | null>(null)
    const dbTableCountTotal = ref<number | null>(null)

    // Получить список таблиц при открытии модалки
    const fetchDbTables = async () => {
      if (!store.dbConnected || !store.authToken) return
      try {
        const response = await fetch('http://localhost:8000/get-tables', {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${store.authToken}`
          },
        })
        const result = await response.json()
        if (result.success) {
          store.setDbTables(result.tables)
          dbTableCountAvailable.value = result.count_available ?? result.tables.length
          dbTableCountTotal.value = result.count_total ?? result.tables.length
        } else {
          store.setDbTables([])
          dbTableCountAvailable.value = null
          dbTableCountTotal.value = null
        }
      } catch (e) {
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
        const response = await fetch('http://localhost:8000/save-prediction-to-db', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${store.authToken}`
          },
          body: JSON.stringify({
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
      const url = `http://localhost:8000/download_prediction_csv/${store.sessionId}`
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
      const url = `http://localhost:8000/download_prediction/${store.sessionId}`
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
      dbTables,
      saveToDbLoading,
      saveToDbError,
      saveSuccessModalVisible,
      dbTableCountAvailable,
      dbTableCountTotal,
      openSaveToDbModal,
      closeSaveToDbModal,
      saveResultsToDb
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

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes fadeOut {
  from { opacity: 1; }
  to { opacity: 0; }
}
</style>
