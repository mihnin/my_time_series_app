<template>
  <div class="db-settings-btn-wrap">
    <details class="advanced-settings">
      <summary>Настройки для продвинутых пользователей</summary>
      <button class="db-settings-btn" @click="showDbModal = true">
        <span class="gear-icon">⚙️</span>
        <span class="btn-text">Настройки БД</span>
      </button>
    </details>

    <!-- Модальное окно для ввода секретного ключа -->
    <Teleport to="body">
      <div v-if="showDbModal" class="modal-overlay">
        <div class="modal-content">
          <button class="modal-close" @click="closeDbModal" aria-label="Закрыть">&times;</button>
          <h4>Подключение к БД</h4>
          <label for="secret-word">Секретное слово:</label>        <input id="secret-word" v-model="secretWord" type="password" class="secret-input" />        
          <button @click="validateSecretKey" class="connect-btn full-width" :disabled="isLoading">
            {{ isLoading ? 'Подождите...' : 'Подключиться' }}
          </button>
          <div class="error-container">
            <div v-if="errorMessage" class="error-message">{{ errorMessage }}</div>
          </div>
        </div>
      </div>
    </Teleport>
    
    <!-- Модальное окно для настройки окружения -->
    <Teleport to="body">
      <div v-if="showEnvModal" class="modal-overlay">
        <div class="modal-content env-settings-modal">
          <button class="modal-close" @click="closeEnvModal" aria-label="Закрыть">&times;</button>
          <h4>Настройки соединения с БД</h4>
          
          <div class="form-group">
            <label for="db-user">Пользователь БД:</label>
            <input id="db-user" v-model="envVars.DB_USER" class="env-input" />
          </div>
          
          <div class="form-group">
            <label for="db-pass">Пароль БД:</label>
            <input id="db-pass" v-model="envVars.DB_PASS" type="password" class="env-input" />
          </div>
          
          <div class="form-group">
            <label for="db-host">Хост:</label>
            <input id="db-host" v-model="envVars.DB_HOST" class="env-input" />
          </div>
          
          <div class="form-group">
            <label for="db-port">Порт:</label>
            <input id="db-port" v-model="envVars.DB_PORT" class="env-input" />
          </div>
          
          <div class="form-group">
            <label for="db-name">Имя БД:</label>
            <input id="db-name" v-model="envVars.DB_NAME" class="env-input" />
          </div>
          
          <div class="form-group">
            <label for="db-schema">Схема:</label>
            <input id="db-schema" v-model="envVars.DB_SCHEMA" class="env-input" />
          </div>
            <button @click="updateEnvVariables" class="connect-btn full-width" :disabled="isLoading">
            {{ isLoading ? 'Сохранение...' : 'Сохранить настройки' }}
          </button>
          
          <div class="error-container">
            <div v-if="errorMessage" class="error-message">{{ errorMessage }}</div>
          </div>
        </div>
      </div>
    </Teleport>
      <!-- Модальное окно успешного обновления -->
    <Teleport to="body">
      <div v-if="successModalVisible" class="success-modal-overlay">
        <div class="success-modal">
          <div class="success-icon">✓</div>
          <h3>Успешно!</h3>
          <p class="success-text">Переменные окружения успешно изменены</p>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, reactive } from 'vue'

export default defineComponent({
  name: 'DbSettingsButton',
  setup() {
    const showDbModal = ref(false)
    const showEnvModal = ref(false)
    const secretWord = ref('')
    const isLoading = ref(false)
    const errorMessage = ref('')
    const successModalVisible = ref(false)
    
    // Параметры окружения по умолчанию
    const envVars = reactive({
      DB_USER: '',
      DB_PASS: '',
      DB_HOST: '',
      DB_PORT: '',
      DB_NAME: '',
      DB_SCHEMA: ''
    })      // Валидировать секретное слово
    const validateSecretKey = async () => {
      if (!secretWord.value) {
        errorMessage.value = 'Введите секретное слово'
        return
      }
      
      isLoading.value = true
      errorMessage.value = ''
      
      try {
        const response = await fetch('http://localhost:8000/validate-secret-key', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            secret_key: secretWord.value
          })
        })
        
        const data = await response.json()
        
        if (data.success) {
          // Если секретный ключ верный, показываем окно настроек окружения
          showDbModal.value = false
          showEnvModal.value = true
          
          // Заполнение параметров из полученных данных API
          if (data.db_vars) {
            envVars.DB_USER = data.db_vars.DB_USER || ''
            envVars.DB_PASS = data.db_vars.DB_PASS || ''
            envVars.DB_HOST = data.db_vars.DB_HOST || ''
            envVars.DB_PORT = data.db_vars.DB_PORT || ''
            envVars.DB_NAME = data.db_vars.DB_NAME || ''
            envVars.DB_SCHEMA = data.db_vars.DB_SCHEMA || ''
          }
        } else {
          errorMessage.value = 'Неверное секретное слово'
        }
      } catch (error) {
        errorMessage.value = 'Ошибка при проверке ключа'
        console.error('Error validating secret key:', error)
      } finally {
        isLoading.value = false
      }
    }
      // Обновить переменные окружения
    const updateEnvVariables = async () => {
      isLoading.value = true
      errorMessage.value = ''
      
      try {
        const response = await fetch('http://localhost:8000/update-env-variables', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            secret_key: secretWord.value,
            ...envVars
          })
        })
          const data = await response.json()
        
        if (data.success) {
          showEnvModal.value = false
          successModalVisible.value = true
          
          // Автоматически скрываем окно успеха через 2 секунды
          setTimeout(() => {
            successModalVisible.value = false
            secretWord.value = ''
          }, 2000)
        } else {
          errorMessage.value = data.message || 'Не удалось обновить настройки'
        }
      } catch (error) {
        errorMessage.value = 'Ошибка при обновлении настроек'
        console.error('Error updating environment variables:', error)
      } finally {
        isLoading.value = false
      }
    }
    
    // Закрыть модальное окно ввода секретного слова
    const closeDbModal = () => {
      showDbModal.value = false
      secretWord.value = ''
      errorMessage.value = ''
    }
    
    // Закрыть модальное окно настроек окружения
    const closeEnvModal = () => {
      showEnvModal.value = false
      errorMessage.value = ''
    }
      // Функция closeSuccessModal больше не нужна, т.к. окно закрывается автоматически
      return {
      showDbModal,
      showEnvModal,
      secretWord,
      envVars,
      isLoading,
      errorMessage,
      successModalVisible,
      validateSecretKey,
      updateEnvVariables,
      closeDbModal,
      closeEnvModal
    }
  }
})
</script>

<style scoped>
.db-settings-btn-wrap {
  margin-bottom: 1rem;
}
.advanced-settings {
  margin-bottom: 1rem;
  user-select: none;
}
.advanced-settings summary {
  cursor: pointer;
  color: #666;
  font-size: 0.9rem;
  margin-bottom: 0.5rem;
}
.advanced-settings summary:hover {
  color: #2196F3;
}
.db-settings-btn {
  width: 100%;
  padding: 0.75rem;
  background-color: #2196F3;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: background-color 0.2s;
  font-size: 0.95rem;
}
.db-settings-btn:hover {
  background-color: #1976D2;
}
.gear-icon {
  font-size: 1.2rem;
  line-height: 1;
  color: white;
}
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  isolation: isolate;
}
.modal-content {
  position: relative;
  background: #fff;
  padding: 2rem;
  border-radius: 8px;
  min-width: 320px;
  box-shadow: 0 2px 16px rgba(0,0,0,0.15);
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.modal-close {
  position: absolute;
  top: 0.5rem;
  right: 0.7rem;
  background: none;
  border: none;
  font-size: 2rem;
  color: #888;
  cursor: pointer;
}
.modal-close:active, .modal-close:focus {
  background: none !important;
  outline: none;
  box-shadow: none;
}
.modal-close:hover {
  color: #888;
}
.secret-input {
  width: 100%;
  padding: 0.5rem;
  font-size: 1rem;
  border: 1px solid #ccc;
  border-radius: 4px;
}
.connect-btn {
  background: #388e3c;
  color: #fff;
  border: none;
  border-radius: 4px;
  padding: 0.5rem 1.2rem;
  font-weight: 500;
  cursor: pointer;
}
.connect-btn:hover {
  background: #2e7031;
}
.full-width {
  width: 100%;
  margin-top: 1rem;
}
.gear-icon {
  font-size: 1.45rem;
  color: #888;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.3rem;
  font-weight: 500;
}

.env-input {
  width: 100%;
  padding: 0.5rem;
  font-size: 1rem;
  border: 1px solid #ccc;
  border-radius: 4px;
}

.env-settings-modal {
  max-width: 450px;
}

.error-container {
  height: 30px; /* Фиксированная высота контейнера */
  margin-top: 0.5rem;
  display: flex;
  align-items: center;
}

.error-message {
  color: #f44336;
  font-size: 0.9rem;
  display: block;
  width: 100%;
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
  z-index: 9999;
  isolation: isolate;
}

.success-modal {
  background: white;
  padding: 2rem;
  border-radius: 8px;
  width: 90%;
  max-width: 400px;
  text-align: center;
}

.success-icon {
  background-color: #4CAF50;
  color: white;
  width: 60px;
  height: 60px;
  font-size: 2.5rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 1.5rem;
}

.success-text {
  color: #4CAF50;
  font-weight: 500;
  font-size: 1.1rem;
  margin-bottom: 1.5rem;
}

.ok-btn {
  background: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 0.6rem 1.5rem;
  font-weight: 500;
  cursor: pointer;
}

.ok-btn:hover {
  background: #388E3C;
}
</style>
