import React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/card.jsx';
import { BarChart3 } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useData } from '../../contexts/DataContext';

export default function ForecastChart({ uploadedData, predictionRows }) {
  const { trainingConfig } = useData();
  if (!uploadedData || !predictionRows || predictionRows.length === 0) return null;
  const dateCol = trainingConfig?.dateColumn || uploadedData.columns.find(col => /date|время|time/i.test(col)) || uploadedData.columns[0];
  const valueCol = trainingConfig?.targetColumn || uploadedData.columns.find(col => /target|value|y/i.test(col)) || uploadedData.columns[uploadedData.columns.length-1];
  const idCol = trainingConfig?.idColumn || uploadedData.columns.find(col => /shop|id|city|country/i.test(col) && !/date|target|value|y/i.test(col));
  let firstId = null;
  if (idCol) {
    firstId = uploadedData.rows[0][uploadedData.columns.indexOf(idCol)];
  }
  // Исходные значения только для одного id
  const train = idCol
    ? uploadedData.rows.filter(row => row[uploadedData.columns.indexOf(idCol)] === firstId)
        .map(row => ({
          date: String(row[uploadedData.columns.indexOf(dateCol)]),
          actual: Number(row[uploadedData.columns.indexOf(valueCol)])
        })).filter(row => row.date && !isNaN(row.actual))
    : uploadedData.rows.map(row => ({
          date: String(row[uploadedData.columns.indexOf(dateCol)]),
          actual: Number(row[uploadedData.columns.indexOf(valueCol)])
        })).filter(row => row.date && !isNaN(row.actual));
  // Прогнозные значения только для одного id
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