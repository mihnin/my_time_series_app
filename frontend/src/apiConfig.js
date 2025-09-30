// Конфиг для API: импорт переменных из .env через import.meta.env

// Поддерживаем два формата конфигурации:
// 1. VITE_API_BASE_URL - полный URL (приоритет)
// 2. VITE_BACKEND_ADDRESS + VITE_BACKEND_PORT - составной URL (fallback)
const API_BASE_URL_DIRECT = import.meta.env.VITE_API_BASE_URL;
const BACKEND_ADDRESS = import.meta.env.VITE_BACKEND_ADDRESS || 'http://172.16.33.12';
const BACKEND_PORT = import.meta.env.VITE_BACKEND_PORT || '9081';

export const API_BASE_URL = API_BASE_URL_DIRECT || `${BACKEND_ADDRESS}:${BACKEND_PORT}`;
