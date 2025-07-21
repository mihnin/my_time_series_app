import * as XLSX from 'xlsx'
import Papa from 'papaparse'
import { API_BASE_URL } from '../apiConfig'

/**
 * Читает файл и возвращает данные в формате { columns, rows, totalRows }
 * @param {File} file - Загруженный файл
 * @returns {Promise<{columns: string[], rows: string[][], totalRows: number}>}
 */
export const parseFile = (file) => {
  return new Promise(async (resolve, reject) => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch(`${API_BASE_URL}/preview-excel`, {
        method: 'POST',
        body: formData
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        reject(new Error(err.detail || 'Ошибка при предпросмотре файла'));
        return;
      }
      const result = await response.json();
      const columns = result.columns || [];
      const rows = Array.isArray(result.rows)
        ? result.rows.map(rowObj => columns.map(col => rowObj[col] ?? ''))
        : [];
      resolve({
        columns,
        rows,
        totalRows: result.total_rows
      });
    } catch (error) {
      reject(new Error(error.message || 'Ошибка при предпросмотре файла'));
    }
  });
}

/**
 * Валидирует размер файла
 * @param {File} file - Файл для проверки
 * @param {number} maxSizeMB - Максимальный размер в МБ
 * @returns {boolean}
 */
export const validateFileSize = (file, maxSizeMB = 100) => {
  const maxSizeBytes = maxSizeMB * 1024 * 1024
  return file.size <= maxSizeBytes
}

/**
 * Валидирует тип файла
 * @param {File} file - Файл для проверки
 * @returns {boolean}
 */
export const validateFileType = (file) => {
  const allowedExtensions = ['csv', 'xlsx', 'xls']
  const fileExtension = file.name.split('.').pop().toLowerCase()
  return allowedExtensions.includes(fileExtension)
}

/**
 * Форматирует размер файла для отображения
 * @param {number} bytes - Размер в байтах
 * @returns {string}
 */
export const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}
