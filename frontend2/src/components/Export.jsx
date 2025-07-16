import { useState, useEffect } from 'react'
import { useData } from '../contexts/DataContext'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.jsx'
import { CheckCircle, Database, Settings, ChevronDown, ChevronUp, Download, Clock } from 'lucide-react'
import { API_BASE_URL } from '../apiConfig.js'
import * as XLSX from 'xlsx';

export default function Export() {
  const { sessionId, authToken, predictionRows, setPredictionRows, trainingStatus, setAuthToken, dbConnected, setDbConnected, dbTables, setDbTables, dbTablesLoading, setDbTablesLoading, dbError, setDbError } = useData();
  const [localUsername, setLocalUsername] = useState('');
  const [localPassword, setLocalPassword] = useState('');
  
  const [exportConfig, setExportConfig] = useState({
    format: 'excel'
  })

  const [exportStatus, setExportStatus] = useState('idle') // idle, preparing, ready, error

  const [dbPanelOpen] = useState(true); // Панель всегда открыта
  const [dbConnecting, setDbConnecting] = useState(false);
  const [dbSaveMode, setDbSaveMode] = useState('existing'); // 'new' or 'existing'
  const [dbSaveLoading, setDbSaveLoading] = useState(false);
  const [dbSaveSuccess, setDbSaveSuccess] = useState(false);
  const [selectedDbSchema, setSelectedDbSchema] = useState('');
  const [selectedDbTable, setSelectedDbTable] = useState('');
  const [newTableName, setNewTableName] = useState('');
  const [selectedPrimaryKeys, setSelectedPrimaryKeys] = useState([]);
  const [dbSaveError, setDbSaveError] = useState('');
  const [dbSchemas, setDbSchemas] = useState([])
  const [dbTablesBySchema, setDbTablesBySchema] = useState({})

  const exportFormats = [
    { value: 'excel', label: 'Excel (.xlsx)', icon: Download, description: 'Многолистовой Excel файл с данными' },
    { value: 'csv', label: 'CSV (.csv)', icon: Download, description: 'Простой CSV файл для импорта в другие системы' }
  ]

  const handleConfigChange = (field, value) => {
    setExportConfig(prev => ({ ...prev, [field]: value }))
  }

  const handleDbConfigChange = (field, value) => {
    setDbConfig(prev => ({ ...prev, [field]: value }))
  }

  const handleExport = async () => {
    if (!sessionId) {
      console.error('Нет активной сессии для скачивания')
      setExportStatus('error')
      setTimeout(() => setExportStatus('idle'), 3000)
      return
    }

    setExportStatus('preparing')
    
    try {
      let url
      let filename
      
      if (exportConfig.format === 'excel') {
        url = `${API_BASE_URL}/download_prediction/${sessionId}`
        filename = `prediction_${sessionId}.xlsx`
      } else if (exportConfig.format === 'csv') {
        url = `${API_BASE_URL}/download_prediction_csv/${sessionId}`
        filename = `prediction_${sessionId}.csv`
      }
      
      const response = await fetch(url)
      
      if (!response.ok) {
        throw new Error(`Ошибка скачивания: ${response.status}`)
      }
      
      const blob = await response.blob()
      const link = document.createElement('a')
      link.href = window.URL.createObjectURL(blob)
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      
      setExportStatus('ready')
      setTimeout(() => setExportStatus('idle'), 4000)
      
    } catch (error) {
      console.error('Ошибка при скачивании файла:', error)
      setExportStatus('error')
      setTimeout(() => setExportStatus('idle'), 3000)
    }
  }

  // --- DB Save Panel State ---
  const handleDbConnect = async () => {
    setDbError('');
    setDbConnecting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: localUsername, password: localPassword })
      });
      if (!response.ok) {
        setDbError('Неверный логин или пароль');
        setDbConnecting(false);
        return;
      }
      const result = await response.json();
      if (result.success && result.access_token) {
        setDbConnected(true);
        setDbError('');
        setLocalUsername('');
        setLocalPassword('');
        setAuthToken(result.access_token); // <--- fix: save token globally
        // fetch tables
        setDbTablesLoading(true);
        const tablesResp = await fetch(`${API_BASE_URL}/get-tables`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${result.access_token}`
          },
        });
        const tablesResult = await tablesResp.json();
        if (tablesResult.success) {
          setDbSchemas(Object.keys(tablesResult.tables));
          setDbTablesBySchema(tablesResult.tables);
          setSelectedDbSchema(Object.keys(tablesResult.tables)[0] || '');
        } else {
          setDbSchemas([]);
          setDbTablesBySchema({});
        }
        setDbTablesLoading(false);
      } else {
        setDbError('Не удалось подключиться к базе данных');
      }
    } catch (e) {
      setDbError('Ошибка подключения: ' + (e instanceof Error ? e.message : e));
    } finally {
      setDbConnecting(false);
    }
  };

  const handleDbDisconnect = () => {
    setDbConnected(false);
    setDbTables([]);
    setDbSchemas([]);
    setDbTablesBySchema({});
    setSelectedDbSchema('');
    setSelectedDbTable('');
    setNewTableName('');
    setSelectedPrimaryKeys([]);
    setDbSaveMode('new');
    setDbError('');
  };

  // Fetch schemas/tables when panel opens
  useEffect(() => {
    if (!authToken) return;
    setDbTablesLoading(true);
    const fetchDbTables = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/get-tables`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}`
          },
        });
        const result = await response.json();
        if (result.success) {
          setDbSchemas(Object.keys(result.tables));
          setDbTablesBySchema(result.tables);
          setSelectedDbSchema(Object.keys(result.tables)[0] || '');
        } else {
          setDbSchemas([]);
          setDbTablesBySchema({});
        }
      } catch {
        setDbSchemas([]);
        setDbTablesBySchema({});
      } finally {
        setDbTablesLoading(false);
      }
    };
    fetchDbTables();
  }, [authToken]);

  const filteredDbTables = selectedDbSchema ? (dbTablesBySchema[selectedDbSchema] || []) : [];

  const handleSaveToDb = async () => {
    setDbSaveLoading(true);
    setDbSaveError('');
    if (!sessionId) {
      setDbSaveError('Нет активной сессии.');
      setDbSaveLoading(false);
      return;
    }
    let schema = selectedDbSchema;
    let tableName = dbSaveMode === 'new' ? newTableName.trim() : selectedDbTable;
    if (!schema) {
      setDbSaveError('Выберите схему.');
      setDbSaveLoading(false);
      return;
    }
    if (dbSaveMode === 'new' && !tableName) {
      setDbSaveError('Введите название новой таблицы.');
      setDbSaveLoading(false);
      return;
    }
    if (dbSaveMode === 'existing' && !tableName) {
      setDbSaveError('Выберите таблицу.');
      setDbSaveLoading(false);
      return;
    }
    try {
      // 1. Скачиваем prediction файл с backend
      const fileResp = await fetch(`${API_BASE_URL}/download_prediction/${sessionId}`);
      if (!fileResp.ok) {
        setDbSaveError('Ошибка скачивания файла прогноза');
        setDbSaveLoading(false);
        return;
      }
      const blob = await fileResp.blob();
      const file = new File([blob], `prediction_${sessionId}.xlsx`, { type: blob.type });

      if (dbSaveMode === 'new') {
        // 2. Создание новой таблицы: отправляем файл и primary_keys через upload-excel-to-db
        const formData = new FormData();
        formData.append('file', file);
        formData.append('schema', schema);
        formData.append('table_name', tableName);
        formData.append('primary_keys', JSON.stringify(selectedPrimaryKeys));
        formData.append('dbSaveMode', 'new');
        const response = await fetch(`${API_BASE_URL}/upload-excel-to-db`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${authToken}`
          },
          body: formData
        });
        const result = await response.json();
        if (result.success) {
          setDbSaveSuccess(true);
          setTimeout(() => setDbSaveSuccess(false), 2000);
          setDbPanelOpen(false);
        } else {
          setDbSaveError(result.detail || 'Ошибка при сохранении в БД.');
        }
      } else {
        // 3. Сохранение в существующую таблицу: используем save-prediction-to-db
        const response = await fetch(`${API_BASE_URL}/save-prediction-to-db`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}`
          },
          body: JSON.stringify({
            schema,
            session_id: sessionId,
            table_name: tableName,
            create_new: false
          })
        });
        const result = await response.json();
        if (result.success) {
          setDbSaveSuccess(true);
          setTimeout(() => setDbSaveSuccess(false), 2000);
          setDbPanelOpen(false);
        } else {
          setDbSaveError(result.detail || 'Ошибка при сохранении в БД.');
        }
      }
    } catch (e) {
      setDbSaveError('Ошибка: ' + (e instanceof Error ? e.message : e));
    } finally {
      setDbSaveLoading(false);
    }
  };

  const handleDatabaseSave = async () => {
    setExportStatus('preparing')
    
    // Simulate database save
    setTimeout(() => {
      setExportStatus('ready')
      setTimeout(() => {
        setExportStatus('idle')
      }, 4000)
    }, 2000)
  }

  const getStatusMessage = () => {
    switch (exportStatus) {
      case 'preparing':
        return 'Подготовка экспорта...'
      case 'ready':
        return 'Экспорт завершен успешно!'
      case 'error':
        return 'Ошибка при экспорте'
      default:
        return ''
    }
  }

  // Проверяем, есть ли успешно завершенное обучение
  const canDownload = () => {
    return sessionId && 
           trainingStatus && 
           ['completed', 'complete'].includes(trainingStatus.status)
  }

  // Удалить useEffect для predictionRows (автоматический парсинг после обучения)

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground mb-2">Экспорт результатов</h1>
        <p className="text-muted-foreground">
          Сохраните результаты прогнозирования в различных форматах или экспортируйте в базу данных
        </p>
      </div>

      <div className="space-y-6">
        {/* Export Status */}
        {exportStatus !== 'idle' && (
          <Card className={`${exportStatus === 'ready' ? 'bg-green-50 border-green-200' : 'bg-blue-50 border-blue-200'}`}>
            <CardContent className="py-6">
              <div className="flex items-center space-x-3">
                {exportStatus === 'preparing' && <Clock className="text-blue-600 animate-spin" size={20} />}
                {exportStatus === 'ready' && <CheckCircle className="text-green-600" size={20} />}
                <span className={`font-medium ${exportStatus === 'ready' ? 'text-green-800' : 'text-blue-800'}`}>
                  {getStatusMessage()}
                </span>
              </div>
            </CardContent>
          </Card>
        )}

        <Tabs defaultValue="download" className="space-y-6">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="download">Скачивание файлов</TabsTrigger>
            <TabsTrigger value="database">Сохранение в БД</TabsTrigger>
          </TabsList>

          <TabsContent value="download" className="space-y-6">
            {/* Format Selection */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Download className="text-primary" size={20} />
                  <span>Выбор формата экспорта</span>
                </CardTitle>
                <CardDescription>
                  Выберите формат файла для экспорта результатов
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {exportFormats.map(format => {
                    const IconComponent = format.icon
                    return (
                      <div 
                        key={format.value}
                        className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                          exportConfig.format === format.value 
                            ? 'border-primary bg-primary/5' 
                            : 'border-gray-200 hover:border-gray-300'
                        }`}
                        onClick={() => handleConfigChange('format', format.value)}
                      >
                        <div className="flex items-start space-x-3">
                          <IconComponent className="text-primary mt-1" size={20} />
                          <div className="flex-1">
                            <div className="font-medium">{format.label}</div>
                            <p className="text-sm text-muted-foreground mt-1">
                              {format.description}
                            </p>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </CardContent>
            </Card>

            {/* Предупреждение если нет завершенного обучения */}
            {!canDownload() && (
              <Card className="border-orange-200 bg-orange-50">
                <CardContent className="pt-6">
                  <div className="flex items-center space-x-2 text-orange-800">
                    <Clock size={20} />
                    <div>
                      <p className="font-medium">Результаты недоступны</p>
                      <p className="text-sm text-orange-600">
                        {!sessionId ? 'Нет активной сессии обучения.' : 
                         !trainingStatus ? 'Статус обучения неизвестен.' :
                         'Дождитесь завершения обучения модели.'}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Export Actions */}
            <div className="flex justify-between">
              <Button variant="outline">
                Назад к анализу
              </Button>
              <Button 
                onClick={handleExport}
                disabled={exportStatus === 'preparing' || !canDownload()}
                className="bg-primary hover:bg-primary/90 flex items-center space-x-2"
              >
                <Download size={16} />
                <span>Скачать результаты</span>
              </Button>
            </div>
          </TabsContent>

          <TabsContent value="database" className="space-y-6">
            {dbSaveSuccess && (
              <Card className="bg-green-50 border-green-200">
                <CardContent className="py-4 flex items-center space-x-2">
                  <CheckCircle className="text-green-600" size={20} />
                  <span className="text-green-800 font-medium">Результаты успешно сохранены в базу данных!</span>
                </CardContent>
              </Card>
            )}
            <Card className="mt-0">
              <CardHeader>
                <div className="flex items-center justify-between w-full">
                  <div className="flex items-center space-x-2">
                    <Database size={20} className="text-blue-600" />
                    <CardTitle className="flex items-center space-x-2">
                      <span>Сохранение результатов в БД</span>
                    </CardTitle>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setDbPanelOpen(!dbPanelOpen)}
                      className="p-1"
                    >
                      {dbPanelOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              {dbPanelOpen && (
                <CardContent className="p-3">
                  {dbError && (
                    <div className="text-red-600 text-sm bg-red-50 p-2 rounded-md mb-2">{dbError}</div>
                  )}
                  <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="space-y-2">
                      <Label htmlFor="db-username">Имя пользователя</Label>
                      <Input
                        id="db-username"
                        type="text"
                        placeholder="Введите имя пользователя"
                        value={localUsername}
                        onChange={e => setLocalUsername(e.target.value)}
                        disabled={dbConnected || dbConnecting}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="db-password">Пароль</Label>
                      <Input
                        id="db-password"
                        type="password"
                        placeholder="Введите пароль"
                        value={localPassword}
                        onChange={e => setLocalPassword(e.target.value)}
                        disabled={dbConnected || dbConnecting}
                      />
                    </div>
                    <div className="col-span-2">
                      {!dbConnected ? (
                        <Button
                          onClick={handleDbConnect}
                          disabled={dbConnecting || !localUsername || !localPassword}
                          className="w-full"
                        >
                          {dbConnecting ? (
                            <>
                              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                              Подключение...
                            </>
                          ) : (
                            "Подключиться к БД"
                          )}
                        </Button>
                      ) : (
                        <Button
                          onClick={handleDbDisconnect}
                          className="w-full mb-4"
                        >
                          Отключиться
                        </Button>
                      )}
                    </div>
                  </div>
                  {dbConnected && (
                    dbTablesLoading ? (
                      <div className="flex items-center justify-center py-6">
                        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600 mr-2"></div>
                        <span className="text-sm text-muted-foreground">Загрузка таблиц...</span>
                      </div>
                    ) : dbSchemas.length > 0 ? (
                        <div className="space-y-3 border-t pt-3">
                          <div className="grid grid-cols-2 gap-3">
                            <button
                              onClick={() => setDbSaveMode('existing')}
                              className={`p-3 rounded-lg border-2 transition-all ${
                                dbSaveMode === 'existing' 
                                  ? 'border-primary bg-primary/5 text-primary' 
                                  : 'border-gray-200 hover:border-gray-300'
                              }`}
                            >
                              <div className="flex flex-col items-center space-y-2">
                                <Database size={20} />
                                <span className="font-medium text-sm">Существующая таблица</span>
                                <span className="text-xs text-center">Сохранить в уже созданную таблицу</span>
                              </div>
                            </button>
                            <button
                              onClick={() => setDbSaveMode('new')}
                              className={`p-3 rounded-lg border-2 transition-all ${
                                dbSaveMode === 'new' 
                                  ? 'border-primary bg-primary/5 text-primary' 
                                  : 'border-gray-200 hover:border-gray-300'
                              }`}
                            >
                              <div className="flex flex-col items-center space-y-2">
                                <Settings size={20} />
                                <span className="font-medium text-sm">Создать таблицу</span>
                                <span className="text-xs text-center">Создать новую таблицу для результатов</span>
                              </div>
                            </button>
                          </div>
                          {dbSaveMode === 'existing' ? (
                            <div className="flex flex-col md:flex-row md:items-center gap-3">
                              <div className="w-full md:w-1/2">
                                <Label htmlFor="schema-select">Схема</Label>
                                <select
                                  id="schema-select"
                                  className="block w-full px-3 py-2 mt-1 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary text-base"
                                  value={selectedDbSchema}
                                  onChange={e => setSelectedDbSchema(e.target.value)}
                                >
                                  <option value="">Выберите схему</option>
                                  {dbSchemas.map((s, idx) => (
                                    <option key={s + idx} value={s}>{s}</option>
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
                                  disabled={!selectedDbSchema || filteredDbTables.length === 0}
                                >
                                  <option value="">Выберите таблицу</option>
                                  {filteredDbTables.map(tbl => (
                                    <option key={tbl} value={tbl}>{tbl}</option>
                                  ))}
                                </select>
                              </div>
                            </div>
                          ) : (
                            <div className="flex flex-col md:flex-row md:items-center gap-3">
                              <div className="w-full md:w-1/2">
                                <Label htmlFor="new-schema-select">Схема</Label>
                                <select
                                  id="new-schema-select"
                                  className="block w-full px-3 py-2 mt-1 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary text-base"
                                  value={selectedDbSchema}
                                  onChange={e => setSelectedDbSchema(e.target.value)}
                                >
                                  <option value="">Выберите схему</option>
                                  {dbSchemas.map((s, idx) => (
                                    <option key={s + idx} value={s}>{s}</option>
                                  ))}
                                </select>
                              </div>
                              <div className="w-full md:w-1/2">
                                <Label htmlFor="new-table-name">Название новой таблицы</Label>
                                <Input
                                  id="new-table-name"
                                  type="text"
                                  placeholder="Введите название таблицы"
                                  value={newTableName}
                                  onChange={e => setNewTableName(e.target.value)}
                                  className="block w-full px-3 py-2 mt-1 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary text-base"
                                />
                              </div>
                            </div>
                          )}
                          {dbSaveMode === 'new' && (
                            <div className="w-full md:w-1/2 mt-3">
                              <Label className="mb-1 block" htmlFor="primary-keys-select">Выберите первичные колонки</Label>
                              <div className="flex flex-wrap gap-2">
                                {predictionRows && predictionRows.length > 0
                                  ? Object.keys(predictionRows[0])
                                      .filter(col => !/^0\.[1-9]$/.test(col))
                                      .map((col) => (
                                        <label key={col} className="flex items-center space-x-1 text-sm border rounded px-2 py-1 bg-gray-50">
                                          <input
                                            type="checkbox"
                                            checked={selectedPrimaryKeys.includes(col)}
                                            onChange={e => {
                                              if (e.target.checked) {
                                                setSelectedPrimaryKeys([...selectedPrimaryKeys, col])
                                              } else {
                                                setSelectedPrimaryKeys(selectedPrimaryKeys.filter(pk => pk !== col))
                                              }
                                            }}
                                          />
                                          <span>{col}</span>
                                        </label>
                                      ))
                                  : (
                                    <span className="text-xs text-muted-foreground">Нет доступных колонок в результатах</span>
                                  )}
                              </div>
                              <p className="text-xs text-muted-foreground mt-1">Выберите одну или несколько колонок, которые будут использоваться как первичные ключи для новой таблицы (опционально)</p>
                            </div>
                          )}
                          {((dbSaveMode === 'existing' && selectedDbTable) || (dbSaveMode === 'new' && selectedDbSchema && newTableName)) && (
                            <div className="space-y-2">
                              <p className="text-sm text-muted-foreground">
                                {dbSaveMode === 'existing' 
                                  ? `Результаты будут сохранены в таблицу: ${selectedDbTable}`
                                  : `Будет создана новая таблица: ${selectedDbSchema}.${newTableName}`
                                }
                              </p>
                              <Button
                                onClick={handleSaveToDb}
                                disabled={
                                  dbSaveLoading ||
                                  (dbSaveMode === 'existing' && !selectedDbTable) || 
                                  (dbSaveMode === 'new' && (!selectedDbSchema || !newTableName))
                                }
                                className="w-full"
                              >
                                {dbSaveLoading ? 'Сохранение...' : 'Сохранить в БД'}
                              </Button>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="text-center py-3 text-muted-foreground">
                          <Database size={20} className="mx-auto mb-2 opacity-50" />
                          <p className="text-sm">Таблицы не найдены</p>
                        </div>
                      )
                    )}
                </CardContent>
              )}
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}

