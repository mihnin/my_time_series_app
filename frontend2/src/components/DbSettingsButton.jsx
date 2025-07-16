import React, { useState } from 'react';
import { Card, CardContent, CardTitle } from '@/components/ui/card.jsx';
import { Button } from '@/components/ui/button.jsx';
import { Input } from '@/components/ui/input.jsx';
import { Label } from '@/components/ui/label.jsx';
import { Settings, CheckCircle, X } from 'lucide-react';
import { API_BASE_URL } from '../apiConfig.js';

export default function DbSettingsButton() {
  const [showSecretModal, setShowSecretModal] = useState(false);
  const [showEnvModal, setShowEnvModal] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [secretKey, setSecretKey] = useState('');
  const [envVars, setEnvVars] = useState({
    DB_USER: '',
    DB_PASS: '',
    DB_HOST: '',
    DB_PORT: '',
    DB_NAME: '',
    DB_SCHEMA: ''
  });
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  // Открыть модалку для ввода ключа
  const openSecretModal = () => {
    setErrorMessage('');
    setSecretKey('');
    setShowSecretModal(true);
  };

  // Проверка секретного ключа
  const validateSecretKey = async () => {
    if (!secretKey) {
      setErrorMessage('Введите секретный ключ');
      return;
    }
    setIsLoading(true);
    setErrorMessage('');
    try {
      const response = await fetch(`${API_BASE_URL}/validate-secret-key`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ secret_key: secretKey })
      });
      const data = await response.json();
      if (data.success) {
        setShowSecretModal(false);
        setShowEnvModal(true);
        setEnvVars({
          DB_USER: data.db_vars?.DB_USER || '',
          DB_PASS: data.db_vars?.DB_PASS || '',
          DB_HOST: data.db_vars?.DB_HOST || '',
          DB_PORT: data.db_vars?.DB_PORT || '',
          DB_NAME: data.db_vars?.DB_NAME || '',
          DB_SCHEMA: data.db_vars?.DB_SCHEMA || ''
        });
      } else {
        setErrorMessage('Неверный секретный ключ');
      }
    } catch (e) {
      setErrorMessage('Ошибка при проверке ключа');
    } finally {
      setIsLoading(false);
    }
  };

  // Сохранить переменные окружения
  const updateEnvVariables = async () => {
    setIsLoading(true);
    setErrorMessage('');
    try {
      const response = await fetch(`${API_BASE_URL}/update-env-variables`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ secret_key: secretKey, ...envVars })
      });
      const data = await response.json();
      if (data.success) {
        setShowEnvModal(false);
        setShowSuccess(true);
        setTimeout(() => setShowSuccess(false), 2000);
      } else {
        setErrorMessage(data.message || 'Не удалось обновить настройки');
      }
    } catch (e) {
      setErrorMessage('Ошибка при обновлении настроек');
    } finally {
      setIsLoading(false);
    }
  };

  // Стили для кнопки-шестерёнки (левый нижний угол)
  const fabStyle = {
    position: 'absolute',
    left: 24,
    bottom: 24,
    zIndex: 50
  };

  return (
    <>
      {/* Кнопка-шестерёнка */}
      <Button
        variant="outline"
        size="icon"
        style={fabStyle}
        className="rounded-full shadow-md bg-white hover:bg-primary/10 border border-gray-200"
        onClick={openSecretModal}
        title="Настройки БД"
      >
        <Settings size={22} />
      </Button>

      {/* Модалка: ввод секретного ключа */}
      {showSecretModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-sm relative">
            <button className="absolute top-2 right-3 text-gray-500 hover:text-red-600 text-2xl font-bold" onClick={() => setShowSecretModal(false)}>&times;</button>
            <h3 className="text-lg font-bold mb-4">Изменение переменных окружения</h3>
            <Label htmlFor="secret-key">Секретный ключ</Label>
            <Input
              id="secret-key"
              type="password"
              className="mb-3 mt-1"
              value={secretKey}
              onChange={e => setSecretKey(e.target.value)}
              autoFocus
            />
            {errorMessage && <div className="text-red-600 text-sm mb-2">{errorMessage}</div>}
            <Button className="w-full mt-2" onClick={validateSecretKey} disabled={isLoading}>
              {isLoading ? 'Подключение...' : 'Подключиться'}
            </Button>
          </div>
        </div>
      )}

      {/* Модалка: редактирование переменных окружения */}
      {showEnvModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md relative">
            <button className="absolute top-2 right-3 text-gray-500 hover:text-red-600 text-2xl font-bold" onClick={() => setShowEnvModal(false)}>&times;</button>
            <h3 className="text-lg font-bold mb-4">Изменение переменных окружения</h3>
            <div className="space-y-3">
              <div>
                <Label htmlFor="db-user">Пользователь БД</Label>
                <Input id="db-user" value={envVars.DB_USER} onChange={e => setEnvVars(v => ({ ...v, DB_USER: e.target.value }))} className="mt-1" />
              </div>
              <div>
                <Label htmlFor="db-pass">Пароль БД</Label>
                <Input id="db-pass" type="password" value={envVars.DB_PASS} onChange={e => setEnvVars(v => ({ ...v, DB_PASS: e.target.value }))} className="mt-1" />
              </div>
              <div>
                <Label htmlFor="db-host">Хост</Label>
                <Input id="db-host" value={envVars.DB_HOST} onChange={e => setEnvVars(v => ({ ...v, DB_HOST: e.target.value }))} className="mt-1" />
              </div>
              <div>
                <Label htmlFor="db-port">Порт</Label>
                <Input id="db-port" value={envVars.DB_PORT} onChange={e => setEnvVars(v => ({ ...v, DB_PORT: e.target.value }))} className="mt-1" />
              </div>
              <div>
                <Label htmlFor="db-name">Имя БД</Label>
                <Input id="db-name" value={envVars.DB_NAME} onChange={e => setEnvVars(v => ({ ...v, DB_NAME: e.target.value }))} className="mt-1" />
              </div>
              <div>
                <Label htmlFor="db-schema">Схема</Label>
                <Input id="db-schema" value={envVars.DB_SCHEMA} onChange={e => setEnvVars(v => ({ ...v, DB_SCHEMA: e.target.value }))} className="mt-1" />
              </div>
            </div>
            {errorMessage && <div className="text-red-600 text-sm mt-2">{errorMessage}</div>}
            <Button className="w-full mt-4" onClick={updateEnvVariables} disabled={isLoading}>
              {isLoading ? 'Сохранение...' : 'Сохранить настройки'}
            </Button>
          </div>
        </div>
      )}

      {/* Модалка: успех */}
      {showSuccess && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-lg p-6 w-full max-w-xs flex flex-col items-center">
            <CheckCircle className="text-green-600 mb-2" size={36} />
            <div className="text-lg font-bold mb-1">Успешно!</div>
            <div className="text-green-700 text-sm">Переменные окружения успешно изменены</div>
          </div>
        </div>
      )}
    </>
  );
} 