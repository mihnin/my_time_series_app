import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/card.jsx';

export default function ModelMetricsCards({
  bestModel,
  bestModelMetric,
  averageMetric,
  totalTrainingTime,
  predictionProcessed
}) {
  if (!bestModel && !averageMetric && !(predictionProcessed && totalTrainingTime)) return null;
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {bestModel && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Лучшая модель</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-primary">{bestModel}</div>
            <p className="text-sm text-muted-foreground">{bestModelMetric || 'Метрика не доступна'}</p>
          </CardContent>
        </Card>
      )}
      {averageMetric && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Средняя метрика</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{averageMetric}</div>
            <p className="text-sm text-muted-foreground">Среди всех моделей</p>
          </CardContent>
        </Card>
      )}
      {predictionProcessed && totalTrainingTime && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Время выполнения</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">{totalTrainingTime}</div>
            <p className="text-sm text-muted-foreground">Общее время выполнения</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
} 