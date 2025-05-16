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
  const considerRussianHolidays = ref(false)  // New state for holidays checkbox
  const fillMethod = ref('None (оставить как есть)')
  const groupingColumns = ref<string[]>([])
  const selectedMetric = ref('SQL (Scaled quantile loss)')
  const selectedModels = ref<string[]>(['*'])  // по умолчанию выбраны все модели
  const selectedPreset = ref('high_quality')
  const predictionHorizon = ref(3)
  const timeLimit = ref<number | null>(null)
  const meanOnly = ref(false)
  const trainPredictSave = ref(false)  // Новое состояние
  const sessionId = ref<string | null>(null)
  const trainingStatus = ref<any>(null)
  const predictionRows = ref<any[]>([])  // Новое состояние для строк прогноза
  const horizonUnit = ref("D (день)")

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

  function setSelectedColumns(columns: string[]) { // Новый метод для установки выбранных колонок
    selectedColumns.value = columns
  }

  function setConsiderRussianHolidays(value: boolean) { // Новый метод для установки значения чекбокса
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

  function setPredictionRows(rows: any[]) {  // Новый метод для установки строк прогноза
    predictionRows.value = rows
  }

  function setHorizonUnit(value: string) {
    horizonUnit.value = value
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
    selectedColumns, // Экспортируем новое свойство
    considerRussianHolidays, // Экспортируем новое свойство
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
    predictionRows, // Экспортируем новое свойство
    horizonUnit,
    setTableData,
    setChunkSize,
    setFile,
    setDateColumn,
    setTargetColumn,
    setIdColumn,
    setStaticFeatures,
    setSelectedColumns, // Экспортируем новый метод
    setConsiderRussianHolidays, // Экспортируем новый метод
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
    setPredictionRows, // Экспортируем новый метод
    setHorizonUnit,
  }
})