import React, { useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/card.jsx';
import { BarChart3 } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useData } from '../../contexts/DataContext';
import { API_BASE_URL } from '../../apiConfig';

export default function ForecastChart({ uploadedData, predictionRows, predictionProcessed }) {
  const { trainingConfig, sessionId, factRows, factLoading, factError, getFactRows } = useData();
  const dateCol = uploadedData && (trainingConfig?.dateColumn || uploadedData.columns.find(col => /date|время|time/i.test(col)) || uploadedData.columns[0]);
  const valueCol = uploadedData && (trainingConfig?.targetColumn || uploadedData.columns.find(col => /target|value|y/i.test(col)) || uploadedData.columns[uploadedData.columns.length-1]);
  const idCol = uploadedData && (trainingConfig?.idColumn || uploadedData.columns.find(col => /shop|id|city|country/i.test(col) && !/date|target|value|y/i.test(col)));
  let firstId = null;
  if (uploadedData && idCol) {
    firstId = uploadedData.rows[0][uploadedData.columns.indexOf(idCol)];
  }

  useEffect(() => {
    if (!predictionProcessed) return;
    if (!sessionId || !idCol || !firstId) return;
    getFactRows({ sessionId, idCol, firstId });
  }, [predictionProcessed, sessionId, idCol, firstId]);

  if (!uploadedData || !predictionRows || predictionRows.length === 0) return null;

  // Формируем данные для графика
  const train = factRows.map(row => ({
    date: String(row[dateCol]),
    actual: Number(row[valueCol])
  })).filter(row => row.date && !isNaN(row.actual));

  const pred = idCol
    ? predictionRows.filter(row => row[idCol] === firstId)
        .map(row => ({
          date: String(row[dateCol]),
          forecast: Number(row[valueCol])
        })).filter(row => row.date && !isNaN(row.forecast))
    : predictionRows.map(row => ({
          date: String(row[dateCol]),
          forecast: Number(row[valueCol])
        })).filter(row => row.date && !isNaN(row.forecast));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center space-x-2">
          <BarChart3 className="text-primary" size={20} />
          <span>Визуализация прогноза для одного ряда</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {idCol && firstId !== null && (
          <div className="mb-2 text-sm text-muted-foreground font-medium">
            Прогноз и факт для <span className="font-semibold">{idCol}</span> = <span className="font-semibold">{String(firstId)}</span>
          </div>
        )}
        {factLoading && <div className="text-sm text-muted-foreground">Загрузка факта...</div>}
        {factError && <div className="text-sm text-red-600">{factError}</div>}
        <div className="h-96">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" type="category" allowDuplicatedCategory={false} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="actual" stroke="#0077C8" strokeWidth={3} name="Факт" data={train} dot={false} />
              <Line type="monotone" dataKey="forecast" stroke="#28a745" strokeDasharray="5 5" name="Прогноз" data={pred} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}