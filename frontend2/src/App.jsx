import { useState } from 'react'
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { 
  Home, 
  Upload, 
  Settings, 
  TrendingUp, 
  BarChart3, 
  Download,
  Database,
  Play,
  FileText
} from 'lucide-react'
import './App.css'
import { DataProvider, useData } from './contexts/DataContext'

// Import page components (to be created)
import Dashboard from './components/Dashboard'
import DataUpload from './components/DataUpload'
import ModelConfig from './components/ModelConfig'
import Training from './components/Training'
import Analysis from './components/Analysis'
import Export from './components/Export'
import DbSettingsButton from './components/DbSettingsButton';
import DbWork from './components/dbWork.jsx';

// Protected Route wrapper component
function ProtectedRoute({ children, requiresTraining = false }) {
  const { uploadedFile, trainingStatus } = useData()
  
  if (!uploadedFile) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="text-center">
          <div className="mb-6">
            <Upload className="mx-auto h-12 w-12 text-gray-400" />
          </div>
          <h1 className="text-2xl font-bold text-foreground mb-2">Файл не загружен</h1>
          <p className="text-muted-foreground mb-6">
            Для доступа к этой странице необходимо сначала загрузить файл данных.
          </p>
          <Link to="/upload">
            <Button className="bg-primary hover:bg-primary/90">
              Перейти к загрузке данных
            </Button>
          </Link>
        </div>
      </div>
    )
  }
  
  if (requiresTraining && (!trainingStatus || !['completed', 'complete'].includes(trainingStatus.status))) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="text-center">
          <div className="mb-6">
            <Play className="mx-auto h-12 w-12 text-gray-400" />
          </div>
          <h1 className="text-2xl font-bold text-foreground mb-2">Обучение не завершено</h1>
          <p className="text-muted-foreground mb-6">
            Для доступа к этой странице необходимо сначала завершить обучение модели.
          </p>
          <Link to="/training">
            <Button className="bg-primary hover:bg-primary/90">
              Перейти к обучению
            </Button>
          </Link>
        </div>
      </div>
    )
  }
  
  return children
}

function Navigation() {
  const location = useLocation()
  const { uploadedFile, trainingStatus } = useData()
  
  const navItems = [
    { path: '/', icon: Home, label: 'Главная', description: 'Дашборд', requiresFile: false, requiresTraining: false },
    { path: '/upload', icon: Upload, label: 'Загрузка данных', description: 'CSV, Excel, PostgreSQL', requiresFile: false, requiresTraining: false },
    { path: '/config', icon: Settings, label: 'Конфигурация', description: 'Настройка модели', requiresFile: true, requiresTraining: false },
    { path: '/training', icon: Play, label: 'Обучение', description: 'Запуск и мониторинг', requiresFile: true, requiresTraining: false },
    { path: '/analysis', icon: BarChart3, label: 'Анализ данных', description: 'Статистика и визуализация', requiresFile: true, requiresTraining: false },
    { path: '/export', icon: Download, label: 'Экспорт', description: 'Сохранение результатов', requiresFile: false, requiresTraining: true },
    { path: '/dbwork', icon: Database, label: 'Работа с БД', description: 'Загрузка и выгрузка таблиц', requiresFile: false, requiresTraining: false }
  ]

  return (
    <nav className="w-64 bg-sidebar border-r border-sidebar-border p-4 relative">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-primary mb-2">Logo</h1>
        <p className="text-sm text-muted-foreground">Прогнозирование временных рядов</p>
      </div>
      
      <div className="space-y-2">
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = location.pathname === item.path
          const isFileDisabled = item.requiresFile && !uploadedFile
          const isTrainingDisabled = item.requiresTraining && (!trainingStatus || !['completed', 'complete'].includes(trainingStatus.status))
          const isDisabled = isFileDisabled || isTrainingDisabled
          
          // Определяем сообщение для отключенного элемента
          let disabledMessage = ''
          if (isFileDisabled) {
            disabledMessage = 'Требуется загруженный файл'
          } else if (isTrainingDisabled) {
            disabledMessage = 'Требуется завершенное обучение'
          }
          
          return (
            <div key={item.path}>
              {isDisabled ? (
                <div className="flex items-center space-x-3 p-3 rounded-lg opacity-50 cursor-not-allowed">
                  <Icon size={20} />
                  <div>
                    <div className="font-medium">{item.label}</div>
                    <div className="text-xs opacity-70">{disabledMessage}</div>
                  </div>
                </div>
              ) : (
                <Link
                  to={item.path}
                  className={`flex items-center space-x-3 p-3 rounded-lg transition-colors ${
                    isActive 
                      ? 'bg-sidebar-primary text-sidebar-primary-foreground' 
                      : 'text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground'
                  }`}
                >
                  <Icon size={20} />
                  <div>
                    <div className="font-medium">{item.label}</div>
                    <div className="text-xs opacity-70">{item.description}</div>
                  </div>
                </Link>
              )}
            </div>
          )
        })}
      </div>
      {/* Кнопка настроек в левом нижнем углу */}
      <DbSettingsButton />
    </nav>
  )
}

function AppContent() {
  return (
    <div className="flex h-screen bg-background">
      <Navigation />
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/upload" element={<DataUpload />} />
          <Route path="/config" element={
            <ProtectedRoute>
              <ModelConfig />
            </ProtectedRoute>
          } />
          <Route path="/training" element={
            <ProtectedRoute>
              <Training />
            </ProtectedRoute>
          } />
          <Route path="/analysis" element={
            <ProtectedRoute>
              <Analysis />
            </ProtectedRoute>
          } />
          <Route path="/export" element={
            <ProtectedRoute requiresTraining={true}>
              <Export />
            </ProtectedRoute>
          } />
          <Route path="/dbwork" element={<DbWork />} />
        </Routes>
      </main>
    </div>
  )
}

function App() {
  return (
    <DataProvider>
      <Router>
        <AppContent />
      </Router>
    </DataProvider>
  )
}

export default App

