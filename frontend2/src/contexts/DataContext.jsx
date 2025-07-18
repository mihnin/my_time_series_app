import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import { API_BASE_URL } from '../apiConfig.js';

const DataContext = createContext();

export function DataProvider({ children }) {
  const [uploadedData, setUploadedData] = useState(null);
  const [dataSource, setDataSource] = useState(null); // 'file' or 'database'
  const [selectedTable, setSelectedTable] = useState(null);
  
  // Training-related state
  const [uploadedFile, setUploadedFile] = useState(null);
  const [trainingConfig, setTrainingConfig] = useState(null);
  const [trainingStatus, setTrainingStatus] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [authToken, setAuthToken] = useState(null);
  const [trainPredictSave, setTrainPredictSave] = useState(false);
  const [predictionRows, setPredictionRows] = useState([]);
  const [dbConnected, setDbConnected] = useState(false);
  const [dbUsername, setDbUsername] = useState("");
  const [dbPassword, setDbPassword] = useState("");
  const [uploadDbName, setUploadDbName] = useState('');
  const [totalTrainingTime, setTotalTrainingTime] = useState('');
  const [predictionProcessed, setPredictionProcessed] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [tablePreview, setTablePreview] = useState(null);
  const [activeTab, setActiveTab] = useState('file');
  const [dbTables, setDbTables] = useState([]);
  const [dbTablesLoading, setDbTablesLoading] = useState(false);
  const [dbError, setDbError] = useState('');
  const [trainingStartTime, setTrainingStartTime] = useState(null);

  const tablesLoadedRef = useRef(false);

  const updateData = (data, source, table = null) => {
    setUploadedData(data)
    setDataSource(source)
    setSelectedTable(table)
  }

  const clearData = () => {
    setUploadedData(null)
    setDataSource(null)
    setSelectedTable(null)
  }

  const updateTrainingConfig = (config) => {
    setTrainingConfig(config)
  }

  const updateTrainingStatus = (status) => {
    setTrainingStatus(status)
  }

  const resetTrainingState = () => {
    setTrainingStatus(null)
    setSessionId(null)
    setTotalTrainingTime('')
    setPredictionRows([])
    setPredictionProcessed(false)
  }

  const ensureTablesLoaded = useCallback(async () => {
    if (!authToken || !dbConnected || dbTablesLoading || dbTables.length > 0 || tablesLoadedRef.current) {
      return;
    }
    tablesLoadedRef.current = true;
    setDbTablesLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/get-tables`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        }
      });
      const result = await response.json();
      if (result.success) {
        setDbTables(Object.keys(result.tables).map(schema => ({ schema, tables: result.tables[schema] })));
      } else {
        setDbError('Ошибка загрузки таблиц: ' + (result.message || 'Неизвестная ошибка'));
      }
    } catch (e) {
      setDbError('Ошибка загрузки таблиц: ' + (e.message || e));
    } finally {
      setDbTablesLoading(false);
    }
  }, [authToken, dbConnected, dbTablesLoading, dbTables.length]);

  // Always fetch latest tables from backend
  const refreshTables = useCallback(async () => {
    if (!authToken || !dbConnected) return;
    setDbTablesLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/get-tables`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        }
      });
      const result = await response.json();
      if (result.success) {
        setDbTables(Object.keys(result.tables).map(schema => ({ schema, tables: result.tables[schema] })));
      } else {
        setDbError('Ошибка загрузки таблиц: ' + (result.message || 'Неизвестная ошибка'));
      }
    } catch (e) {
      setDbError('Ошибка загрузки таблиц: ' + (e.message || e));
    } finally {
      setDbTablesLoading(false);
    }
  }, [authToken, dbConnected]);

  return (
    <DataContext.Provider value={{
      // Data state
      uploadedData,
      dataSource,
      selectedTable,
      updateData,
      clearData,
      
      // Training state
      uploadedFile,
      setUploadedFile,
      trainingConfig,
      updateTrainingConfig,
      trainingStatus,
      updateTrainingStatus,
      resetTrainingState,
      sessionId,
      setSessionId,
      authToken,
      setAuthToken,
      trainPredictSave,
      setTrainPredictSave,
      predictionRows,
      setPredictionRows,
      dbConnected,
      setDbConnected,
      dbUsername,
      setDbUsername,
      dbPassword,
      setDbPassword,
      uploadDbName,
      setUploadDbName,
      totalTrainingTime,
      setTotalTrainingTime,
      predictionProcessed,
      setPredictionProcessed,
      previewData,
      setPreviewData,
      tablePreview,
      setTablePreview,
      activeTab,
      setActiveTab,
      dbTables,
      setDbTables,
      dbTablesLoading,
      setDbTablesLoading,
      dbError,
      setDbError,
      trainingStartTime,
      setTrainingStartTime,
      ensureTablesLoaded,
      refreshTables,
    }}>
      {children}
    </DataContext.Provider>
  );
}

export function useData() {
  const context = useContext(DataContext);
  if (!context) {
    throw new Error('useData must be used within a DataProvider');
  }
  return context;
}
