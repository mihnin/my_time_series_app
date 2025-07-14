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
  const [uploadDbName, setUploadDbName] = useState('')

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
      uploadDbName,
      setUploadDbName
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
