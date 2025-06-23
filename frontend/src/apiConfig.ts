// Конфиг для API: импорт переменных из .env через import.meta.env

const BACKEND_ADDRESS = import.meta.env.VITE_BACKEND_ADDRESS || 'http://localhost';
const BACKEND_PORT = import.meta.env.VITE_BACKEND_PORT || '8000';

export const API_BASE_URL = `${BACKEND_ADDRESS}:${BACKEND_PORT}`;
