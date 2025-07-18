import React, { useState, useEffect, useRef } from 'react';
import { useData } from '../../contexts/DataContext';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card.jsx';
import { Button } from '@/components/ui/button.jsx';
import { Input } from '@/components/ui/input.jsx';
import { Label } from '@/components/ui/label.jsx';
import { Switch } from '@/components/ui/switch.jsx';
import { Toggle } from '@/components/ui/toggle.jsx';
import { CheckCircle, Database, Settings, ChevronDown, ChevronUp } from 'lucide-react';
import { API_BASE_URL } from '../../apiConfig.js';

export default function DbAutoSavePanel(props) {
  const { dbConnected, setDbConnected, setAuthToken, dbTables, setDbTables, dbTablesLoading, dbError, setDbError, authToken, ensureTablesLoaded, refreshTables } = useData();
  const [localUsername, setLocalUsername] = useState('');
  const [localPassword, setLocalPassword] = useState('');
  const [autoSaveMenuOpen, setAutoSaveMenuOpen] = useState(false); // по умолчанию скрыто
  const contentRef = useRef(null);
  const [contentHeight, setContentHeight] = useState(0);
  const {
    selectedSchema,
    setSelectedSchema,
    selectedTable,
    setSelectedTable,
    saveMode,
    setSaveMode,
    newTableName,
    setNewTableName,
    autoSaveSettings,
    handleDbConnect,
    handleDbInputChange,
    handleSchemaChange,
    handleTableChange,
    handleAutoSaveSetup,
    fileColumns,
    selectedPrimaryKeys,
    setSelectedPrimaryKeys,
  } = props;

  // Автоматическая загрузка таблиц после подключения к БД
  useEffect(() => {
    if (authToken && dbConnected && dbTables.length === 0) {
      ensureTablesLoaded();
    }
  }, [authToken, dbConnected, dbTables.length, ensureTablesLoaded]);

  useEffect(() => {
    if (autoSaveMenuOpen && contentRef.current) {
      setContentHeight(contentRef.current.scrollHeight);
    } else {
      setContentHeight(0);
    }
  }, [autoSaveMenuOpen, dbConnected, dbTablesLoading, dbTables.length]);

  return (
    <Card className="mt-0">
      <CardHeader>
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center space-x-2">
            <Database size={20} className="text-blue-600" />
            <CardTitle
              className="flex items-center space-x-2 cursor-pointer select-none"
              onClick={() => setAutoSaveMenuOpen((open) => !open)}
            >
              <span>Автосохранение результатов в БД после прогноза</span>
            </CardTitle>
          </div>
          <div className="flex items-center space-x-2">
            <Switch
              checked={props.autoSaveEnabled}
              onCheckedChange={(checked) => {
                if (!checked) {
                  props.setAutoSaveEnabled(false);
                  setSelectedSchema('');
                  setSelectedTable('');
                  setNewTableName('');
                  setSaveMode('existing');
                  setAutoSaveSettings(null);
                  setSaveTableName('');
                }
              }}
              className="data-[state=checked]:bg-blue-600"
            />
            <button
              type="button"
              className="p-1"
              style={{ width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
              onClick={() => setAutoSaveMenuOpen((open) => !open)}
              aria-label="Свернуть/развернуть"
            >
              <span style={{ display: 'inline-block', width: 16, height: 16 }}>
                {autoSaveMenuOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </span>
            </button>
          </div>
        </div>
        <CardDescription
          className="cursor-pointer select-none"
          onClick={() => setAutoSaveMenuOpen((open) => !open)}
        >
          Автоматически сохраняйте результаты прогноза в выбранную базу данных после завершения обучения
        </CardDescription>
      </CardHeader>
      {(props.autoSaveEnabled && autoSaveSettings) || autoSaveMenuOpen ? (
        <div
          style={{
            width: '100%',
            boxSizing: 'border-box',
            display: 'block',
          }}
        >
          <CardContent className="p-3">
            {props.autoSaveEnabled && autoSaveSettings && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-3 mb-3">
                <div className="flex items-center space-x-2">
                  <CheckCircle className="text-green-600" size={16} />
                  <div className="text-sm">
                    <p className="font-medium text-green-800">Автосохранение настроено</p>
                    <p className="text-green-600">
                      {autoSaveSettings.mode === 'existing' 
                        ? `Результаты будут сохранены в таблицу: ${autoSaveSettings.selectedTable}`
                        : `Результаты будут сохранены в новую таблицу: ${autoSaveSettings.selectedSchema}.${autoSaveSettings.newTableName}`
                      }
                    </p>
                  </div>
                </div>
              </div>
            )}
            {autoSaveMenuOpen && (
              <div className="space-y-3 border-t pt-3">
                <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <Label htmlFor="db-username">Имя пользователя</Label>
                    <Input
                      id="db-username"
                      type="text"
                      placeholder="Введите имя пользователя"
                      value={localUsername}
                      onChange={e => setLocalUsername(e.target.value)}
                      disabled={props.dbConnecting || dbConnected}
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
                      disabled={props.dbConnecting || dbConnected}
                    />
                  </div>
                </div>

                {dbError && (
                  <div className="text-red-600 text-sm bg-red-50 p-2 rounded-md">
                    {dbError}
                  </div>
                )}

                {!dbConnected ? (
                  <Button
                    onClick={async () => {
                      setDbError('');
                      props.setDbConnecting && props.setDbConnecting(true);
                      try {
                        const response = await fetch(`${API_BASE_URL}/login`, {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ username: localUsername, password: localPassword })
                        });
                        if (!response.ok) {
                          setDbError('Неверный логин или пароль');
                          props.setDbConnecting && props.setDbConnecting(false);
                          return;
                        }
                        const result = await response.json();
                        if (result.success && result.access_token) {
                          setAuthToken(result.access_token);
                          setDbConnected(true);
                          setDbError('');
                          setLocalUsername('');
                          setLocalPassword('');
                        } else {
                          setDbError('Не удалось подключиться к базе данных');
                          setDbConnected(false);
                          setAuthToken(null);
                        }
                      } catch (e) {
                        setDbError('Ошибка сети: ' + (e.message || e));
                        setDbConnected(false);
                        setAuthToken(null);
                      } finally {
                        props.setDbConnecting && props.setDbConnecting(false);
                      }
                    }}
                    disabled={props.dbConnecting || !localUsername || !localPassword}
                    className="w-full"
                  >
                    {props.dbConnecting ? (
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
                    onClick={() => {
                      setAuthToken(null)
                      setDbConnected(false)
                      setDbTables([])
                      setSelectedSchema('')
                      setSelectedTable('')
                      setDbError('')
                    }}
                    className="w-full"
                  >
                    Отключиться
                  </Button>
                )}

                {/* Горизонтальная линия теперь внутри анимируемого блока */}
                {dbConnected && (
                  <div className="my-4 border-t border-gray-200" />
                )}

                {dbConnected && (
                  <div className="space-y-3">
                    {dbTablesLoading ? (
                      <div className="flex items-center justify-center py-6">
                        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600 mr-2"></div>
                        <span className="text-sm text-muted-foreground">Загрузка таблиц...</span>
                      </div>
                    ) : dbTables.length > 0 ? (
                      <div className="space-y-3">
                        {/* Выбор режима сохранения */}
                        <div className="grid grid-cols-2 gap-3">
                          <button
                            onClick={() => setSaveMode('existing')}
                            className={`p-3 rounded-lg border-2 transition-all ${
                              saveMode === 'existing' 
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
                            onClick={() => setSaveMode('create')}
                            className={`p-3 rounded-lg border-2 transition-all ${
                              saveMode === 'create' 
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

                        {saveMode === 'existing' ? (
                          <div className="flex flex-col md:flex-row md:items-center gap-3">
                            <div className="w-full md:w-1/2">
                              <Label htmlFor="schema-select">Схема</Label>
                              <select
                                id="schema-select"
                                className="block w-full px-3 py-2 mt-1 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary text-base"
                                value={selectedSchema}
                                onChange={e => handleSchemaChange(e.target.value)}
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
                                value={selectedTable}
                                onChange={e => handleTableChange(e.target.value)}
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
                        ) : (
                          <div className="flex flex-col md:flex-row md:items-center gap-3">
                            <div className="w-full md:w-1/2">
                              <Label htmlFor="new-schema-select">Схема</Label>
                              <select
                                id="new-schema-select"
                                className="block w-full px-3 py-2 mt-1 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary text-base"
                                value={selectedSchema}
                                onChange={e => setSelectedSchema(e.target.value)}
                              >
                                <option value="">Выберите схему</option>
                                {dbTables.map((s, idx) => (
                                  <option key={s.schema + idx} value={s.schema}>{s.schema}</option>
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
                                onChange={(e) => setNewTableName(e.target.value)}
                                className="block w-full px-3 py-2 mt-1 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary text-base"
                              />
                            </div>
                          </div>
                        )}

                        {saveMode === 'create' && (
                          <div className="w-full md:w-1/2 mt-3">
                            <Label className="mb-1 block" htmlFor="primary-keys-select">Выберите первичные колонки</Label>
                            <div className="flex flex-wrap gap-2">
                              {fileColumns.length > 0
                                ? fileColumns.map((col) => (
                                    <label key={col} className="flex items-center space-x-1 text-sm border rounded px-2 py-1 bg-gray-50">
                                      <input
                                        type="checkbox"
                                        checked={Array.isArray(selectedPrimaryKeys) && selectedPrimaryKeys.includes(col)}
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
                                  <span className="text-xs text-muted-foreground">Нет доступных колонок в файле</span>
                                )}
                            </div>
                            <p className="text-xs text-muted-foreground mt-1">Выберите одну или несколько колонок, которые будут использоваться как первичные ключи для новой таблицы</p>
                          </div>
                        )}

                        <div className="space-y-2">
                          <p className="text-sm text-muted-foreground">
                            {saveMode === 'existing' 
                              ? (selectedTable ? `Результаты будут сохранены в таблицу: ${selectedTable}` : 'Выберите схему и таблицу для сохранения')
                              : (selectedSchema && newTableName ? `Будет создана новая таблица: ${selectedSchema}.${newTableName}` : 'Выберите схему и имя новой таблицы')
                            }
                          </p>
                          <Button
                            onClick={async () => {
                              const saveSettings = saveMode === 'existing' 
                                ? { mode: 'existing', selectedSchema, selectedTable }
                                : { mode: 'create', selectedSchema, newTableName };
                              const success = await handleAutoSaveSetup(saveSettings);
                              if (success) {
                                props.setAutoSaveEnabled(true);
                                setAutoSaveMenuOpen(false);
                                refreshTables(); // обновить глобальный список таблиц
                              }
                            }}
                            disabled={saveMode === 'existing' ? !selectedTable : (!selectedSchema || !newTableName)}
                            className="w-full"
                          >
                            Сохранить изменения
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-3 text-muted-foreground">
                        <Database size={20} className="mx-auto mb-2 opacity-50" />
                        <p className="text-sm">Таблицы не найдены</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </div>
      ) : null}
    </Card>
  );
}