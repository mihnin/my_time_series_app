import React, { createContext, useContext, useState } from 'react'

const DataContext = createContext()

export function DataProvider({ children }) {
  const [uploadedData, setUploadedData] = useState(null)
  const [dataSource, setDataSource] = useState(null) // 'file' or 'database'
  const [selectedTable, setSelectedTable] = useState(null)
  
  // Training-related state
  const [uploadedFile, setUploadedFile] = useState(null)
  const [trainingConfig, setTrainingConfig] = useState(null)
  const [trainingStatus, setTrainingStatus] = useState(null)
  const [sessionId, setSessionId] = useState(null)
  const [authToken, setAuthToken] = useState(null)
  const [trainPredictSave, setTrainPredictSave] = useState(false)
  const [predictionRows, setPredictionRows] = useState([])
  const [dbConnected, setDbConnected] = useState(false)
  const [dbUsername, setDbUsername] = useState("")
  const [dbPassword, setDbPassword] = useState("")
  const [uploadDbName, setUploadDbName] = useState('')
  const [totalTrainingTime, setTotalTrainingTime] = useState('')
  const [predictionProcessed, setPredictionProcessed] = useState(false);
  const [previewData, setPreviewData] = useState(null)
  const [tablePreview, setTablePreview] = useState(null)
  const [activeTab, setActiveTab] = useState('file')
  const [dbTables, setDbTables] = useState([])
  const [dbTablesLoading, setDbTablesLoading] = useState(false)
  const [dbError, setDbError] = useState('')
  const [trainingStartTime, setTrainingStartTime] = useState(null);

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
      setTrainingStartTime
    }}>
      {children}
    </DataContext.Provider>
  )
}

export function useData() {
  const context = useContext(DataContext)
  if (!context) {
    throw new Error('useData must be used within a DataProvider')
  }
  return context
}
