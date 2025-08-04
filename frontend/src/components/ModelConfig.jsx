import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useData } from '../contexts/DataContext'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select.jsx'
import { Checkbox } from '@/components/ui/checkbox.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.jsx'
import { 
  Settings, 
  Calendar, 
  Target, 
  Hash,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Info
} from 'lucide-react'

export default function ModelConfig() {
  const navigate = useNavigate()
  const { uploadedData, dataSource, selectedTable, updateTrainingConfig, trainingConfig } = useData()
  
  const [config, setConfig] = useState({
    dateColumn: '',
    targetColumn: '',
    idColumn: '',
    frequency: 'D',
    missingValueMethod: 'forward_fill',
    selectedAutogluonModels: ['*'], // По умолчанию "Все модели"
    selectedPycaretModels: [], // По умолчанию ничего не выбрано
    selectedMetric: 'mae', // Одна выбранная метрика
    forecastHorizon: 30,
    staticFeatures: [],
    considerHolidays: false,
    groupingColumns: [],
    autogluonPreset: 'medium_quality', // Пресет AutoGluon
    trainingTimeLimit: 60 // Максимальное время обучения в секундах
  })

  const [selectedFeatureToAdd, setSelectedFeatureToAdd] = useState('none')
  const [selectedGroupingColumn, setSelectedGroupingColumn] = useState('none')
  const [selectedAutogluonModelToAdd, setSelectedAutogluonModelToAdd] = useState('none')
  const [selectedPycaretModelToAdd, setSelectedPycaretModelToAdd] = useState('none')

  // Инициализация конфигурации из сохраненного состояния
  useEffect(() => {
    if (trainingConfig) {
      setConfig(trainingConfig)
    }
  }, []) // Загружаем только при монтировании компонента

  // Автосохранение конфигурации при каждом изменении
  useEffect(() => {
    // Избегаем сохранения при первой загрузке
    if (config.dateColumn || config.targetColumn) {
      updateTrainingConfig(config)
    }
  }, [config, updateTrainingConfig])

  // Получаем доступные колонки из загруженных данных
  const availableColumns = uploadedData && uploadedData.columns ? uploadedData.columns : [
    'date', 'timestamp', 'value', 'metric_value', 'temperature', 
    'pressure', 'id', 'sensor_id', 'location', 'category'
  ]

  const frequencyOptions = [
    { value: 'D', label: 'Дневная (D)' },
    { value: 'W', label: 'Недельная (W)' },
    { value: 'M', label: 'Месячная (M)' },
    { value: 'Q', label: 'Квартальная (Q)' },
    { value: 'Y', label: 'Годовая (Y)' },
    { value: 'H', label: 'Часовая (H)' },
    { value: 'T', label: 'Минутная (T)' }
  ]

  const missingValueMethods = [
    { value: 'constant_zero', label: 'Constant=0 (заменить на нули)' },
    { value: 'group_mean', label: 'Group mean (среднее по группе)' },
    { value: 'forward_fill', label: 'Forward fill (протянуть значения)' },
    { value: 'interpolate', label: 'Interpolate (линейная интерполяция)' },
    { value: 'knn_imputer', label: 'KNN imputer (k ближайших соседей)' }
  ]

  const modelOptions = {
    autogluon: [
      { id: '*', label: 'Все модели', description: 'Использовать все доступные AutoGluon модели' },
      { id: 'NaiveModel', label: 'Naive Model', description: 'Базовая модель: прогноз = последнее наблюдение' },
      { id: 'SeasonalNaiveModel', label: 'Seasonal Naive', description: 'Прогноз = последнее значение той же фазы сезона' },
      { id: 'AverageModel', label: 'Average Model', description: 'Прогноз = среднее/квантиль' },
      { id: 'SeasonalAverageModel', label: 'Seasonal Average', description: 'Прогноз = среднее по тем же фазам сезона' },
      { id: 'ZeroModel', label: 'Zero Model', description: 'Прогноз = 0' },
      { id: 'ETSModel', label: 'ETS Model', description: 'Экспоненциальное сглаживание (ETS)' },
      { id: 'AutoARIMAModel', label: 'Auto ARIMA', description: 'Автоматическая ARIMA' },
      { id: 'AutoETSModel', label: 'Auto ETS', description: 'Автоматическая ETS' },
      { id: 'AutoCESModel', label: 'Auto CES', description: 'Комплексное экспоненциальное сглаживание (AIC)' },
      { id: 'ThetaModel', label: 'Theta Model', description: 'Theta' },
      { id: 'ADIDAModel', label: 'ADIDA', description: 'Intermittent demand (ADIDA)' },
      { id: 'CrostonModel', label: 'Croston', description: 'Intermittent demand (Croston)' },
      { id: 'IMAPAModel', label: 'IMAPA', description: 'Intermittent demand (IMAPA)' },
      { id: 'NPTSModel', label: 'NPTS', description: 'Non-Parametric Time Series' },
      { id: 'DeepARModel', label: 'DeepAR', description: 'RNN (DeepAR)' },
      { id: 'DLinearModel', label: 'DLinear', description: 'DLinear (убирает тренд)' },
      { id: 'PatchTSTModel', label: 'PatchTST', description: 'PatchTST (Transformer)' },
      { id: 'SimpleFeedForwardModel', label: 'Feed Forward', description: 'Простая полносвязная сеть' },
      { id: 'TemporalFusionTransformerModel', label: 'TFT', description: 'LSTM + Transformer (TFT)' },
      { id: 'TiDEModel', label: 'TiDE', description: 'Time series dense encoder' },
      { id: 'WaveNetModel', label: 'WaveNet', description: 'WaveNet (CNN)' },
      { id: 'DirectTabularModel', label: 'Direct Tabular', description: 'AutoGluon-Tabular (Direct)' },
      { id: 'RecursiveTabularModel', label: 'Recursive Tabular', description: 'AutoGluon-Tabular (Recursive)' },
      { id: 'Chronos', label: 'Chronos', description: 'Chronos Bolt model pretrained' }
    ],
    pycaret: [
      { id: '*', label: 'Все модели', description: 'Использовать все доступные PyCaret модели' },
      { id: 'naive', label: 'Naive Forecaster', description: 'Простейший прогноз' },
      { id: 'grand_means', label: 'Grand Means', description: 'Прогноз по общему среднему' },
      { id: 'snaive', label: 'Seasonal Naive', description: 'Сезонный наивный прогноз' },
      { id: 'polytrend', label: 'Polynomial Trend', description: 'Полиномиальный тренд' },
      { id: 'arima', label: 'ARIMA', description: 'Авторегрессионная интегрированная модель скользящего среднего' },
      { id: 'exp_smooth', label: 'Exponential Smoothing', description: 'Экспоненциальное сглаживание' },
      { id: 'ets', label: 'ETS', description: 'Error, Trend, Seasonality' },
      { id: 'theta', label: 'Theta Forecaster', description: 'Theta модель' },
      { id: 'stlf', label: 'STLF', description: 'STL Forecaster' },
      { id: 'croston', label: 'Croston', description: 'Модель Кростона' },
      { id: 'bats', label: 'BATS', description: 'Box-Cox transform, ARMA errors, Trend, Seasonal' },
      { id: 'tbats', label: 'TBATS', description: 'Trigonometric, Box-Cox, ARMA, Trend, Seasonal' },
      { id: 'lr_cds_dt', label: 'Linear Regression', description: 'Линейная регрессия с обработкой' },
      { id: 'en_cds_dt', label: 'Elastic Net', description: 'Elastic Net с обработкой' },
      { id: 'ridge_cds_dt', label: 'Ridge', description: 'Ridge регрессия с обработкой' },
      { id: 'lasso_cds_dt', label: 'Lasso', description: 'Lasso регрессия с обработкой' },
      { id: 'rf_cds_dt', label: 'Random Forest', description: 'Случайный лес с обработкой' },
      { id: 'xgboost_cds_dt', label: 'XGBoost', description: 'Extreme Gradient Boosting с обработкой' },
      { id: 'lightgbm_cds_dt', label: 'LightGBM', description: 'Light Gradient Boosting с обработкой' },
      { id: 'catboost_cds_dt', label: 'CatBoost', description: 'CatBoost регрессор с обработкой' }
    ]
  }

  const metricOptions = [
    { id: 'mae', label: 'MAE', description: 'Mean Absolute Error' },
    { id: 'mape', label: 'MAPE', description: 'Mean Absolute Percentage Error' },
    { id: 'mase', label: 'MASE', description: 'Mean Absolute Scaled Error' },
    { id: 'mse', label: 'MSE', description: 'Mean Squared Error' },
    { id: 'rmse', label: 'RMSE', description: 'Root Mean Squared Error' },
    { id: 'rmsse', label: 'RMSSE', description: 'Root Mean Squared Scaled Error' },
    { id: 'smape', label: 'SMAPE', description: 'Symmetric Mean Absolute Percentage Error' }
  ]

  const presetsList = [
    { id: 'fast_training', label: 'Быстрое обучение', description: 'Быстрая тренировка, базовые модели' },
    { id: 'medium_quality', label: 'Среднее качество', description: 'Баланс скорости и качества' },
    { id: 'high_quality', label: 'Высокое качество', description: 'Более точные модели, больше времени' },
    { id: 'best_quality', label: 'Лучшее качество', description: 'Максимальное качество, долгое обучение' }
  ]

  const handleConfigChange = (field, value) => {
    // Преобразуем "none" в пустую строку для ID колонки
    const processedValue = (field === 'idColumn' && value === 'none') ? '' : value
    
    // Если изменяется метод обработки пропусков, сбрасываем группировочные колонки
    if (field === 'missingValueMethod') {
      setConfig(prev => ({ 
        ...prev, 
        [field]: processedValue,
        groupingColumns: [] // Сбрасываем группировочные колонки
      }))
      setSelectedGroupingColumn('none') // Сбрасываем выбор
    } else {
      setConfig(prev => ({ ...prev, [field]: processedValue }))
    }
  }

  const handleModelToggle = (modelId, framework) => {
    const fieldName = framework === 'autogluon' ? 'selectedAutogluonModels' : 'selectedPycaretModels'
    setConfig(prev => ({
      ...prev,
      [fieldName]: prev[fieldName].includes(modelId)
        ? prev[fieldName].filter(id => id !== modelId)
        : [...prev[fieldName], modelId]
    }))
  }

  const handleModelAdd = (modelId, framework) => {
    if (modelId && modelId !== 'none') {
      const fieldName = framework === 'autogluon' ? 'selectedAutogluonModels' : 'selectedPycaretModels'
      
      setConfig(prev => {
        const currentModels = prev[fieldName]
        
        // Если выбирают "Все модели"
        if (modelId === '*') {
          return { ...prev, [fieldName]: ['*'] }
        }
        
        // Если уже выбраны "Все модели", заменяем на конкретную модель
        if (currentModels.includes('*')) {
          return { ...prev, [fieldName]: [modelId] }
        }
        
        // Если модель уже выбрана, не добавляем
        if (currentModels.includes(modelId)) {
          return prev
        }
        
        // Добавляем модель к существующим
        return { ...prev, [fieldName]: [...currentModels, modelId] }
      })
      
      // Сбрасываем селектор
      if (framework === 'autogluon') {
        setSelectedAutogluonModelToAdd('none')
      } else {
        setSelectedPycaretModelToAdd('none')
      }
    }
  }

  const handleModelRemove = (modelId, framework) => {
    const fieldName = framework === 'autogluon' ? 'selectedAutogluonModels' : 'selectedPycaretModels'
    setConfig(prev => ({
      ...prev,
      [fieldName]: prev[fieldName].filter(id => id !== modelId)
    }))
  }

  const handleStaticFeatureAdd = (feature) => {
    if (feature && feature !== 'none' && config.staticFeatures.length < 3 && !config.staticFeatures.includes(feature)) {
      setConfig(prev => ({
        ...prev,
        staticFeatures: [...prev.staticFeatures, feature]
      }))
      setSelectedFeatureToAdd('none') // Сбрасываем выбор
    }
  }

  const handleStaticFeatureRemove = (feature) => {
    setConfig(prev => ({
      ...prev,
      staticFeatures: prev.staticFeatures.filter(f => f !== feature),
      // Удаляем из группировочных колонок, если он там был
      groupingColumns: prev.groupingColumns.filter(c => c !== feature)
    }))
  }

  const handleGroupingColumnAdd = (column) => {
    if (column && column !== 'none' && !config.groupingColumns.includes(column)) {
      setConfig(prev => ({
        ...prev,
        groupingColumns: [...prev.groupingColumns, column]
      }))
      setSelectedGroupingColumn('none') // Сбрасываем выбор
    }
  }

  const handleGroupingColumnRemove = (column) => {
    setConfig(prev => ({
      ...prev,
      groupingColumns: prev.groupingColumns.filter(c => c !== column)
    }))
  }

  // Получаем доступные статические признаки (исключая уже выбранные колонки)
  const availableStaticFeatures = availableColumns.filter(column => 
    column !== config.dateColumn &&
    column !== config.targetColumn &&
    (config.idColumn ? column !== config.idColumn : true) &&
    !config.staticFeatures.includes(column)
  )

  // Доступные колонки для группировки (из статических признаков)
  const availableGroupingColumns = config.staticFeatures.filter(column => 
    !config.groupingColumns.includes(column)
  )

  // Доступные модели для добавления
  const availableAutogluonModels = modelOptions.autogluon.filter(model => 
    !config.selectedAutogluonModels.includes(model.id)
  )

  const availablePycaretModels = modelOptions.pycaret.filter(model => 
    !config.selectedPycaretModels.includes(model.id)
  )

  const isConfigValid = config.dateColumn && config.targetColumn && 
                       (config.selectedAutogluonModels.length > 0 || config.selectedPycaretModels.length > 0) && 
                       config.selectedMetric

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground mb-2">Конфигурация модели</h1>
        <p className="text-muted-foreground">
          Настройте параметры для обучения модели прогнозирования временных рядов
        </p>
      </div>

      <div className="space-y-6">
        {/* Column Selection */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Settings className="text-primary" size={20} />
              <span>Выбор колонок</span>
            </CardTitle>
            <CardDescription>
              Укажите колонки для даты, целевой переменной и идентификатора
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label className="flex items-center space-x-2">
                  <Calendar size={16} className="text-primary" />
                  <span>Колонка даты *</span>
                </Label>
                <Select value={config.dateColumn} onValueChange={(value) => handleConfigChange('dateColumn', value)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Выберите колонку даты" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableColumns.map(column => (
                      <SelectItem key={column} value={column}>{column}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label className="flex items-center space-x-2">
                  <Target size={16} className="text-primary" />
                  <span>Целевая переменная *</span>
                </Label>
                <Select value={config.targetColumn} onValueChange={(value) => handleConfigChange('targetColumn', value)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Выберите целевую переменную" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableColumns.map(column => (
                      <SelectItem key={column} value={column}>{column}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label className="flex items-center space-x-2">
                  <Hash size={16} className="text-primary" />
                  <span>ID колонка *</span>
                </Label>
                <Select value={config.idColumn || 'none'} onValueChange={(value) => handleConfigChange('idColumn', value)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Выберите ID колонку (опционально)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Не выбрана</SelectItem>
                    {availableColumns.map(column => (
                      <SelectItem key={column} value={column}>{column}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Статические признаки */}
            <div className="space-y-4">
              <div className="space-y-2">
                <Label className="text-base font-medium">Статические признаки (до 3)</Label>
                <p className="text-sm text-muted-foreground">
                  Выберите дополнительные признаки для улучшения качества прогноза
                </p>
              </div>

              {/* Выбранные признаки */}
              {config.staticFeatures.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {config.staticFeatures.map((feature) => (
                    <div key={feature} className="flex items-center bg-blue-50 text-blue-700 px-3 py-1 rounded-full text-sm">
                      <span>{feature}</span>
                      <button
                        onClick={() => handleStaticFeatureRemove(feature)}
                        className="ml-2 text-blue-500 hover:text-blue-700 font-bold"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* Селектор для добавления признаков */}
              <Select 
                value={selectedFeatureToAdd}
                onValueChange={(value) => {
                  setSelectedFeatureToAdd(value)
                  handleStaticFeatureAdd(value)
                }}
                disabled={config.staticFeatures.length >= 3}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Выберите признак для добавления" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Выберите признак</SelectItem>
                  {availableStaticFeatures.map(column => (
                    <SelectItem key={column} value={column}>{column}</SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* Чекбокс для праздников */}
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="holidays"
                  checked={config.considerHolidays}
                  onCheckedChange={(checked) => handleConfigChange('considerHolidays', checked)}
                />
                <Label htmlFor="holidays" className="text-sm font-normal cursor-pointer">
                  Учитывать праздники РФ
                </Label>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Data Processing */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <AlertTriangle className="text-primary" size={20} />
              <span>Обработка данных</span>
            </CardTitle>
            <CardDescription>
              Настройте частоту данных и методы обработки пропусков
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Частота данных</Label>
                <Select value={config.frequency} onValueChange={(value) => handleConfigChange('frequency', value)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {frequencyOptions.map(option => (
                      <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Метод обработки пропусков</Label>
                <Select value={config.missingValueMethod} onValueChange={(value) => handleConfigChange('missingValueMethod', value)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {missingValueMethods.map(method => (
                      <SelectItem key={method.value} value={method.value}>{method.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Группировочные колонки для Group mean */}
            {config.missingValueMethod === 'group_mean' && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Колонки для группировки</Label>
                  <p className="text-sm text-muted-foreground">
                    Выберите колонки для вычисления среднего значения по группам
                  </p>
                </div>

                {/* Выбранные группировочные колонки */}
                {config.groupingColumns.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {config.groupingColumns.map((column) => (
                      <div key={column} className="flex items-center bg-blue-50 text-blue-700 px-3 py-1 rounded-full text-sm">
                        <span>{column}</span>
                        <button
                          onClick={() => handleGroupingColumnRemove(column)}
                          className="ml-2 text-blue-500 hover:text-blue-700 font-bold"
                          type="button"
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Селектор для добавления группировочных колонок */}
                <Select 
                  value={selectedGroupingColumn}
                  onValueChange={(value) => {
                    setSelectedGroupingColumn(value)
                    handleGroupingColumnAdd(value)
                  }}
                  disabled={availableGroupingColumns.length === 0}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Выберите колонку для добавления" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Выберите колонку</SelectItem>
                    {availableGroupingColumns.map(column => (
                      <SelectItem key={column} value={column}>{column}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {/* Сообщение, если нет доступных статических признаков */}
                {config.staticFeatures.length === 0 && (
                  <div className="text-sm text-amber-600 bg-amber-50 p-3 rounded-md border border-amber-200">
                    <p>
                      Для группировки по среднему значению необходимо выбрать статические признаки в разделе выше.
                    </p>
                  </div>
                )}
              </div>
            )}

            <div className="space-y-2">
              <Label>Горизонт прогнозирования (периоды)</Label>
              <Input
                type="number"
                value={config.forecastHorizon}
                onChange={(e) => handleConfigChange('forecastHorizon', parseInt(e.target.value))}
                min="1"
                max="365"
              />
            </div>
          </CardContent>
        </Card>

        {/* Model Selection */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <TrendingUp className="text-primary" size={20} />
              <span>Выбор моделей</span>
            </CardTitle>
            <CardDescription>
              Выберите модели для обучения и сравнения
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* AutoGluon Models */}
            <div className="space-y-4">
              <div className="space-y-2">
                <Label className="text-lg font-semibold text-foreground">AutoGluon модели</Label>
                <p className="text-sm text-muted-foreground">
                  Модели из библиотеки AutoGluon для временных рядов
                </p>
              </div>

              {/* Выбранные AutoGluon модели */}
              {config.selectedAutogluonModels.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {config.selectedAutogluonModels.map((modelId) => {
                    const model = modelOptions.autogluon.find(m => m.id === modelId)
                    return (
                      <div key={modelId} className="flex items-center bg-blue-50 text-blue-700 px-3 py-1 rounded-full text-sm">
                        <span>{model?.label || modelId}</span>
                        <button
                          onClick={() => handleModelRemove(modelId, 'autogluon')}
                          className="ml-2 text-blue-500 hover:text-blue-700 font-bold"
                          type="button"
                        >
                          ×
                        </button>
                      </div>
                    )
                  })}
                </div>
              )}

              {/* Селекторы для добавления AutoGluon моделей и пресета */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Добавить модель</Label>
                  <Select 
                    value={selectedAutogluonModelToAdd}
                    onValueChange={(value) => {
                      setSelectedAutogluonModelToAdd(value)
                      handleModelAdd(value, 'autogluon')
                    }}
                    disabled={availableAutogluonModels.length === 0}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Выберите модель для добавления" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Выберите модель</SelectItem>
                      {availableAutogluonModels.map(model => (
                        <SelectItem key={model.id} value={model.id}>{model.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label>Пресет AutoGluon</Label>
                  <Select 
                    value={config.autogluonPreset} 
                    onValueChange={(value) => handleConfigChange('autogluonPreset', value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Выберите пресет">
                        {config.autogluonPreset ? presetsList.find(p => p.id === config.autogluonPreset)?.label : "Выберите пресет"}
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                      {presetsList.map(preset => (
                        <SelectItem key={preset.id} value={preset.id}>
                          <div className="flex flex-col">
                            <span className="font-medium">{preset.label}</span>
                            <span className="text-xs text-muted-foreground">{preset.description}</span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>

            {/* PyCaret Models */}
            <div className="space-y-4">
              <div className="space-y-2">
                <Label className="text-lg font-semibold text-foreground">PyCaret модели</Label>
                <p className="text-sm text-muted-foreground">
                  Модели из библиотеки PyCaret для временных рядов
                </p>
              </div>

              {/* Выбранные PyCaret модели */}
              {config.selectedPycaretModels.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {config.selectedPycaretModels.map((modelId) => {
                    const model = modelOptions.pycaret.find(m => m.id === modelId)
                    return (
                      <div key={modelId} className="flex items-center bg-green-50 text-green-700 px-3 py-1 rounded-full text-sm">
                        <span>{model?.label || modelId}</span>
                        <button
                          onClick={() => handleModelRemove(modelId, 'pycaret')}
                          className="ml-2 text-green-500 hover:text-green-700 font-bold"
                          type="button"
                        >
                          ×
                        </button>
                      </div>
                    )
                  })}
                </div>
              )}

              {/* Селектор для добавления PyCaret моделей */}
              <Select 
                value={selectedPycaretModelToAdd}
                onValueChange={(value) => {
                  setSelectedPycaretModelToAdd(value)
                  handleModelAdd(value, 'pycaret')
                }}
                disabled={availablePycaretModels.length === 0}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Выберите модель для добавления" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Выберите модель</SelectItem>
                  {availablePycaretModels.map(model => (
                    <SelectItem key={model.id} value={model.id}>{model.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Additional Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Settings className="text-primary" size={20} />
              <span>Дополнительные настройки</span>
            </CardTitle>
            <CardDescription>
              Настройки метрики качества и ограничения времени обучения
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Метрика оценки качества</Label>
                <Select 
                  value={config.selectedMetric} 
                  onValueChange={(value) => handleConfigChange('selectedMetric', value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Выберите метрику">
                      {config.selectedMetric ? metricOptions.find(m => m.id === config.selectedMetric)?.label : "Выберите метрику"}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {metricOptions.map(metric => (
                      <SelectItem key={metric.id} value={metric.id}>
                        <div className="flex flex-col">
                          <span className="font-medium">{metric.label}</span>
                          <span className="text-xs text-muted-foreground">{metric.description}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <Label>Максимальное время обучения (секунды)</Label>
                <Input
                  type="number"
                  min="30"
                  max="3600"
                  value={config.trainingTimeLimit}
                  onChange={(e) => handleConfigChange('trainingTimeLimit', parseInt(e.target.value) || 60)}
                  placeholder="60"
                />
                <p className="text-xs text-muted-foreground">
                  Ограничение времени на обучение всех моделей (от 30 до 3600 секунд)
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Configuration Summary */}
        {isConfigValid && (
          <Card className="bg-green-50 border-green-200">
            <CardHeader>
              <CardTitle className="flex items-center space-x-2 text-green-800">
                <Info className="text-green-600" size={20} />
                <span>Сводка конфигурации</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="text-green-700">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div>
                  <p><strong>Источник данных:</strong> {dataSource === 'file' ? 'Файл' : dataSource === 'database' ? `БД (${selectedTable})` : 'Не загружено'}</p>
                  <p><strong>Колонка даты:</strong> {config.dateColumn}</p>
                  <p><strong>Целевая переменная:</strong> {config.targetColumn}</p>
                  <p><strong>ID колонка:</strong> {config.idColumn || 'Не выбрана'}</p>
                  {config.staticFeatures.length > 0 && (
                    <p><strong>Статические признаки:</strong> {config.staticFeatures.join(', ')}</p>
                  )}
                  {config.considerHolidays && (
                    <p><strong>Праздники РФ:</strong> Учитываются</p>
                  )}
                </div>
                <div>
                  <p><strong>Частота:</strong> {frequencyOptions.find(f => f.value === config.frequency)?.label}</p>
                  <p><strong>Метод обработки пропусков:</strong> {missingValueMethods.find(m => m.value === config.missingValueMethod)?.label}</p>
                  {config.missingValueMethod === 'group_mean' && config.groupingColumns.length > 0 && (
                    <p><strong>Группировка по:</strong> {config.groupingColumns.join(', ')}</p>
                  )}
                  <p><strong>Горизонт прогноза:</strong> {config.forecastHorizon} периодов</p>
                  <p><strong>Выбрано AutoGluon моделей:</strong> {config.selectedAutogluonModels.length}</p>
                  <p><strong>Пресет AutoGluon:</strong> {presetsList.find(p => p.id === config.autogluonPreset)?.label}</p>
                  <p><strong>Выбрано PyCaret моделей:</strong> {config.selectedPycaretModels.length}</p>
                  <p><strong>Метрика качества:</strong> {metricOptions.find(m => m.id === config.selectedMetric)?.label}</p>
                  <p><strong>Время обучения:</strong> {config.trainingTimeLimit} секунд</p>
                  {uploadedData && uploadedData.rows && (
                    <p><strong>Строк данных:</strong> {uploadedData.rows.length}</p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Action Buttons */}
        <div className="flex justify-between">
          <Button 
            variant="outline"
            onClick={() => navigate('/upload')}
          >
            Назад к загрузке данных
          </Button>
          <Button 
            className="bg-primary hover:bg-primary/90"
            disabled={!isConfigValid}
            onClick={() => {
              updateTrainingConfig(config)
              navigate('/training')
            }}
          >
            Продолжить к обучению
          </Button>
        </div>
      </div>
    </div>
  )
}

