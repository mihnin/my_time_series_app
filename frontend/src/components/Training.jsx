import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useData } from '../contexts/DataContext'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Button } from '@/components/ui/button.jsx'
import { Progress } from '@/components/ui/progress.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Switch } from '@/components/ui/switch.jsx'
import { 
  Play, 
  Pause, 
  Square, 
  TrendingUp, 
  Award,
  Clock,
  CheckCircle,
  AlertCircle,
  Download,
  Database,
  Settings,
  ChevronDown,
  ChevronUp,
  BarChart3
} from 'lucide-react'
import { API_BASE_URL } from '../apiConfig.js'
import DbAutoSavePanel from './training/DbAutoSavePanel.jsx';
import TrainingControl from './training/TrainingControl.jsx';
import ModelLeaderboard from './training/ModelLeaderboard.jsx';
import PycaretModal from './training/PycaretModal.jsx';
import ModelMetricsCards from './training/ModelMetricsCards.jsx';
import { useTrainingLogic } from '../hooks/useTrainingLogic.jsx';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import ForecastChart from './training/ForecastChart.jsx';

export default function Training() {
  const navigate = useNavigate();
  const { 
    uploadedFile, 
    trainingConfig, 
    setSessionId,
    updateTrainingStatus,
    sessionId,
    trainingStatus: globalTrainingStatus,
    totalTrainingTime,
    setTotalTrainingTime,
    authToken,
    setAuthToken,
    predictionProcessed,
    uploadedData, predictionRows
  } = useData();
  const {
    autoSaveEnabled, setAutoSaveEnabled,
    dbUsername, setDbUsername,
    dbPassword, setDbPassword,
    dbConnecting, dbConnected, dbError, dbTables, dbTablesLoading,
    selectedSchema, setSelectedSchema, selectedTable, setSelectedTable,
    saveTableName, setSaveTableName, autoSaveMenuOpen, setAutoSaveMenuOpen,
    saveMode, setSaveMode, newTableName, setNewTableName, autoSaveSettings, uploadTableName,
    handleDbConnect, handleDbInputChange, handleSchemaChange, handleTableChange, handleAutoSaveSetup,
    fileColumns, selectedPrimaryKeys, setSelectedPrimaryKeys,
    setAuthToken: setAuthTokenLocal,
    trainingStatus, setTrainingStatus, progress, setProgress, currentModel, setCurrentModel, elapsedTime, setElapsedTime, statusCheckInterval, setStatusCheckInterval, pycaretModalVisible, setPycaretModalVisible, pycaretLeaderboards, setPycaretLeaderboards, trainingStartTime,
    getTrainingStatus, getStatusMessage, getCurrentProgress, getCurrentModel,
    pollTrainingStatus, handleStartTraining, handleStopTraining,
    openPycaretModal, closePycaretModal, isPycaretRow, hasPycaretData, getStatusBadge, getRankBadge, formatCellValue,
    getBestModel, getBestModelMetric, getAverageMetric, getTotalTrainingTime,
    resetTrainingState
  } = useTrainingLogic({
    uploadedFile,
    trainingConfig,
    setSessionId,
    updateTrainingStatus,
    sessionId,
    globalTrainingStatus,
    setTotalTrainingTime,
    authToken,
    setAuthToken
  });

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground mb-2">Обучение и прогнозирование</h1>
        <p className="text-muted-foreground">
          Запустите процесс обучения моделей и просмотрите результаты прогнозирования
        </p>
      </div>
      <div className="space-y-6">
        <DbAutoSavePanel
          autoSaveEnabled={autoSaveEnabled}
          setAutoSaveEnabled={setAutoSaveEnabled}
          dbUsername={dbUsername}
          setDbUsername={setDbUsername}
          dbPassword={dbPassword}
          setDbPassword={setDbPassword}
          dbConnecting={dbConnecting}
          dbConnected={dbConnected}
          dbError={dbError}
          dbTables={dbTables}
          dbTablesLoading={dbTablesLoading}
          selectedSchema={selectedSchema}
          setSelectedSchema={setSelectedSchema}
          selectedTable={selectedTable}
          setSelectedTable={setSelectedTable}
          saveTableName={saveTableName}
          setSaveTableName={setSaveTableName}
          autoSaveMenuOpen={autoSaveMenuOpen}
          setAutoSaveMenuOpen={setAutoSaveMenuOpen}
          saveMode={saveMode}
          setSaveMode={setSaveMode}
          newTableName={newTableName}
          setNewTableName={setNewTableName}
          autoSaveSettings={autoSaveSettings}
          uploadTableName={uploadTableName}
          handleDbConnect={handleDbConnect}
          handleDbInputChange={handleDbInputChange}
          handleSchemaChange={handleSchemaChange}
          handleTableChange={handleTableChange}
          handleAutoSaveSetup={handleAutoSaveSetup}
          fileColumns={fileColumns}
          selectedPrimaryKeys={selectedPrimaryKeys}
          setSelectedPrimaryKeys={setSelectedPrimaryKeys}
          setAuthToken={setAuthToken}
        />
        <TrainingControl
          getTrainingStatus={getTrainingStatus}
          handleStartTraining={handleStartTraining}
          trainingConfig={trainingConfig}
          uploadedFile={uploadedFile}
          getCurrentProgress={getCurrentProgress}
          elapsedTime={elapsedTime}
          getStatusMessage={getStatusMessage}
          globalTrainingStatus={globalTrainingStatus}
        />
        <ModelLeaderboard
          leaderboard={globalTrainingStatus?.leaderboard}
          trainingParams={globalTrainingStatus?.training_params}
          trainingConfig={trainingConfig}
          isPycaretRow={isPycaretRow}
          hasPycaretData={hasPycaretData}
          openPycaretModal={openPycaretModal}
          formatCellValue={formatCellValue}
        />
        <ForecastChart
            uploadedData={uploadedData}
            predictionRows={predictionRows}
            predictionProcessed={predictionProcessed}
        />
        <ModelMetricsCards
          bestModel={getBestModel()}
          bestModelMetric={getBestModelMetric()}
          averageMetric={getAverageMetric()}
          totalTrainingTime={getTotalTrainingTime()}
          predictionProcessed={predictionProcessed}
        />
        <div className="flex justify-between items-center">
          <Button 
            variant="outline"
            onClick={() => navigate('/config')}
          >
            Назад к конфигурации
          </Button>
          <div className="flex flex-row gap-4">
            <Button 
              variant="outline" 
              className="flex items-center space-x-2"
              onClick={() => navigate('/export')}
              disabled={!predictionProcessed}
              title={predictionProcessed ? '' : 'Сначала выполните прогнозирование'}
            >
              <Download size={16} />
              <span>Скачать результаты</span>
            </Button>
            <Button 
              className="bg-primary hover:bg-primary/90"
              onClick={() => navigate('/analysis')}
              disabled={!uploadedFile}
              title={uploadedFile ? '' : 'Сначала загрузите файл'}
            >
              Перейти к анализу
            </Button>
          </div>
        </div>
      </div>
      <PycaretModal
        visible={pycaretModalVisible}
        closeModal={closePycaretModal}
        pycaretLeaderboards={pycaretLeaderboards}
        formatCellValue={formatCellValue}
      />
    </div>
  )
}
