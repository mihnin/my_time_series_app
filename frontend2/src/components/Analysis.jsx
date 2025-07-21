import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useData } from '../contexts/DataContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { BarChart3, AlertTriangle, PieChart } from 'lucide-react'
import { Button } from '@/components/ui/button.jsx'
import { API_BASE_URL } from '../apiConfig.js'

export default function Analysis() {
  const navigate = useNavigate();
  const { uploadedFile, predictionProcessed, sessionId, analysisCache, setAnalysisCache } = useData()
  const [columns, setColumns] = useState([])
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [missingStats, setMissingStats] = useState({ total: 0, missing: 0, percent: 0 })
  const [missingBins, setMissingBins] = useState([])
  const [dateColIdx, setDateColIdx] = useState(-1)

  // Ключ для кэша: либо sessionId, либо имя файла
  const cacheKey = sessionId ? `session_${sessionId}` : (uploadedFile ? `file_${uploadedFile.name}_${uploadedFile.size}` : null)

  useEffect(() => {
    if (!cacheKey) return;
    // Если есть кэш — подгружаем
    if (analysisCache[cacheKey]) {
      const cached = analysisCache[cacheKey]
      setColumns(cached.columns)
      setRows(cached.rows)
      setDateColIdx(cached.dateColIdx)
      setMissingStats(cached.missingStats)
      setMissingBins(cached.missingBins)
      setError('')
      setLoading(false)
      return
    }
    async function loadData() {
      setLoading(true)
      setError('')
      try {
        let result
        // Логируем параметры перед запросом
        console.log('Analysis request params:', { sessionId, uploadedFile, cacheKey })
        if (sessionId) {
          // Анализ по parquet — НЕ отправляем файл!
          const formData = new FormData()
          formData.append('session_id', sessionId)
          // Для совместимости с pydantic схемой: session_id всегда строка
          const res = await fetch(`${API_BASE_URL}/analyze-data`, {
            method: 'POST',
            body: formData
          })
          if (!res.ok) throw new Error((await res.json()).detail || 'Ошибка анализа')
          result = await res.json()
        } else if (uploadedFile) {
          // Анализ по файлу (если sessionId нет)
          const formData = new FormData()
          formData.append('file', uploadedFile)
          const res = await fetch(`${API_BASE_URL}/analyze-data`, {
            method: 'POST',
            body: formData
          })
          if (!res.ok) throw new Error((await res.json()).detail || 'Ошибка анализа')
          result = await res.json()
        } else {
          setError('Нет данных для анализа')
          setLoading(false)
          return
        }
        setColumns(result.columns)
        setRows(result.rows)
        const dateIdx = result.columns.findIndex(col => /date|время|time/i.test(col))
        setDateColIdx(dateIdx)
        const stats = {
          total: result.total,
          missing: result.missing,
          percent: result.percent
        }
        setMissingStats(stats)
        setMissingBins(result.bins)
        // Сохраняем в кэш
        setAnalysisCache(prev => ({
          ...prev,
          [cacheKey]: {
            columns: result.columns,
            rows: result.rows,
            dateColIdx: dateIdx,
            missingStats: stats,
            missingBins: result.bins
          }
        }))
      } catch (e) {
        setError(e.message || 'Ошибка анализа файла')
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [uploadedFile, sessionId])

  // Сброс кэша при загрузке нового файла
  useEffect(() => {
    if (!uploadedFile && !sessionId) {
      setAnalysisCache({})
    }
  }, [uploadedFile, sessionId])

  // вынесем функцию для обновления анализа
  const handleRefresh = () => {
    setLoading(true)
    setTimeout(() => setLoading(false), 10)
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground mb-2">Анализ данных</h1>
        <p className="text-muted-foreground">Обзор пропусков в исходных данных</p>
      </div>
      {loading ? (
        <div className="flex items-center justify-center h-40">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary"></div>
          <span className="ml-2 text-lg text-muted-foreground">Анализ данных...</span>
        </div>
      ) : error ? <div className="text-red-500">{error}</div> : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <BarChart3 className="text-primary" size={20} />
                  <span>Всего записей</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-primary">{missingStats.total}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <AlertTriangle className="text-orange-500" size={20} />
                  <span>Всего пропусков</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-orange-600">{missingStats.missing}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <PieChart className="text-blue-400" size={20} />
                  <span>Процент пропусков</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-blue-600">{missingStats.percent.toFixed(2)}%</div>
              </CardContent>
            </Card>
          </div>
          <Card>
            <CardHeader>
              <CardTitle>Пропуски по времени (12 интервалов)</CardTitle>
            </CardHeader>
            <CardContent style={{ height: 320 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={missingBins}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="missing" fill="#f59e42" name="Пропуски" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
          <div className="flex justify-between items-center mt-8">
            <Button
              variant="outline"
              onClick={() => navigate('/training')}
            >
              Назад к обучению
            </Button>
            <Button
              variant="outline"
              onClick={handleRefresh}
            >
              Обновить анализ
            </Button>
            <Button
              variant="default"
              onClick={() => navigate('/export')}
              disabled={!predictionProcessed}
              title={predictionProcessed ? '' : 'Сначала выполните прогнозирование'}
            >
              Перейти к экспорту
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

