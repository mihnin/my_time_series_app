import React, { useState, useLayoutEffect, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useData } from '../contexts/DataContext'
import { parseFile, validateFileSize, validateFileType, formatFileSize } from '../utils/fileParser'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.jsx'
import { 
  Upload, 
  Database, 
  FileText, 
  CheckCircle,
  AlertCircle,
  Eye,
  Download
} from 'lucide-react'

// Read API base URL from environment
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export default function DataUpload() {
  const navigate = useNavigate()
  const { updateData, uploadedFile, setUploadedFile } = useData()
  
  // --- File upload state ---
  const [previewData, setPreviewData] = useState(null)
  const [fileLoading, setFileLoading] = useState(false)
  const [fileError, setFileError] = useState('')
  const [isDragOver, setIsDragOver] = useState(false)

  // --- DB connection/auth state ---
  const [dbUsername, setDbUsername] = useState('')
  const [dbPassword, setDbPassword] = useState('')
  const [dbConnecting, setDbConnecting] = useState(false)
  const [dbConnected, setDbConnected] = useState(false)
  const [dbError, setDbError] = useState('')
  const [dbSuccess, setDbSuccess] = useState(false)
  const [authToken, setAuthToken] = useState(null)

  // --- DB tables state ---
  const [dbTables, setDbTables] = useState([])
  const [dbTablesLoading, setDbTablesLoading] = useState(false)
  const [selectedDbTable, setSelectedDbTable] = useState('')
  const [selectedSchema, setSelectedSchema] = useState('')
  const [tablePreview, setTablePreview] = useState(null)
  const [tablePreviewLoading, setTablePreviewLoading] = useState(false)
  const [tablePreviewError, setTablePreviewError] = useState('')
  const [previewVisible, setPreviewVisible] = useState(false)
  const firstRenderRef = React.useRef(true)
  
  // Ref для автоматического скролла к предпросмотру
  const previewRef = useRef(null)

  // --- File upload logic ---
  const handleFileUpload = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    // Сброс предыдущих состояний
    setFileError('')
    setPreviewData(null)
    setUploadedFile(null)

    try {
      // Валидация размера файла
      if (!validateFileSize(file, 100)) {
        setFileError('Размер файла превышает 100 МБ')
        return
      }

      // Валидация типа файла
      if (!validateFileType(file)) {
        setFileError('Поддерживаются только файлы форматов CSV, XLSX, XLS')
        return
      }

      setFileLoading(true)
      setUploadedFile(file)

      // Парсинг файла
      const parsedData = await parseFile(file)
      
      // Ограничиваем предпросмотр первыми 10 строками для производительности
      const previewRows = parsedData.rows.slice(0, 10)
      
      setPreviewData({
        columns: parsedData.columns,
        rows: previewRows,
        totalRows: parsedData.rows.length
      })

    } catch (error) {
      console.error('Ошибка при обработке файла:', error)
      setFileError(error.message || 'Произошла ошибка при обработке файла')
      setUploadedFile(null)
      setPreviewData(null)
    } finally {
      setFileLoading(false)
    }
  }

  const handleClearFile = () => {
    setUploadedFile(null)
    setPreviewData(null)
    setFileError('')
    setFileLoading(false)
    // Очищаем input
    const fileInput = document.querySelector('input[type="file"]')
    if (fileInput) {
      fileInput.value = ''
    }
  }

  // Автоматический скролл к предпросмотру после загрузки файла
  useEffect(() => {
    if (previewData && previewRef.current) {
      // Небольшая задержка для завершения рендеринга
      setTimeout(() => {
        previewRef.current.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        })
      }, 100)
    }
  }, [previewData])

  // --- Drag & Drop handlers ---
  const handleDragEnter = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    e.stopPropagation()
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)

    const files = e.dataTransfer.files
    if (files.length > 0) {
      const file = files[0]
      // Создаем событие как для input
      const fakeEvent = {
        target: {
          files: [file]
        }
      }
      handleFileUpload(fakeEvent)
    }
  }

  // --- DB connect logic ---
  const handleDbConnect = async () => {
    setDbError('')
    setDbSuccess(false)
    setDbConnecting(true)
    try {
      const response = await fetch(`${API_BASE_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: dbUsername, password: dbPassword })
      })
      if (!response.ok) {
        if (response.status === 401) {
          setDbError('Неверный логин или пароль')
        } else {
          setDbError(`Ошибка сервера: ${response.status}`)
        }
        setDbConnected(false)
        setAuthToken(null)
        setDbConnecting(false)
        return
      }
      let result = null
      try {
        result = await response.json()
      } catch (jsonErr) {
        setDbError('Не удалось получить ответ от сервера.')
        setDbConnected(false)
        setDbConnecting(false)
        return
      }
      if (result.success && result.access_token) {
        setAuthToken(result.access_token)
        setDbConnected(true)
        setDbSuccess(true)
        setDbError('')
        setDbUsername('')
        setDbPassword('')
        // Optionally: setTimeout to hide success after a while
        setTimeout(() => setDbSuccess(false), 1800)
      } else {
        setDbError('Не удалось подключиться к базе данных')
        setDbConnected(false)
        setAuthToken(null)
      }
    } catch (e) {
      setDbError(`Ошибка сети: ${e.message}`)
      setDbConnected(false)
      setAuthToken(null)
    } finally {
      setDbConnecting(false)
    }
  }

  // --- DB disconnect logic ---
  const handleDbDisconnect = () => {
    setAuthToken(null)
    setDbConnected(false)
    setDbSuccess(false)
    setDbError('')
    setDbUsername('')
    setDbPassword('')
    // Optionally: clear any DB-related preview data
  }

  // --- Fetch tables after successful connection ---
  const fetchDbTables = async (token) => {
    setDbTablesLoading(true)
    setDbTables([])
    setSelectedDbTable('')
    setSelectedSchema('')
    setTablePreview(null)
    setTablePreviewError('')
    try {
      const response = await fetch(`${API_BASE_URL}/get-tables`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      })
      const result = await response.json()
      console.log('Ответ /get-tables:', result)
      if (result.success && result.tables && typeof result.tables === 'object') {
        const schemas = Object.keys(result.tables)
        const tablesBySchema = schemas.map(schema => ({
          schema,
          tables: Array.isArray(result.tables[schema]) ? result.tables[schema] : []
        })).filter(s => s.tables.length > 0)
        setDbTables(tablesBySchema)
        // Не выбирать схему и таблицу по умолчанию
        setSelectedSchema('')
        setSelectedDbTable('')
      } else {
        setDbTables([])
        setTablePreviewError('Не удалось получить список таблиц')
      }
    } catch (e) {
      setDbTables([])
      setTablePreviewError('Ошибка при получении списка таблиц')
    } finally {
      setDbTablesLoading(false)
    }
  }

  // --- Fetch table preview ---
  const fetchTablePreview = async (tableName) => {
    setTablePreviewLoading(true)
    setTablePreview(null)
    setTablePreviewError('')
    try {
      // tableName в формате schema.table
      const [schema, ...tableParts] = tableName.split('.')
      const table = tableParts.join('.')
      if (!schema || !table) {
        setTablePreviewError('Некорректное имя таблицы')
        setTablePreviewLoading(false)
        return
      }
      const url = `${API_BASE_URL}/get-table-preview`
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({ schema, table })
      })
      const result = await response.json()
      console.log('Ответ /get-table-preview:', result)
      if (result.success && Array.isArray(result.data) && result.data.length > 0) {
        const columns = Object.keys(result.data[0])
        const rows = result.data.map(rowObj => columns.map(col => rowObj[col]))
        setTablePreview({ columns, rows })
      } else if (result.success && Array.isArray(result.data) && result.data.length === 0) {
        setTablePreview({ columns: [], rows: [] })
        setTablePreviewError('Таблица пуста')
      } else {
        setTablePreviewError('Не удалось получить предпросмотр таблицы')
      }
    } catch (e) {
      setTablePreviewError('Ошибка при получении предпросмотра таблицы')
    } finally {
      setTablePreviewLoading(false)
    }
  }

  // --- Effect: fetch tables after connect ---
  React.useEffect(() => {
    if (dbConnected && authToken) {
      fetchDbTables(authToken)
    }
  }, [dbConnected, authToken])

  // --- Effect: fetch preview when table selected ---
  React.useEffect(() => {
    if (selectedDbTable && authToken) {
      fetchTablePreview(selectedDbTable)
    } else {
      setTablePreview(null)
      setTablePreviewError('')
    }
  }, [selectedDbTable, authToken])

  // --- Effect: show animation when tablePreview appears (fade-in always works) ---
  React.useEffect(() => {
    if (tablePreview && tablePreview.columns && tablePreview.rows && tablePreview.rows.length > 0 && !tablePreviewLoading && !tablePreviewError) {
      setPreviewVisible(false)
      requestAnimationFrame(() => setPreviewVisible(true))
    } else {
      setPreviewVisible(false)
    }
  }, [tablePreview, tablePreviewLoading, tablePreviewError])

  // --- UI handlers ---
  const handleDbInputChange = (setter) => (e) => {
    setter(e.target.value)
    setDbError('')
  }

  const handleContinueToConfig = async () => {
    // Сохраняем данные в контекст перед навигацией
    if (previewData && uploadedFile) {
      try {
        setFileLoading(true)
        // Загружаем полные данные для передачи в конфигурацию
        const fullData = await parseFile(uploadedFile)
        updateData(fullData, 'file', null)
      } catch (error) {
        console.error('Ошибка при загрузке полных данных:', error)
        setFileError('Ошибка при подготовке данных для конфигурации')
        setFileLoading(false)
        return
      } finally {
        setFileLoading(false)
      }
    } else if (tablePreview && selectedDbTable) {
      updateData(tablePreview, 'database', selectedDbTable)
    }
    navigate('/config')
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground mb-2">Загрузка данных</h1>
        <p className="text-muted-foreground">
          Загрузите данные временных рядов из файла или подключитесь к базе данных PostgreSQL
        </p>
      </div>

      <Tabs defaultValue="file" className="space-y-6">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="file" className="flex items-center space-x-2">
            <FileText size={16} />
            <span>Загрузка из файла</span>
          </TabsTrigger>
          <TabsTrigger value="database" className="flex items-center space-x-2">
            <Database size={16} />
            <span>Загрузка из БД</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="file" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Upload className="text-primary" size={20} />
                <span>Загрузка файла</span>
              </CardTitle>
              <CardDescription>
                Поддерживаются форматы: CSV, Excel (.xlsx, .xls)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div 
                className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                  isDragOver 
                    ? 'border-primary bg-primary/5' 
                    : 'border-border'
                }`}
                onDragEnter={handleDragEnter}
                onDragLeave={handleDragLeave}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
              >
                <Upload className={`mx-auto mb-4 ${isDragOver ? 'text-primary' : 'text-muted-foreground'}`} size={48} />
                <div className="space-y-2">
                  <p className="text-lg font-medium">
                    {isDragOver ? 'Отпустите файл для загрузки' : 'Перетащите файл сюда или выберите файл'}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Максимальный размер файла: 100 МБ
                  </p>
                </div>
                <Input
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={handleFileUpload}
                  disabled={fileLoading}
                  className="mt-4 max-w-xs mx-auto"
                />
                {fileLoading && (
                  <div className="mt-4 flex items-center justify-center space-x-2">
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary"></div>
                    <span className="text-sm text-muted-foreground">Обработка файла...</span>
                  </div>
                )}
              </div>

              {uploadedFile && !fileError && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <CheckCircle className="text-green-600" size={20} />
                      <div>
                        <p className="font-medium text-green-800">Файл успешно загружен</p>
                        <p className="text-sm text-green-600">
                          {uploadedFile.name} ({formatFileSize(uploadedFile.size)})
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleClearFile}
                      className="text-gray-600 hover:text-gray-800"
                    >
                      Очистить
                    </Button>
                  </div>
                </div>
              )}

              {fileError && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <div className="flex items-center space-x-2">
                    <AlertCircle className="text-red-600" size={20} />
                    <div>
                      <p className="font-medium text-red-800">Ошибка загрузки файла</p>
                      <p className="text-sm text-red-600">
                        {fileError}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Data Preview and Next Steps only for file tab */}
          {previewData && (
            <>
              <Card ref={previewRef}>
                <CardHeader>
                  <CardTitle className="flex items-center space-x-2">
                    <Eye className="text-primary" size={20} />
                    <span>Предпросмотр данных</span>
                  </CardTitle>
                  <CardDescription>
                    Первые 5 строк загруженных данных
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse border border-border">
                      <thead>
                        <tr className="bg-muted">
                          {previewData.columns.map((column, index) => (
                            <th key={index} className="border border-border p-2 text-left font-medium">
                              {column}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {previewData.rows.map((row, rowIndex) => (
                          <tr key={rowIndex} className="hover:bg-muted/50">
                            {row.map((cell, cellIndex) => (
                              <td key={cellIndex} className="border border-border p-2">
                                {cell}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="mt-4 flex justify-between items-center">
                    <p className="text-sm text-muted-foreground">
                      Показано {previewData.rows.length} из {previewData.totalRows || previewData.rows.length} строк
                    </p>
                    <Button variant="outline" className="flex items-center space-x-2">
                      <Download size={16} />
                      <span>Скачать образец</span>
                    </Button>
                  </div>
                </CardContent>
              </Card>
              <div className="flex justify-end space-x-4">
                <Button variant="outline">
                  Назад
                </Button>
                <Button 
                  className="bg-primary hover:bg-primary/90"
                  onClick={handleContinueToConfig}
                  disabled={fileLoading || !previewData}
                >
                  {fileLoading ? 'Подготовка данных...' : 'Продолжить к настройке модели'}
                </Button>
              </div>
            </>
          )}
        </TabsContent>

        <TabsContent value="database" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Database className="text-primary" size={20} />
                <span>Загрузка из БД</span>
              </CardTitle>
              <CardDescription>
                Введите учетные данные для загрузки данных из базы данных
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="username">Пользователь</Label>
                  <Input
                    id="username"
                    placeholder="postgres"
                    value={dbUsername}
                    onChange={handleDbInputChange(setDbUsername)}
                    disabled={dbConnected || dbConnecting}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Пароль</Label>
                  <Input
                    id="password"
                    type="password"
                    placeholder="••••••••"
                    value={dbPassword}
                    onChange={handleDbInputChange(setDbPassword)}
                    disabled={dbConnected || dbConnecting}
                  />
                </div>
              </div>
              {!dbConnected ? (
                <Button
                  onClick={handleDbConnect}
                  disabled={dbConnecting || dbConnected || !dbUsername || !dbPassword}
                  className="w-full"
                >
                  {dbConnecting ? 'Подключение...' : 'Подключиться'}
                </Button>
              ) : (
                <Button
                  onClick={handleDbDisconnect}
                  className="w-full bg-red-600 hover:bg-red-700"
                >
                  Отключиться
                </Button>
              )}
              {dbSuccess && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <div className="flex items-center space-x-2">
                    <CheckCircle className="text-green-600" size={20} />
                    <div>
                      <p className="font-medium text-green-800">Подключение успешно</p>
                      <p className="text-sm text-green-600">
                        Соединение с базой данных установлено
                      </p>
                    </div>
                  </div>
                </div>
              )}
              {dbError && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <div className="flex items-center space-x-2">
                    <AlertCircle className="text-red-600" size={20} />
                    <div>
                      <p className="font-medium text-red-800">Ошибка подключения</p>
                      <p className="text-sm text-red-600">
                        {dbError}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* --- DB Table Selection and Preview --- */}
          {dbConnected && (
            <Card className="bg-white border border-border rounded-lg">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Database className="text-primary" size={18} />
                  <span>Выбор таблицы из БД</span>
                </CardTitle>
                <CardDescription>
                  Выберите таблицу для загрузки данных
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {dbTablesLoading ? (
                  <div className="text-center text-muted-foreground py-4">Загрузка списка таблиц...</div>
                ) : dbTables.length === 0 ? (
                  <div className="text-center text-muted-foreground py-4">Нет доступных таблиц</div>
                ) : (
                  <div className="flex flex-col md:flex-row md:items-center gap-4">
                    <div className="w-full md:w-1/2">
                      <Label htmlFor="schema-select">Схема</Label>
                      <select
                        id="schema-select"
                        className="block w-full px-3 py-2 mt-1 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary text-base"
                        value={selectedSchema}
                        onChange={e => {
                          setSelectedSchema(e.target.value)
                          // При смене схемы сразу сбросить таблицу
                          const schemaObj = dbTables.find(s => s.schema === e.target.value)
                          if (schemaObj && schemaObj.tables.length > 0) {
                            setSelectedDbTable('')
                          } else {
                            setSelectedDbTable('')
                          }
                        }}
                      >
                        <option value="">Выберите схему</option>
                        {dbTables.map((s, idx) => (
                          <option key={s.schema + idx} value={s.schema}>{s.schema}</option>
                        ))}
                      </select>
                    </div>
                    <div className="w-full md:w-1/2">
                      <Label htmlFor="table-select">Таблица</Label>
                      <select
                        id="table-select"
                        className="block w-full px-3 py-2 mt-1 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary text-base"
                        value={selectedDbTable}
                        onChange={e => setSelectedDbTable(e.target.value)}
                        disabled={!selectedSchema || dbTables.length === 0}
                      >
                        <option value="">Выберите таблицу</option>
                        {(() => {
                          const schemaObj = dbTables.find(s => s.schema === selectedSchema)
                          return schemaObj ? schemaObj.tables.map(tbl => (
                            <option key={schemaObj.schema + '.' + tbl} value={schemaObj.schema + '.' + tbl}>{tbl}</option>
                          )) : null
                        })()}
                      </select>
                    </div>
                  </div>
                )}
                {/* Table preview */}
                {selectedDbTable && (
                  <div className="mt-6">
                    <div className="font-semibold mb-2">Предпросмотр таблицы</div>
                    {tablePreviewLoading ? (
                      <div className="text-center text-muted-foreground py-4">Загрузка...</div>
                    ) : tablePreviewError ? (
                      <div className="text-center text-red-600 py-4">{tablePreviewError}</div>
                    ) : tablePreview && tablePreview.columns && tablePreview.rows ? (
                      <div>
                        <div className={`transition-all duration-500 ease-out ${previewVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'} will-change-transform`}>
                          <table className="w-full border-collapse border border-border">
                            <thead>
                              <tr className="bg-muted">
                                {tablePreview.columns.map((col, idx) => (
                                  <th key={col + idx} className="border border-border p-2 text-left font-medium">{col}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {tablePreview.rows.map((row, rowIdx) => (
                                <tr key={rowIdx} className="hover:bg-muted/50">
                                  {row.map((cell, cellIdx) => (
                                    <td key={cellIdx} className="border border-border p-2">{cell}</td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        <div className="flex justify-end space-x-4 mt-4">
                          <Button variant="outline">
                            Назад
                          </Button>
                          <Button 
                            className="bg-primary hover:bg-primary/90"
                            onClick={handleContinueToConfig}
                          >
                            Продолжить к настройке модели
                          </Button>
                        </div>
                      </div>
                    ) : null}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

