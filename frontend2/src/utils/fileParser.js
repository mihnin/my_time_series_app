import * as XLSX from 'xlsx'
import Papa from 'papaparse'

/**
 * Читает файл и возвращает данные в формате { columns, rows }
 * @param {File} file - Загруженный файл
 * @returns {Promise<{columns: string[], rows: string[][]}>}
 */
export const parseFile = (file) => {
  return new Promise((resolve, reject) => {
    const fileExtension = file.name.split('.').pop().toLowerCase()
    const reader = new FileReader()

    reader.onload = (e) => {
      try {
        const data = e.target.result
        let parsedData

        if (fileExtension === 'csv') {
          // Обработка CSV файлов
          const parsed = Papa.parse(data, {
            header: false,
            skipEmptyLines: true,
            encoding: 'UTF-8'
          })
          
          if (parsed.errors.length > 0) {
            console.warn('Papa Parse warnings:', parsed.errors)
          }

          const rows = parsed.data
          if (rows.length === 0) {
            reject(new Error('Файл пуст'))
            return
          }

          const columns = rows[0] // Первая строка - заголовки
          const dataRows = rows.slice(1) // Остальные строки - данные

          parsedData = {
            columns: columns.map(col => String(col)),
            rows: dataRows.map(row => row.map(cell => String(cell || '')))
          }
        } else if (fileExtension === 'xlsx' || fileExtension === 'xls') {
          // Обработка Excel файлов
          const workbook = XLSX.read(data, { type: 'array' })
          const firstSheetName = workbook.SheetNames[0]
          const worksheet = workbook.Sheets[firstSheetName]
          
          // Преобразуем в массив массивов
          const jsonData = XLSX.utils.sheet_to_json(worksheet, { 
            header: 1,
            defval: '',
            raw: false // Преобразуем все в строки
          })

          if (jsonData.length === 0) {
            reject(new Error('Файл пуст'))
            return
          }

          const columns = jsonData[0] // Первая строка - заголовки
          const dataRows = jsonData.slice(1) // Остальные строки - данные

          parsedData = {
            columns: columns.map(col => String(col || '')),
            rows: dataRows.map(row => row.map(cell => String(cell || '')))
          }
        } else {
          reject(new Error('Неподдерживаемый формат файла'))
          return
        }

        // Фильтруем пустые строки
        parsedData.rows = parsedData.rows.filter(row => 
          row.some(cell => cell.trim() !== '')
        )

        resolve(parsedData)
      } catch (error) {
        reject(new Error(`Ошибка при чтении файла: ${error.message}`))
      }
    }

    reader.onerror = () => {
      reject(new Error('Ошибка при чтении файла'))
    }

    // Читаем файл в зависимости от типа
    if (fileExtension === 'csv') {
      reader.readAsText(file, 'UTF-8')
    } else {
      reader.readAsArrayBuffer(file)
    }
  })
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
