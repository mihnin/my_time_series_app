<template>
  <div class="db-connection">    <button v-if="!isConnected" class="toggle-btn" @click="openModal" title="Подключение к БД">
      <span class="db-icon">🛢️</span>
    </button>
    <button v-else class="toggle-btn disconnect-btn" @click="disconnect" title="Отключиться от БД">
      <span class="db-icon">🛢️</span><span class="disconnect-icon">❌</span>
    </button>
    <!-- Модальное окно -->
    <div v-if="modalVisible" class="db-modal-overlay" @click="closeModal">
      <div class="db-modal" @click.stop>
        <button class="close-btn" @click="closeModal">×</button>
        <h3 style="margin-bottom:1rem">Подключение к базе данных</h3>
        <input v-model="login"
               type="text"
               placeholder="Логин"
               class="db-input db-input-full"
               :disabled="isConnected"
               :style="isConnected ? 'cursor: not-allowed;' : ''"
               @keyup.enter="!isConnected && connect()"
        />
        <input v-model="password"
               type="password"
               placeholder="Пароль"
               class="db-input db-input-full"
               :disabled="isConnected"
               :style="isConnected ? 'cursor: not-allowed;' : ''"
               @keyup.enter="!isConnected && connect()"
        />
        <button
          v-if="!isConnected"
          class="connect-btn"
          @click="connect"
          :disabled="connecting || isConnected"
        >
          Подключиться
        </button>
        <div v-if="error" class="error-message">{{ error }}</div>
      </div>
    </div>

    <!-- Success Modal -->
    <div v-if="successModalVisible" class="success-modal-overlay">
      <div class="success-modal">
        <div class="success-icon">
          <svg width="80" height="80" viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="40" cy="40" r="40" fill="#4CAF50"/>
            <path d="M24 42L36 54L56 34" stroke="white" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="success-text">Подключение успешно</div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed } from 'vue'
import { useMainStore } from '../stores/mainStore'

export default defineComponent({
  name: 'DbConnection',
  setup() {
    const open = ref(false)
    const modalVisible = ref(false)
    const login = ref('')
    const password = ref('')
    const connecting = ref(false)
    const error = ref('')
    const store = useMainStore()
    const fetchingTables = ref(false)
    const selectedDbTable = ref('');
    const successModalVisible = ref(false)

    // Вычисляемое состояние подключения
    const isConnected = computed(() => store.dbConnected)

    const toggleOpen = () => {
      open.value = !open.value
    }

    const openModal = async () => {
      modalVisible.value = true
      // Загружаем таблицы только при открытии модального окна, если подключены
      if (isConnected.value && store.authToken) {
        fetchingTables.value = true;
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
            error.value = '';
          } else {
            error.value = result.detail || 'Не удалось загрузить таблицы из БД.';
            store.setDbTables([]);
          }
        } catch (e: any) {
          error.value = 'Ошибка при загрузке таблиц: ' + (e && typeof e === 'object' && 'message' in e ? (e as any).message : String(e));
          store.setDbTables([]);
        } finally {
          fetchingTables.value = false;
        }
      }
    }
    const closeModal = () => {
      modalVisible.value = false
    }

    const connect = async () => {
      error.value = ''
      connecting.value = true
      try {
        const response = await fetch('http://localhost:8000/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: login.value, password: password.value })
        })
        let result = null
        try {
          result = await response.json()
        } catch (jsonErr) {
          error.value = 'Не удалось получить ответ от сервера.'
          store.setDbConnected(false)
          connecting.value = false
          return
        }

        store.setDbCheckResult(result)
        if (result.success && result.access_token) {
          store.setAuthToken(result.access_token) // Сохраняем токен в Pinia (в памяти)
          store.setDbConnected(true)
          // Очищаем логин/пароль из локальных состояний компонента
          login.value = ''
          password.value = ''
          // Показываем success-модалку и скрываем основную
          modalVisible.value = false
          successModalVisible.value = true
          setTimeout(() => { successModalVisible.value = false }, 1800)
        } else {
          error.value = 'Не удалось подключиться к базе данных'
          store.setDbConnected(false)
          store.setAuthToken(null)
        }
      } catch (e: any) {
        error.value = `Ошибка сети: ${e.message}`
        store.setDbConnected(false)
        store.setAuthToken(null)
      } finally {
        connecting.value = false
      }
    }

    const disconnect = () => {
      store.setAuthToken(null) // Очищаем токен из Pinia
      store.setDbConnected(false)
      store.setDbCheckResult(null)
      store.setDbTables([]) // Очищаем список таблиц
      selectedDbTable.value = ''
      error.value = ''
    }

    return {
      open,
      login,
      password,
      connecting,
      error,
      toggleOpen,
      connect,
      disconnect,
      store,
      isConnected,
      selectedDbTable,
      fetchingTables,
      modalVisible,
      openModal,
      closeModal,
      successModalVisible,
    }
  }
})
</script>

<style scoped>
/* Ваши стили остаются без изменений */
.db-connection {
  position: fixed;
  top: 1.2rem;
  right: 1.2rem;
  z-index: 50;
}
.toggle-btn {
  width: 40px;
  height: 40px;
  background: #fff;
  color: #2196F3;
  border: 1px solid #e0e0e0;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  margin-bottom: 0.5rem;
  box-shadow: 0 2px 8px rgba(33, 150, 243, 0.08);
  transition: background 0.2s, box-shadow 0.2s, transform 0.1s;
  letter-spacing: 0.5px;
  font-family: inherit;
}
.toggle-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(33, 150, 243, 0.2);
}

.db-icon {
  font-size: 1.4rem;
  line-height: 1;
}

.disconnect-icon {
  position: absolute;
  top: -4px;
  right: -4px;
  font-size: 0.9rem;
  color: #e53935;
  background: white;
  border-radius: 50%;
  line-height: 1;
}
.db-form {
  margin-top: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.db-input {
  padding: 0.5rem;
  font-size: 1rem;
  border: 1px solid #ccc;
  border-radius: 4px;
}
.db-input-full {
  width: 100%;
  box-sizing: border-box;
  display: block;
  margin-bottom: 0.5rem;
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
  margin-top: 0.5rem;
  font-family: inherit;
}
.connect-btn:hover:not(:disabled) {
  background-color: #1976d2;
}
.connect-btn:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}
.disconnect-btn {
  background: #fff;
  color: #e53935;
  border: 1px solid #e0e0e0;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  transition: all 0.2s ease;
  letter-spacing: 0.5px;
  font-family: inherit;
}
.disconnect-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(229, 57, 53, 0.2);
}
.error-message {
  color: red;
  font-size: 0.9rem;
  margin-top: 0.5rem;
}
.success-message {
  color: #388e3c;
  font-size: 0.95rem;
  margin-top: 0.5rem;
}
.db-input[disabled] {
  background: #f3f3f3;
  color: #aaa;
  cursor: not-allowed !important;
}
.db-input[disabled]:hover {
  cursor: not-allowed !important;
}
.db-input[disabled] {
  /* Красный перечеркнутый кружочек */
  caret-color: transparent;
}
.db-input[disabled]::-webkit-input-placeholder {
  color: #aaa;
}
.db-input[disabled] {
  /* Для курсора: перечеркнутый красный кружочек */
  pointer-events: auto;
}
.db-input[disabled]:hover {
  cursor: not-allowed !important;
}
.db-modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.35);
  z-index: 9998;
  display: flex;
  align-items: center;
  justify-content: center;
}
.db-modal {
  background: #fff;
  border-radius: 8px;
  padding: 2rem 2rem 1.5rem 2rem;
  min-width: 340px;
  max-width: 90vw;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 4px 32px rgba(0,0,0,0.18);
  position: relative;
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
}
.success-modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.35);
  z-index: 9998;
  display: flex;
  align-items: center;
  justify-content: center;
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