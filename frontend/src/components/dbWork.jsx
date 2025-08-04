import { useState, useRef, useEffect } from 'react';
import { useData } from '../contexts/DataContext';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card.jsx';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.jsx';
import { Download, Upload, Database, Eye, CheckCircle, AlertCircle, Settings, ChevronDown, ChevronUp } from 'lucide-react';
import { validateFileSize, validateFileType, formatFileSize } from '../utils/fileParser.js';
import { Button } from '@/components/ui/button.jsx';
import { Input } from '@/components/ui/input.jsx';
import { API_BASE_URL } from '../apiConfig.js';

// Persisted state lives across route changes (module scope) but resets on page refresh
let persistedDbWorkState = null;

export default function DbWork() {
   // --- Initial state builder ---
  const ps = persistedDbWorkState || {};
  // --- Global DB connection via DataContext ---
  const {
    authToken,
    setAuthToken,
    dbConnected,
    setDbConnected,
    dbTables,
    setDbTables,
    dbTablesLoading,
    setDbTablesLoading,
    dbError,
    setDbError,
    ensureTablesLoaded,
    refreshTables
  } = useData();

  // Локальные состояния (остается только UI/файл)
  const [activeTab, setActiveTab] = useState(ps.activeTab || 'download');
  // Алиасы для использования в существующем коде без масштабного рефакторинга
  const localDbConnected = dbConnected;
  const setLocalDbConnected = setDbConnected;
  const localAuthToken = authToken;
  const setLocalAuthToken = setAuthToken;
  const localDbTables = dbTables;
  const setLocalDbTables = setDbTables;
  const localDbTablesLoading = dbTablesLoading;
  const setLocalDbTablesLoading = setDbTablesLoading;
  const localDbError = dbError;
  const setLocalDbError = setDbError;
  const [localSelectedDbTable, setLocalSelectedDbTable] = useState(ps.localSelectedDbTable || '');
  const [localSelectedSchema, setLocalSelectedSchema] = useState(ps.localSelectedSchema || '');
  const [localUsername, setLocalUsername] = useState('');
  const [localPassword, setLocalPassword] = useState('');
  const [localDbConnecting, setLocalDbConnecting] = useState(false);
  const [localDbSuccess, setLocalDbSuccess] = useState(false);
  const [downloadStatus, setDownloadStatus] = useState('idle');
  const [previewRows, setPreviewRows] = useState([]);
  const [previewColumns, setPreviewColumns] = useState([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [localTablePreviewLoading, setLocalTablePreviewLoading] = useState(false);
  const [localTablePreviewError, setLocalTablePreviewError] = useState('');
  const [localPreviewVisible, setLocalPreviewVisible] = useState(false);
  const [localTableLoadingFromDb, setLocalTableLoadingFromDb] = useState(false);
  const previewRef = useRef(null);

  // --- Upload to DB states ---
  const [uploadFile, setUploadFile] = useState(ps.uploadFile || null);
  const [uploadFileLoading, setUploadFileLoading] = useState(false);
  const [uploadFileError, setUploadFileError] = useState('');
  const [uploadColumns, setUploadColumns] = useState(ps.uploadColumns || []);
  const [uploadMode, setUploadMode] = useState(ps.uploadMode || 'existing'); // default existing
  const [uploadSchema, setUploadSchema] = useState(ps.uploadSchema || '');
  const [uploadExistingTable, setUploadExistingTable] = useState(ps.uploadExistingTable || '');
  const [uploadNewTableName, setUploadNewTableName] = useState(ps.uploadNewTableName || '');
  const [uploadPK, setUploadPK] = useState(ps.uploadPK || []);
  const [uploadStatus, setUploadStatus] = useState('idle'); // not persisted to avoid stale
  const uploadPreviewRef = useRef(null);
  const [uploadPreviewVisible, setUploadPreviewVisible] = useState(false);
  // Ref для сообщения об успехе
  const uploadSuccessRef = useRef(null);
  // Drag & Drop state for upload
  const [isUploadDragOver, setIsUploadDragOver] = useState(false);
  // Toggle for credentials visibility
  const [credOpen, setCredOpen] = useState(!localDbConnected);

  useEffect(()=>{
    setCredOpen(!localDbConnected);
  },[localDbConnected]);

  // Подключение к БД
  const handleDbConnect = async () => {
    setLocalDbError('');
    setLocalDbSuccess(false);
    setLocalDbConnecting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: localUsername, password: localPassword })
      });
      if (!response.ok) {
        setLocalDbError('Ошибка подключения');
        setLocalDbConnected(false);
        setLocalAuthToken('');
        setLocalDbConnecting(false);
        return;
      }
      const result = await response.json();
      if (result.success && result.access_token) {
        setLocalAuthToken(result.access_token);
        setLocalDbConnected(true);
        setLocalDbSuccess(true);
        setLocalDbError('');
        setLocalUsername('');
        setLocalPassword('');
        setTimeout(() => setLocalDbSuccess(false), 1800);
        setCredOpen(false); // collapse credentials
        // После успешного логина: больше не вызываем ensureTablesLoaded здесь
      } else {
        setLocalDbError('Не удалось подключиться к базе данных');
        setLocalDbConnected(false);
        setLocalAuthToken('');
      }
    } catch (e) {
      setLocalDbError(`Ошибка сети: ${e.message}`);
      setLocalDbConnected(false);
      setLocalAuthToken('');
    } finally {
      setLocalDbConnecting(false);
    }
  };

  // Отключение от БД
  const handleDbDisconnect = () => {
    setLocalAuthToken('');
    setLocalDbConnected(false);
    setLocalDbSuccess(false);
    setLocalDbError('');
    setLocalUsername('');
    setLocalPassword('');
    setLocalDbTables([]);
    setLocalSelectedDbTable('');
    setLocalSelectedSchema('');
    setPreviewRows([]);
    setPreviewColumns([]);
    setLocalTablePreviewError('');
    setLocalTableLoadingFromDb(false);
    setCredOpen(true); // reopen form
  };

  // Получение схем и таблиц
  useEffect(() => {
    if (localAuthToken) {
      ensureTablesLoaded();
      setLocalDbConnected && setLocalDbConnected(true);
    } else {
      setLocalDbConnected && setLocalDbConnected(false);
    }
  }, [localAuthToken, ensureTablesLoaded]);

  // Получение предпросмотра
  const fetchTablePreview = async (tableName) => {
    setLocalTablePreviewLoading(true);
    setPreviewRows([]);
    setPreviewColumns([]);
    setLocalTablePreviewError('');
    try {
      const schema = localSelectedSchema;
      const table = tableName;
      if (!schema || !table) {
        setLocalTablePreviewError('Выберите схему и таблицу');
        setLocalTablePreviewLoading(false);
        return;
      }
      const url = `${API_BASE_URL}/get-table-preview`;
      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localAuthToken}`
          },
          body: JSON.stringify({ schema, table })
        });
        if (!response.ok) {
          const err = await response.json().catch(() => ({}));
          setLocalTablePreviewError(err.detail || 'Ошибка при получении предпросмотра таблицы');
          return;
        }
        const result = await response.json();
        if (result.success && Array.isArray(result.data) && result.data.length > 0) {
          const columns = Object.keys(result.data[0]);
          const rows = result.data.map(rowObj => columns.map(col => rowObj[col]));
          setPreviewColumns(columns);
          setPreviewRows(rows);
        } else if (result.success && Array.isArray(result.data) && result.data.length === 0) {
          setPreviewColumns([]);
          setPreviewRows([]);
          setLocalTablePreviewError('Таблица пуста');
        } else {
          setLocalTablePreviewError(result.detail || 'Не удалось получить предпросмотр таблицы');
        }
      } catch (e) {
        setLocalTablePreviewError('Ошибка при получении предпросмотра таблицы: ' + (e?.message || e));
      } finally {
        setLocalTablePreviewLoading(false);
      }
    } catch (e) {
      setLocalTablePreviewError('Ошибка при получении предпросмотра таблицы');
    } finally {
      setLocalTablePreviewLoading(false);
    }
  };

  // Effect: fetch preview when table selected
  useEffect(() => {
    if (localSelectedDbTable && localAuthToken) {
      fetchTablePreview(localSelectedDbTable);
    } else {
      setPreviewColumns([]);
      setPreviewRows([]);
      setLocalTablePreviewError('');
    }
  }, [localSelectedDbTable, localAuthToken]);

  // Effect: show animation when tablePreview appears
  useEffect(() => {
    if (previewColumns.length > 0 && previewRows.length > 0 && !localTablePreviewLoading && !localTablePreviewError) {
      setLocalPreviewVisible(false);
      requestAnimationFrame(() => setLocalPreviewVisible(true));
    } else {
      setLocalPreviewVisible(false);
    }
  }, [previewColumns, previewRows, localTablePreviewLoading, localTablePreviewError]);

  // Скачивание выбранной таблицы
  const loadTableFromDb = async () => {
    if (!localSelectedDbTable || !localAuthToken) return;
    setLocalTablePreviewError('');
    setLocalTableLoadingFromDb(true);
    try {
      const schema = localSelectedSchema;
      const table = localSelectedDbTable;
      if (!schema || !table) {
        setLocalTablePreviewError('Выберите схему и таблицу');
        setLocalTableLoadingFromDb(false);
        return;
      }
      const response = await fetch(`${API_BASE_URL}/download-table-from-db`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localAuthToken}`
        },
        body: JSON.stringify({ schema, table })
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        setLocalTablePreviewError(err.detail || 'Ошибка загрузки таблицы из БД');
        return;
      }
      const blob = await response.blob();
      const file = new File([blob], `${table}.xlsx`, { type: blob.type });
      // Здесь не парсим файл, просто скачиваем
      const link = document.createElement('a');
      link.href = window.URL.createObjectURL(blob);
      link.download = `${table}.xlsx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (error) {
      setLocalTablePreviewError('Ошибка загрузки данных из БД: ' + (error?.message || error));
    } finally {
      setLocalTableLoadingFromDb(false);
    }
  };

  // --- Helpers ---
  const extractColumnsFromExcel = async(file) => {
    if (!file) return [];
    try {
      const arrayBuffer = await file.arrayBuffer();
      const XLSX = await import('xlsx');
      const workbook = XLSX.read(arrayBuffer, { type: 'array' });
      const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
      const rows = XLSX.utils.sheet_to_json(firstSheet, { header: 1 });
      if (rows.length > 0) {
        return rows[0].map(h=>h?.toString().trim());
      }
    }catch(e){ console.error(e); }
    return [];
  };

  // --- Drag & Drop handlers for upload file ---
  const handleUploadDragEnter = (e) => { e.preventDefault(); e.stopPropagation(); setIsUploadDragOver(true); };
  const handleUploadDragLeave = (e) => { e.preventDefault(); e.stopPropagation(); setIsUploadDragOver(false); };
  const handleUploadDragOver = (e) => { e.preventDefault(); e.stopPropagation(); };
  const handleUploadDrop = (e) => {
    e.preventDefault(); e.stopPropagation(); setIsUploadDragOver(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) handleUploadFileSelect({ target: { files: [files[0]] } });
  };

  const handleUploadFileSelect = async(e)=>{
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadFileError('');
    setUploadFileLoading(true);
    try{
      // size & type validation
      if (!validateFileSize(file, 100)) {
        setUploadFileError('Размер файла превышает 100 МБ');
        return;
      }
      if (!validateFileType(file) || (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls'))){
        setUploadFileError('Поддерживаются только Excel файлы (.xlsx, .xls)');
        return;
      }
      const cols = await extractColumnsFromExcel(file);
      setUploadFile(file);
      setUploadColumns(cols);
      setUploadPK([]);
    }catch(err){
      setUploadFileError('Ошибка обработки файла');
    }finally{
      setUploadFileLoading(false);
    }
  };

  // Очистка выбранного файла
  const handleUploadFileClear = () => {
    setUploadFile(null);
    setUploadColumns([]);
    setUploadPK([]);
    setUploadFileError('');
    setUploadFileLoading(false);
    const inp = document.querySelector('#db-upload-file-input');
    if (inp) inp.value = '';
  };

  // Upload table to DB
  const handleUploadToDb = async()=>{
    if(!uploadFile || !uploadSchema) return;
    let tableName = '';
    if(uploadMode==='existing'){
      tableName = uploadExistingTable;
      if(!tableName){ setUploadStatus('error'); return; }
    }else{
      tableName = uploadNewTableName;
      if(!tableName){ setUploadStatus('error'); return; }
    }
    setUploadStatus('loading');
    try{
      const formData = new FormData();
      formData.append('file', uploadFile, uploadFile.name);
      formData.append('schema', uploadSchema);
      formData.append('table_name', tableName);
      formData.append('primary_keys', JSON.stringify(uploadPK));
      formData.append('dbSaveMode', uploadMode==='new'?'new':'existing');
      const response = await fetch(`${API_BASE_URL}/upload-excel-to-db`,{
        method:'POST',
        headers:{ 'Authorization': `Bearer ${localAuthToken}` },
        body: formData
      });
      const res = await response.json();
      if(response.ok && res.success){
        setUploadStatus('success');
        setTimeout(() => setUploadStatus('idle'), 2000);
        refreshTables(); // обновить глобальный список таблиц
      }else{
        setUploadStatus('error');
        setUploadFileError(res.detail || 'Ошибка при загрузке файла в БД');
      }
    }catch(err){
      setUploadStatus('error');
      setUploadFileError('Ошибка загрузки: '+err.message);
    }
  };

  // Show fade preview for upload columns
  useEffect(()=>{
    if(uploadColumns.length>0){ setUploadPreviewVisible(false); requestAnimationFrame(()=>setUploadPreviewVisible(true)); }
    else{ setUploadPreviewVisible(false);} 
  },[uploadColumns]);

  // Scroll to success message
  useEffect(()=>{
    if(uploadStatus==='success' && uploadSuccessRef.current){
      uploadSuccessRef.current.scrollIntoView({ behavior:'smooth', block:'end' });
    }
  },[uploadStatus]);

  // Persist relevant state on any change
  useEffect(() => {
    persistedDbWorkState = {
      activeTab,
      localDbConnected,
      localAuthToken,
      localDbTables,
      localSelectedDbTable,
      localSelectedSchema,
      uploadFile,
      uploadColumns,
      uploadMode,
      uploadSchema,
      uploadExistingTable,
      uploadNewTableName,
      uploadPK
    };
  }, [activeTab, localDbConnected, localAuthToken, localDbTables, localSelectedDbTable, localSelectedSchema, uploadFile, uploadColumns, uploadMode, uploadSchema, uploadExistingTable, uploadNewTableName, uploadPK]);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Общая карточка подключения к БД */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
            <Card className="mb-6">
          <CardHeader onClick={()=>setCredOpen(prev=>!prev)} className="cursor-pointer select-none flex justify-between items-center">
                <CardTitle>Подключение к базе данных</CardTitle>
            {credOpen ? <ChevronUp size={18}/> : <ChevronDown size={18}/>}
              </CardHeader>
          {credOpen && (
              <CardContent>
                <div className="flex gap-2 mb-4">
                  <div className="flex-1">
                    <Input type="text" value={localUsername} onChange={e => setLocalUsername(e.target.value)} placeholder="Логин" disabled={localDbConnected || localDbConnecting} />
                  </div>
                  <div className="flex-1">
                    <Input type="password" value={localPassword} onChange={e => setLocalPassword(e.target.value)} placeholder="Пароль" disabled={localDbConnected || localDbConnecting} />
                  </div>
                </div>
                {!localDbConnected ? (
                  <Button
                    onClick={handleDbConnect}
                    disabled={localDbConnecting || !localUsername || !localPassword}
                    className="w-full"
                  >
                {localDbConnecting ? 'Подключение...' : 'Подключиться к базе данных'}
                  </Button>
                ) : (
              <Button onClick={handleDbDisconnect} className="w-full">Отключиться</Button>
                )}
                {localDbError && <div className="text-red-600 mt-2">{localDbError}</div>}
              </CardContent>
          )}
            </Card>

        <TabsList className="grid w-full grid-cols-2 mb-4">
          <TabsTrigger value="download" className="flex items-center space-x-2">
            <Database size={16} />
            <span>Загрузить из БД</span>
          </TabsTrigger>
          <TabsTrigger value="upload" className="flex items-center space-x-2">
            <Upload size={16} />
            <span>Загрузить в БД</span>
          </TabsTrigger>
        </TabsList>
        <TabsContent value="download">
          <div className="space-y-4">
            {/* Карточка подключения удалена из этого блока, т.к. теперь она общая */}
            {localDbConnected && (
              <Card>
                <CardHeader>
                  <CardTitle>Выбор схемы и таблицы</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex gap-2 mb-4">
                    <div className="flex-1">
                      <label className="block text-sm font-medium mb-1">Схема</label>
                      <select value={localSelectedSchema} onChange={e => setLocalSelectedSchema(e.target.value)} className="w-full border rounded px-2 py-1">
                        <option value="">Выберите схему</option>
                        {localDbTables.map(({ schema }) => (
                          <option key={schema} value={schema}>{schema}</option>
                        ))}
                      </select>
                    </div>
                    <div className="flex-1">
                      <label className="block text-sm font-medium mb-1">Таблица</label>
                      <select value={localSelectedDbTable} onChange={e => setLocalSelectedDbTable(e.target.value)} className="w-full border rounded px-2 py-1" disabled={!localSelectedSchema}>
                        <option value="">Выберите таблицу</option>
                        {localDbTables.find(s => s.schema === localSelectedSchema)?.tables.map(table => (
                          <option key={table} value={table}>{table}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                  {/* Убрано сообщение о загрузке предпросмотра */}
                  {previewColumns.length > 0 && previewRows.length > 0 && (
                    <div
                      ref={previewRef}
                      className={`mt-4 overflow-auto border rounded transition-opacity duration-300 ${localPreviewVisible ? 'opacity-100' : 'opacity-0'}`}
                    >
                      <table className="min-w-full text-sm">
                        <thead>
                          <tr>
                            {previewColumns.map(col => <th key={col} className="px-2 py-1 border-b bg-gray-50 text-left">{col}</th>)}
                          </tr>
                        </thead>
                        <tbody>
                          {previewRows.map((row, idx) => (
                            <tr key={idx}>
                              {row.map((cell, i) => <td key={i} className="px-2 py-1 border-b text-left">{cell}</td>)}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  {/* Download button under preview */}
                  <div className="flex mt-4">
                    <Button
                      className="w-full flex justify-center items-center space-x-2"
                      onClick={loadTableFromDb}
                      disabled={!localSelectedSchema || !localSelectedDbTable || downloadStatus==='loading'}
                    >
                      <Download size={16} />
                      <span>Скачать выбранную таблицу</span>
                    </Button>
                  </div>
                  {downloadStatus==='success' && <div className="text-green-600 mt-2">Файл скачан!</div>}
                  {downloadStatus==='error' && <div className="text-red-600 mt-2">Ошибка скачивания</div>}
                  {localTablePreviewError && <div className="text-red-600 mt-2">{localTablePreviewError}</div>}
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>
        <TabsContent value="upload">
          <div className="space-y-4">
            {/* File upload (drag & drop) */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Upload className="text-primary" size={20} />
                  <span>Загрузка файла</span>
                </CardTitle>
                <CardDescription>Поддерживаются форматы: Excel (.xlsx, .xls)</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div
                  className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${isUploadDragOver ? 'border-primary bg-primary/5' : 'border-border'}`}
                  onDragEnter={handleUploadDragEnter}
                  onDragLeave={handleUploadDragLeave}
                  onDragOver={handleUploadDragOver}
                  onDrop={handleUploadDrop}
                >
                  <Upload className={`mx-auto mb-4 ${isUploadDragOver ? 'text-primary' : 'text-muted-foreground'}`} size={48} />
                  <div className="space-y-2">
                    <p className="text-lg font-medium">
                      {isUploadDragOver ? 'Отпустите файл для загрузки' : 'Перетащите файл сюда или выберите файл'}
                    </p>
                    <p className="text-sm text-muted-foreground">Максимальный размер файла: 100 МБ</p>
                  </div>
                  <Input
                    id="db-upload-file-input"
                    type="file"
                    accept=".xlsx,.xls"
                    onChange={handleUploadFileSelect}
                    disabled={uploadFileLoading}
                    className="mt-4 max-w-xs mx-auto"
                  />
                  {uploadFileLoading && (
                    <div className="mt-4 flex items-center justify-center space-x-2">
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary"></div>
                      <span className="text-sm text-muted-foreground">Обработка файла...</span>
                    </div>
                  )}
                </div>
                {uploadFile && !uploadFileError && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <CheckCircle className="text-green-600" size={20} />
                        <div>
                          <p className="font-medium text-green-800">Файл успешно загружен</p>
                          <p className="text-sm text-green-600">{uploadFile.name} ({formatFileSize(uploadFile.size)})</p>
                        </div>
                      </div>
                      <Button variant="outline" size="sm" onClick={handleUploadFileClear} className="text-gray-600 hover:text-gray-800">Очистить</Button>
                    </div>
                  </div>
                )}
                {uploadFileError && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <div className="flex items-center space-x-2">
                      <AlertCircle className="text-red-600" size={20} />
                      <div>
                        <p className="font-medium text-red-800">Ошибка загрузки файла</p>
                        <p className="text-sm text-red-600">{uploadFileError}</p>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Mode selection (показывается только после подключения к БД) */}
            {uploadFile && localDbConnected && (
              <div className="grid grid-cols-2 gap-3 mt-4">
                <button
                  onClick={()=>setUploadMode('existing')}
                  className={`p-3 rounded-lg border-2 transition-all ${uploadMode==='existing'?'border-primary bg-primary/5 text-primary':'border-gray-200 hover:border-gray-300'}`}
                >
                  <div className="flex flex-col items-center space-y-2">
                    <Database size={20} />
                    <span className="font-medium text-sm">Загрузить в существующую таблицу</span>
                  </div>
                </button>
                <button
                  onClick={()=>setUploadMode('new')}
                  className={`p-3 rounded-lg border-2 transition-all ${uploadMode==='new'?'border-primary bg-primary/5 text-primary':'border-gray-200 hover:border-gray-300'}`}
                >
                  <div className="flex flex-col items-center space-y-2">
                    <Settings size={20} />
                    <span className="font-medium text-sm">Создать и загрузить в новую таблицу</span>
                  </div>
                </button>
              </div>
            )}

            {/* Existing mode (только после подключения) */}
            {uploadFile && localDbConnected && uploadMode==='existing' && (
              <div className="mt-4 flex flex-col md:flex-row md:items-center gap-3">
                <div className="w-full md:w-1/2">
                  <label className="block text-sm font-medium mb-1">Схема</label>
                  <select value={uploadSchema} onChange={e=>{setUploadSchema(e.target.value); setUploadExistingTable('');}} className="w-full border rounded px-2 py-1">
                    <option value="">Выберите схему</option>
                    {localDbTables.map(s=> <option key={s.schema} value={s.schema}>{s.schema}</option>)}
                  </select>
                </div>
                <div className="w-full md:w-1/2">
                  <label className="block text-sm font-medium mb-1">Таблица</label>
                  <select value={uploadExistingTable} onChange={e=>setUploadExistingTable(e.target.value)} className="w-full border rounded px-2 py-1" disabled={!uploadSchema}>
                    <option value="">Выберите таблицу</option>
                    {localDbTables.find(s=>s.schema===uploadSchema)?.tables.map(t=> <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
              </div>
            )}

            {/* New mode (только после подключения) */}
            {uploadFile && localDbConnected && uploadMode==='new' && (
              <div className="mt-4 space-y-4">
                <div className="flex flex-col md:flex-row md:items-center gap-3">
                  <div className="w-full md:w-1/2">
                    <label className="block text-sm font-medium mb-1">Схема</label>
                    <select value={uploadSchema} onChange={e=>setUploadSchema(e.target.value)} className="w-full border rounded px-2 py-1">
                      <option value="">Выберите схему</option>
                      {localDbTables.map(s=> <option key={s.schema} value={s.schema}>{s.schema}</option>)}
                    </select>
                  </div>
                  <div className="w-full md:w-1/2">
                    <label className="block text-sm font-medium mb-1">Название новой таблицы</label>
                    <Input value={uploadNewTableName} onChange={e=>setUploadNewTableName(e.target.value)} placeholder="Введите имя" />
                  </div>
                </div>
                {/* PK selection */}
                {uploadColumns.length>0 && (
                  <div>
                    <label className="block text-sm font-medium mb-1">Первичные ключи</label>
                    <div className="flex flex-wrap gap-2">
                      {uploadColumns.map(col=>{
                        const checked = uploadPK.includes(col);
                        return (
                          <label key={col} className={`flex items-center space-x-1 text-sm border rounded px-2 py-1 cursor-pointer transition-colors ${checked?'bg-blue-100 border-blue-500':'bg-gray-50 border-gray-300'}`}>
                            <input type="checkbox" checked={checked} onChange={e=>{
                              if(e.target.checked) setUploadPK([...uploadPK,col]); else setUploadPK(uploadPK.filter(pk=>pk!==col));
                            }} className="accent-blue-600" />
                            <span>{col}</span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Предпросмотр не нужен, поэтому убран */}

            {/* Upload button – доступна только при подключении */}
            {uploadFile && localDbConnected && (
              <Button className="w-full mt-4" onClick={handleUploadToDb} disabled={uploadStatus==='loading' || !uploadSchema || (uploadMode==='existing'? !uploadExistingTable : !uploadNewTableName)}>
                {uploadStatus==='loading'?'Загрузка...':'Загрузить в БД'}
              </Button>
            )}
            {uploadStatus==='success' && (
              <div ref={uploadSuccessRef} className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center space-x-2 mt-4">
                <CheckCircle className="text-green-600" size={20} />
                <span className="font-medium text-green-800">Файл успешно загружен в базу данных</span>
              </div>
            )}
            {uploadStatus==='error' && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center space-x-2 mt-4 animate-fade-in">
                <AlertCircle className="text-red-600" size={22} />
                <div>
                  <span className="font-medium text-red-800">Ошибка загрузки в базу данных</span>
                  <div className="text-sm text-red-600 mt-1">{localTablePreviewError || 'Произошла ошибка при загрузке файла. Проверьте данные и повторите попытку.'}</div>
                </div>
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
