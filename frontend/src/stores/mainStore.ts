import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useMainStore = defineStore('main', () => {
  const tableData = ref<any[]>([])
  const selectedFile = ref<File | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const chunkSize = ref(100000)

  // Колонки датасета
  const dateColumn = ref('<нет>')
  const targetColumn = ref('<нет>')
  const idColumn = ref('<нет>')
  const staticFeatures = ref<string[]>([])
  const selectedColumns = ref<string[]>([])
  const considerRussianHolidays = ref(false)
  const fillMethod = ref('None (оставить как есть)')
  const groupingColumns = ref<string[]>([])
  const selectedMetric = ref('MAE (Mean absolute error)')
  const selectedModels = ref<string[]>(['*'])
  const selectedPreset = ref('high_quality')
  const predictionHorizon = ref(3)
  const timeLimit = ref<number | null>(null)
  const meanOnly = ref(false)
  const trainPredictSave = ref(false)
  const sessionId = ref<string | null>(null)
  const trainingStatus = ref<any>(null)
  const predictionRows = ref<any[]>([])
  const horizonUnit = ref("D (день)")

  // PyCaret models selection
  const selectedPycaretModels = ref<string[]>(['*'])

  // --- DB connection state (обновлено) ---
  const authToken = ref<string | null>(null) // Теперь храним только токен
  const dbConnected = ref(false)
  const dbCheckResult = ref<{ success: boolean; detail: string; access_token?: string } | null>(null)
  const dbTables = ref<string[]>([]) // Новое: для хранения списка таблиц из БД

  function setTableData(data: any[]) {
    tableData.value = data
  }

  function setChunkSize(size: number) {
    chunkSize.value = size
  }

  function setFile(file: File | null) {
    selectedFile.value = file
    error.value = null
  }

  function setDateColumn(column: string) {
    dateColumn.value = column
  }

  function setTargetColumn(column: string) {
    targetColumn.value = column
  }

  function setIdColumn(column: string) {
    idColumn.value = column
  }

  function setStaticFeatures(features: string[]) {
    staticFeatures.value = features
  }

  function setSelectedColumns(columns: string[]) {
    selectedColumns.value = columns
  }

  function setConsiderRussianHolidays(value: boolean) {
    considerRussianHolidays.value = value
  }

  function setGroupingColumns(columns: string[]) {
    groupingColumns.value = columns
  }

  function setFillMethod(method: string) {
    fillMethod.value = method
  }

  function setSelectedMetric(metric: string) {
    selectedMetric.value = metric
  }

  function setSelectedModels(models: string[]) {
    selectedModels.value = models
  }

  function setSelectedPreset(preset: string) {
    selectedPreset.value = preset
  }

  function setPredictionHorizon(horizon: number) {
    predictionHorizon.value = horizon
  }

  function setTimeLimit(limit: number | null) {
    timeLimit.value = limit
  }

  function setMeanOnly(value: boolean) {
    meanOnly.value = value
  }

  function setTrainPredictSave(value: boolean) {
    trainPredictSave.value = value
  }

  function setSessionId(id: string | null) {
    sessionId.value = id
  }

  function setTrainingStatus(status: any) {
    trainingStatus.value = status
  }

  function setPredictionRows(rows: any[]) {
    predictionRows.value = rows
  }

  function setHorizonUnit(value: string) {
    horizonUnit.value = value
  }

  function setSelectedPycaretModels(models: string[]) {
    selectedPycaretModels.value = models
  }

  // Методы для JWT и подключения к БД
  function setAuthToken(token: string | null) {
    authToken.value = token
    // УДАЛЕНО: localStorage.setItem/removeItem
  }

  function setDbConnected(connected: boolean) {
    dbConnected.value = connected
  }

  function setDbCheckResult(result: { success: boolean; detail: string; access_token?: string } | null) {
    dbCheckResult.value = result
  }

  function setDbTables(tables: string[]) {
    dbTables.value = tables
  }

  return {
    tableData,
    selectedFile,
    isLoading,
    error,
    chunkSize,
    dateColumn,
    targetColumn,
    idColumn,
    staticFeatures,
    selectedColumns,
    considerRussianHolidays,
    fillMethod,
    groupingColumns,
    selectedMetric,
    selectedModels,
    selectedPreset,
    predictionHorizon,
    timeLimit,
    meanOnly,
    trainPredictSave,
    sessionId,
    trainingStatus,
    predictionRows,
    horizonUnit,
    selectedPycaretModels,
    // Новые экспорты для DB connection
    authToken,
    dbConnected,
    dbCheckResult,
    dbTables,
    setTableData,
    setChunkSize,
    setFile,
    setDateColumn,
    setTargetColumn,
    setIdColumn,
    setStaticFeatures,
    setSelectedColumns,
    setConsiderRussianHolidays,
    setGroupingColumns,
    setFillMethod,
    setSelectedMetric,
    setSelectedModels,
    setSelectedPreset,
    setPredictionHorizon,
    setTimeLimit,
    setMeanOnly,
    setTrainPredictSave,
    setSessionId,
    setTrainingStatus,
    setPredictionRows,
    setHorizonUnit,
    setSelectedPycaretModels,
    // Новые методы для DB connection
    setAuthToken,
    setDbConnected,
    setDbCheckResult,
    setDbTables,
  }
})