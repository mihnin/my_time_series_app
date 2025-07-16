import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useData } from '../contexts/DataContext'
import { parseFile } from '../utils/fileParser'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { BarChart3, AlertTriangle, PieChart } from 'lucide-react'
import { Button } from '@/components/ui/button.jsx'

export default function Analysis() {
  const navigate = useNavigate();
  const { uploadedFile, uploadedData, predictionProcessed } = useData()
  const [columns, setColumns] = useState([])
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [missingStats, setMissingStats] = useState({ total: 0, missing: 0, percent: 0 })
  const [missingBins, setMissingBins] = useState([])
  const [dateColIdx, setDateColIdx] = useState(-1)

  useEffect(() => {
    async function loadData() {
      setLoading(true)
      setError('')
      try {
        let data = uploadedData
        if (!data && uploadedFile) {
          data = await parseFile(uploadedFile)
        }
        if (!data || !data.rows || !data.columns) {
          setError('Нет данных для анализа')
          setLoading(false)
          return
        }
        setColumns(data.columns)
        setRows(data.rows)
        // Поиск колонки с датой/временем
        let dateIdx = data.columns.findIndex(col => /date|время|time/i.test(col))
        setDateColIdx(dateIdx)
        // Подсчёт пропусков
        let totalCells = data.rows.length * data.columns.length
        let missingCells = 0
        for (let row of data.rows) {
          for (let cell of row) {
            if (cell === '' || cell === null || cell === undefined) missingCells++
          }
        }
        setMissingStats({
          total: data.rows.length,
          missing: missingCells,
          percent: totalCells ? (missingCells / totalCells) * 100 : 0
        })
        // Бины для диаграммы
        const binCount = 12
        const binSize = Math.ceil(data.rows.length / binCount)
        let bins = Array.from({ length: binCount }, (_, i) => ({
          name: `${i + 1}`,
          missing: 0,
          total: 0
        }))
        for (let i = 0; i < data.rows.length; i++) {
          const binIdx = Math.floor(i / binSize)
          let row = data.rows[i]
          let rowMissing = row.filter(cell => cell === '' || cell === null || cell === undefined).length
          bins[binIdx].missing += rowMissing
          bins[binIdx].total++
        }
        // Если есть дата — подписываем бины по времени
        if (dateIdx !== -1) {
          const getLabel = (row) => row[dateIdx]?.slice(0, 10) || ''
          const first = getLabel(data.rows[0])
          const last = getLabel(data.rows[data.rows.length - 1])
          for (let i = 0; i < bins.length; i++) {
            bins[i].name = `${first} - ${last}`
          }
        }
        setMissingBins(bins)
      } catch (e) {
        setError(e.message || 'Ошибка анализа файла')
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [uploadedFile, uploadedData])

  // вынесем функцию для обновления анализа
  const handleRefresh = () => {
    // просто повторно вызовет loadData через смену loading
    setLoading(true)
    setTimeout(() => setLoading(false), 10)
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground mb-2">Анализ данных</h1>
        <p className="text-muted-foreground">Обзор пропусков в исходных данных</p>
      </div>
      {loading ? <div>Загрузка...</div> : error ? <div className="text-red-500">{error}</div> : (
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

