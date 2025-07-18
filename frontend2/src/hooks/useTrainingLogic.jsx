import { useState, useEffect, useRef } from 'react';
import { API_BASE_URL } from '../apiConfig.js';
import { useData } from '../contexts/DataContext';

export function useTrainingLogic({
  uploadedFile,
  trainingConfig,
  updateTrainingStatus,
  sessionId,
  globalTrainingStatus,
  setTotalTrainingTime,
  authToken,
  setAuthToken
}) {
  // --- Auto-save DB state ---
  const [autoSaveEnabled, setAutoSaveEnabled] = useState(false);
  const [dbUsername, setDbUsername] = useState('');
  const [dbPassword, setDbPassword] = useState('');
  const [dbConnecting, setDbConnecting] = useState(false);
  const [dbConnected, setDbConnected] = useState(false);
  const [dbError, setDbError] = useState('');
  const [dbTables, setDbTables] = useState([]);
  const [dbTablesLoading, setDbTablesLoading] = useState(false);
  const [selectedSchema, setSelectedSchema] = useState('');
  const [selectedTable, setSelectedTable] = useState('');
  const [saveTableName, setSaveTableName] = useState('');
  const [autoSaveMenuOpen, setAutoSaveMenuOpen] = useState(false);
  const [saveMode, setSaveMode] = useState('existing');
  const [newTableName, setNewTableName] = useState('');
  const [autoSaveSettings, setAutoSaveSettings] = useState(null);
  const [uploadTableName, setUploadTableName] = useState('');
  const [fileColumns, setFileColumns] = useState([]);
  const [selectedPrimaryKeys, setSelectedPrimaryKeys] = useState([]);

  // --- Training state ---
  const [trainingStatus, setTrainingStatus] = useState('idle');
  const [progress, setProgress] = useState(0);
  const [currentModel, setCurrentModel] = useState('');
  const [elapsedTime, setElapsedTime] = useState(0);
  const { setPredictionRows, predictionProcessed, setPredictionProcessed, trainingStartTime, setTrainingStartTime, setSessionId } = useData();
  const [pycaretModalVisible, setPycaretModalVisible] = useState(false);
  const [pycaretLeaderboards, setPycaretLeaderboards] = useState(null);

  // Ref for polling interval
  const pollingRef = useRef(null);

  // --- Auto-save DB functions ---
  const handleDbConnect = async () => {
    setDbError('');
    setDbConnecting(true);
    setAuthToken(null);
    setDbConnected(false);
    try {
      const response = await fetch(`${API_BASE_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: dbUsername, password: dbPassword })
      });
      if (!response.ok) {
        if (response.status === 401) {
          setDbError('Неверный логин или пароль');
        } else {
          setDbError(`Ошибка сервера: ${response.status}`);
        }
        setDbConnected(false);
        setAuthToken(null);
        setDbConnecting(false);
        return;
      }
      let result = null;
      try {
        result = await response.json();
      } catch (jsonErr) {
        setDbError('Не удалось получить ответ от сервера.');
        setDbConnected(false);
        setDbConnecting(false);
        return;
      }
      if (result.success && result.access_token) {
        setAuthToken(result.access_token);
        setDbConnected(true);
        setDbError('');
        setDbUsername('');
        setDbPassword('');
      } else {
        setDbError('Не удалось подключиться к базе данных');
        setDbConnected(false);
      }
    } catch (error) {
      setDbError('Ошибка подключения: ' + error.message);
      setDbConnected(false);
    } finally {
      setDbConnecting(false);
    }
  };

  const handleDbInputChange = (setter) => (e) => {
    setter(e.target.value);
    setDbError('');
  };

  const handleSchemaChange = (schema) => {
    setSelectedSchema(schema);
    setSelectedTable('');
  };

  const handleTableChange = (table) => {
    setSelectedTable(table);
  };

  const handleAutoSaveSetup = async (settings) => {
    if (!settings) return false;
    setDbError('');
    try {
      if (settings.mode === 'create') {
        if (!uploadedFile) {
          setDbError('Файл не выбран. Пожалуйста, загрузите файл перед созданием таблицы.');
          return false;
        }
        const formData = new FormData();
        formData.append('file', uploadedFile, uploadedFile.name);
        formData.append('table_name', settings.newTableName);
        formData.append('primary_keys', JSON.stringify(selectedPrimaryKeys));
        formData.append('create_table_only', 'true');
        formData.append('schema', settings.selectedSchema);
        const response = await fetch(`${API_BASE_URL}/create-table-from-file`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${authToken}`
          },
          body: formData
        });
        const result = await response.json();
        if (!response.ok || !result.success) {
          setDbError(result.detail || 'Ошибка создания таблицы');
          return false;
        }
        setUploadTableName(settings.newTableName);
        setAutoSaveSettings({
          ...settings,
          tableName: settings.newTableName,
          primaryKeys: selectedPrimaryKeys
        });
      } else {
        if (!uploadedFile) {
          setDbError('Файл не выбран. Пожалуйста, загрузите файл перед проверкой структуры таблицы.');
          return false;
        }
        const [schema, ...tableParts] = settings.selectedTable.split('.');
        const tableName = tableParts.join('.');
        const formData = new FormData();
        formData.append('file', uploadedFile, uploadedFile.name);
        formData.append('table_name', tableName);
        formData.append('schema', schema);
        const response = await fetch(`${API_BASE_URL}/check-df-matches-table-schema`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${authToken}`
          },
          body: formData
        });
        const result = await response.json();
        if (!result.success) {
          setDbError(result.detail || 'Структура файла не совпадает с таблицей');
          return false;
        }
        setUploadTableName(tableName);
        setAutoSaveSettings({
          ...settings,
          tableName
        });
      }
      setDbError('');
      return true;
    } catch (error) {
      setDbError(error.message || 'Ошибка настройки автосохранения');
      return false;
    }
  };

  // --- Training logic ---
  const resetTrainingState = () => {
    setTrainingStatus(null);
    setSessionId(null);
    setTotalTrainingTime('');
    setTrainingStartTime(null);
  };

  const getTrainingStatus = () => {
    if (globalTrainingStatus) {
      if (['completed', 'complete'].includes(globalTrainingStatus.status)) {
        return 'completed';
      }
      if (globalTrainingStatus.status === 'failed') {
        return 'error';
      }
      if (['initializing', 'running'].includes(globalTrainingStatus.status)) {
        return 'running';
      }
    }
    return trainingStatus;
  };

  const getStatusMessage = () => {
    if (!globalTrainingStatus) return '';
    if (globalTrainingStatus.pycaret_locked === true) {
      return 'Повышенная нагрузка на сервер. Обучение и прогноз займет немного больше времени.';
    }
    const status = globalTrainingStatus.status;
    if (status === 'initializing') return 'Инициализация обучения...';
    if (status === 'running') return `Обучение в процессе (${globalTrainingStatus.progress ?? 0}%)`;
    if (status === 'completed') return 'Обучение успешно завершено!';
    if (status === 'failed') return 'Ошибка при обучении';
    return status;
  };

  const getCurrentProgress = () => {
    return globalTrainingStatus?.progress ?? progress;
  };

  const getCurrentModel = () => {
    return globalTrainingStatus?.current_model || currentModel;
  };

  // Очистка polling при размонтировании
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, []);

  // Опрос статуса при получении sessionId
  useEffect(() => {
    if (sessionId && getTrainingStatus() === 'running') {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
      pollingRef.current = setInterval(pollTrainingStatus, 2000);
      pollTrainingStatus();
    } else if (getTrainingStatus() === 'completed' || getTrainingStatus() === 'error') {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      // Do not reset sessionId or trainingStatus here
    }
    // eslint-disable-next-line
  }, [sessionId, getTrainingStatus()]);

  // useEffect for globalTrainingStatus?.status больше не нужен для polling

  // Таймер elapsedTime
  useEffect(() => {
    let timeInterval;
    if (getTrainingStatus() === 'running') {
      if (trainingStartTime) {
        timeInterval = setInterval(() => {
          setElapsedTime(Math.floor((Date.now() - trainingStartTime) / 1000));
        }, 1000);
      }
    } else if (getTrainingStatus() !== 'running') {
      setElapsedTime(0);
    }
    return () => {
      if (timeInterval) {
        clearInterval(timeInterval);
      }
    };
    // eslint-disable-next-line
  }, [getTrainingStatus(), trainingStartTime]);

  // Опрос статуса обучения
  const pollTrainingStatus = async () => {
    if (!sessionId) return;
    const currentStatus = getTrainingStatus();
    if (currentStatus === 'completed' || currentStatus === 'error') {
      return;
    }
    try {
      const statusResp = await fetch(`${API_BASE_URL}/training_status/${sessionId}`);
      if (!statusResp.ok) throw new Error('Failed to fetch training status');
      const status = await statusResp.json();
      updateTrainingStatus(status);
      if (status.current_model) setCurrentModel(status.current_model);
      if (typeof status.progress === 'number') setProgress(status.progress);
      if (["completed", "complete", "failed"].includes(status.status)) {
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
        if (["completed", "complete"].includes(status.status)) {
          try {
            const fileResp = await fetch(`${API_BASE_URL}/download_prediction/${sessionId}`);
            if (!fileResp.ok) throw new Error('Ошибка скачивания прогноза');
            const blob = await fileResp.blob();
            const arrayBuffer = await blob.arrayBuffer();
            const XLSX = await import('xlsx');
            const workbook = XLSX.read(arrayBuffer, { type: 'array' });
            const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
            const rows = XLSX.utils.sheet_to_json(firstSheet, { header: 1 });
            if (rows.length > 1) {
              const headers = rows[0];
              // Фильтруем технические колонки 0.1-0.9
              const filteredHeaders = headers.filter(h => !/^0\.[1-9]$/.test(h));
              const dataRows = rows.slice(1);
              const parsedRows = dataRows.map(row =>
                Object.fromEntries(filteredHeaders.map((h, i) => [h, row[headers.indexOf(h)]]))
              );
              setPredictionRows(parsedRows);
            }
            if (trainingStartTime) {
              const endTime = Date.now();
              const diffMs = endTime - trainingStartTime;
              const minutes = Math.floor(diffMs / 60000);
              const seconds = Math.floor((diffMs % 60000) / 1000);
              const finalTime = `${minutes}m ${seconds}s`;
              setTotalTrainingTime(finalTime);
              setTrainingStartTime(null);
              setPredictionProcessed(true);
            }
          } catch (e) {
            alert('Ошибка при обработке прогноза: ' + (e instanceof Error ? e.message : e));
          }
        }
        // Do not reset sessionId or trainingStatus here
      }
    } catch (error) {
      // Можно добавить обработку ошибок
    }
  };

  const handleStartTraining = async () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    setPredictionRows([]);
    setPredictionProcessed(false);
    if (!uploadedFile) {
      alert('Ошибка: Файл не выбран. Пожалуйста, загрузите файл перед обучением модели.');
      return;
    }
    if (!trainingConfig) {
      alert('Ошибка: Конфигурация модели не задана. Пожалуйста, настройте параметры модели.');
      return;
    }
    setTrainingStatus('running');
    setProgress(0);
    setElapsedTime(0);
    setCurrentModel('Инициализация...');
    setTotalTrainingTime('');
    setTrainingStartTime(Date.now());
    updateTrainingStatus({ status: 'initializing', progress: 0 });
    try {
      const formData = new FormData();
      if (uploadedFile) {
        formData.append('training_file', uploadedFile, uploadedFile.name);
      }
      const params = {
        datetime_column: trainingConfig.dateColumn || 'date',
        target_column: trainingConfig.targetColumn || 'value',
        item_id_column: trainingConfig.idColumn || '',
        frequency: trainingConfig.frequency || 'D',
        fill_missing_method: trainingConfig.missingValueMethod === 'forward_fill' ? 'interpolate' : 
                            trainingConfig.missingValueMethod === 'backward_fill' ? 'backfill' :
                            trainingConfig.missingValueMethod === 'interpolate' ? 'interpolate' : 
                            'None',
        fill_group_columns: trainingConfig.groupingColumns || [],
        use_russian_holidays: trainingConfig.considerHolidays || false,
        evaluation_metric: trainingConfig.selectedMetric?.toUpperCase() || 'MAE',
        models_to_train: trainingConfig.selectedAutogluonModels?.includes('*') ? '*' : 
                        (trainingConfig.selectedAutogluonModels?.length > 0 ? trainingConfig.selectedAutogluonModels : '*'),
        autogluon_preset: trainingConfig.autogluonPreset || 'medium_quality',
        predict_mean_only: false,
        prediction_length: trainingConfig.forecastHorizon || 30,
        training_time_limit: trainingConfig.trainingTimeLimit || 60,
        static_feature_columns: trainingConfig.staticFeatures || [],
        pycaret_models: trainingConfig.selectedPycaretModels?.[0] === '*' && trainingConfig.selectedPycaretModels.length === 1 ? '*' : 
                       (trainingConfig.selectedPycaretModels?.length > 0 ? trainingConfig.selectedPycaretModels : null)
      };
      if (autoSaveEnabled && autoSaveSettings && uploadTableName) {
        params.upload_table_name = uploadTableName;
        if (autoSaveSettings.selectedSchema) {
          params.upload_table_schema = autoSaveSettings.selectedSchema;
        }
      }
      formData.append('params', JSON.stringify(params));
      const headers = { 'Accept': 'application/json' };
      if (autoSaveEnabled && authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
      }
      const response = await fetch(`${API_BASE_URL}/train_prediction_save/`, {
        method: 'POST',
        body: formData,
        headers: headers
      });
      if (!response.ok) {
        const errorText = await response.text();
        let errorData;
        try {
          errorData = JSON.parse(errorText);
        } catch (e) {
          errorData = { detail: errorText };
        }
        const errorMessage = errorData.detail || 'Failed to train and predict';
        alert(`Ошибка обучения+прогноза: ${errorMessage}`);
        setTrainingStatus('error');
        return;
      }
      const result = await response.json();
      if (result.session_id) {
        setSessionId(result.session_id);
        updateTrainingStatus({ status: 'running', progress: 0 });
      }
    } catch (error) {
      alert(`Ошибка при запуске обучения: ${error.message}`);
      setTrainingStatus('error');
      updateTrainingStatus({ status: 'failed', progress: 0, error: error.message });
    }
  };

  const handleStopTraining = () => {
    setTrainingStatus('idle');
    setProgress(0);
    setElapsedTime(0);
    setCurrentModel('');
    setTrainingStartTime(null);
    pollingRef.current = null; // Clear polling interval on stop
    resetTrainingState();
  };

  // PyCaret modal logic
  const openPycaretModal = () => {
    setPycaretLeaderboards(globalTrainingStatus?.pycaret || null);
    setPycaretModalVisible(true);
  };
  const closePycaretModal = () => {
    setPycaretModalVisible(false);
  };
  const isPycaretRow = (row) => row.strategy === 'pycaret' || row.isPyCaret === true;
  const hasPycaretData = () => globalTrainingStatus?.pycaret && typeof globalTrainingStatus.pycaret === 'object';

  // Badges for leaderboard
  const getStatusBadge = (status) => {
    switch (status) {
      case 'completed':
        return <span className="bg-green-100 text-green-800 px-2 py-1 rounded">Завершено</span>;
      case 'running':
        return <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded">Выполняется</span>;
      case 'error':
        return <span className="bg-red-100 text-red-800 px-2 py-1 rounded">Ошибка</span>;
      default:
        return <span className="bg-gray-100 text-gray-800 px-2 py-1 rounded">Ожидание</span>;
    }
  };
  const getRankBadge = (rank) => {
    if (!rank) return null;
    const colors = {
      1: 'bg-yellow-100 text-yellow-800',
      2: 'bg-gray-100 text-gray-800',
      3: 'bg-orange-100 text-orange-800'
    };
    return <span className={`px-2 py-1 rounded ${colors[rank] || 'bg-blue-100 text-blue-800'}`}>#{rank}</span>;
  };
  const formatCellValue = (key, value) => {
    if (value === null || value === undefined || value === '') return '-';
    if (key === 'rank') return getRankBadge(value);
    if (key === 'status') return getStatusBadge(value);
    if (key === 'model') return <span className="font-medium">{value}</span>;
    if (key === 'trainingTime' || key === 'training_time') return <span className="text-sm text-muted-foreground">{value}</span>;
    if (typeof value === 'number') {
      if (key === 'score_val') return value.toFixed(3);
      if (key.toLowerCase().includes('mape')) return `${value.toFixed(1)}%`;
      if (key.toLowerCase().includes('r2') || key.toLowerCase().includes('rsquared')) return value.toFixed(3);
      return value.toFixed(2);
    }
    return value;
  };

  // Метрики
  const getBestModel = () => {
    const leaderboard = globalTrainingStatus?.leaderboard;
    if (leaderboard && leaderboard.length > 0) {
      const bestModel = leaderboard.find(model => model.rank === 1) || leaderboard[0];
      return bestModel?.model || null;
    }
    return null;
  };
  const getBestModelMetric = () => {
    const leaderboard = globalTrainingStatus?.leaderboard;
    if (leaderboard && leaderboard.length > 0) {
      const bestModel = leaderboard.find(model => model.rank === 1) || leaderboard[0];
      if (bestModel && bestModel.score_val !== null && bestModel.score_val !== undefined) {
        const metricName = globalTrainingStatus?.training_params?.evaluation_metric || trainingConfig?.selectedMetric?.toUpperCase() || 'Метрика';
        return `${metricName}: ${bestModel.score_val.toFixed(3)}`;
      }
    }
    return null;
  };
  const getAverageMetric = () => {
    const leaderboard = globalTrainingStatus?.leaderboard;
    if (leaderboard && leaderboard.length > 0) {
      const validModels = leaderboard.filter(model => model.score_val !== null && model.score_val !== undefined);
      if (validModels.length > 0) {
        const avgScore = validModels.reduce((sum, model) => sum + model.score_val, 0) / validModels.length;
        const metricName = globalTrainingStatus?.training_params?.evaluation_metric || trainingConfig?.selectedMetric?.toUpperCase() || 'Метрика';
        return `${metricName}: ${avgScore.toFixed(3)}`;
      }
    }
    return null;
  };
  const getTotalTrainingTime = () => {
    if (typeof setTotalTrainingTime === 'function' && setTotalTrainingTime.current) {
      return setTotalTrainingTime.current;
    }
    if (globalTrainingStatus?.total_training_time) {
      return globalTrainingStatus.total_training_time;
    }
    if (globalTrainingStatus?.start_time && globalTrainingStatus?.end_time) {
      try {
        const startTime = new Date(globalTrainingStatus.start_time);
        const endTime = new Date(globalTrainingStatus.end_time);
        const diffMs = endTime - startTime;
        const minutes = Math.floor(diffMs / 60000);
        const seconds = Math.floor((diffMs % 60000) / 1000);
        return `${minutes}m ${seconds}s`;
      } catch (e) {}
    }
    return null;
  };

  // Парсим заголовки файла при загрузке uploadedFile
  useEffect(() => {
    if (!uploadedFile) {
      setFileColumns([]);
      return;
    }
    const parseHeaders = async () => {
      if (uploadedFile.name.endsWith('.csv')) {
        const reader = new FileReader();
        reader.onload = (e) => {
          const text = e.target.result;
          const lines = text.split(/\r?\n/);
          if (lines.length > 0) {
            const headers = lines[0].split(',').map(h => h.trim());
            setFileColumns(headers);
          }
        };
        reader.readAsText(uploadedFile);
      } else if (uploadedFile.name.endsWith('.xlsx') || uploadedFile.name.endsWith('.xls')) {
        const reader = new FileReader();
        reader.onload = async (e) => {
          const XLSX = await import('xlsx');
          const data = new Uint8Array(e.target.result);
          const workbook = XLSX.read(data, { type: 'array' });
          const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
          const rows = XLSX.utils.sheet_to_json(firstSheet, { header: 1 });
          if (rows.length > 0) {
            setFileColumns(rows[0].map(h => h?.toString().trim()));
          }
        };
        reader.readAsArrayBuffer(uploadedFile);
      } else {
        setFileColumns([]);
      }
    };
    parseHeaders();
    // eslint-disable-next-line
  }, [uploadedFile]);

  return {
    autoSaveEnabled, setAutoSaveEnabled,
    dbUsername, setDbUsername,
    dbPassword, setDbPassword,
    dbConnecting, dbConnected, dbError, dbTables, dbTablesLoading,
    selectedSchema, setSelectedSchema, selectedTable, setSelectedTable,
    saveTableName, setSaveTableName, autoSaveMenuOpen, setAutoSaveMenuOpen,
    saveMode, setSaveMode, newTableName, setNewTableName, autoSaveSettings, uploadTableName,
    handleDbConnect, handleDbInputChange, handleSchemaChange, handleTableChange, handleAutoSaveSetup,
    fileColumns, selectedPrimaryKeys, setSelectedPrimaryKeys,
    setAuthToken,
    trainingStatus, setTrainingStatus, progress, setProgress, currentModel, setCurrentModel, elapsedTime, setElapsedTime, pycaretModalVisible, setPycaretModalVisible, pycaretLeaderboards, setPycaretLeaderboards, trainingStartTime,
    predictionProcessed, setPredictionProcessed,
    getTrainingStatus, getStatusMessage, getCurrentProgress, getCurrentModel,
    pollTrainingStatus, handleStartTraining, handleStopTraining,
    openPycaretModal, closePycaretModal, isPycaretRow, hasPycaretData, getStatusBadge, getRankBadge, formatCellValue,
    getBestModel, getBestModelMetric, getAverageMetric, getTotalTrainingTime,
    resetTrainingState
  };
}