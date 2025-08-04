import React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/card.jsx';
import { Award } from 'lucide-react';

export default function ModelLeaderboard({
  leaderboard,
  trainingParams,
  trainingConfig,
  isPycaretRow,
  hasPycaretData,
  openPycaretModal,
  formatCellValue
}) {
  if (!leaderboard || leaderboard.length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center space-x-2">
          <Award className="text-primary" size={20} />
          <span>Лидерборд моделей</span>
        </CardTitle>
        <CardDescription>
          Сравнение качества обученных моделей по различным метрикам
          {leaderboard.some(row => isPycaretRow(row)) && hasPycaretData() && (
            <span className="block text-sm text-blue-600 mt-1">
              💡 Нажмите на строки PyCaret для просмотра детальных метрик по каждому ряду
            </span>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b">
                {Object.keys(leaderboard[0]).map((key) => (
                  <th key={key} className="text-left p-3 font-medium">
                    {key === 'rank' ? 'Ранг' :
                     key === 'model' ? 'Модель' :
                     key === 'status' ? 'Статус' :
                     key === 'mae' ? 'MAE' :
                     key === 'mape' ? 'MAPE' :
                     key === 'rmse' ? 'RMSE' :
                     key === 'r2' || key === 'rsquared' ? 'R²' :
                     key === 'trainingTime' || key === 'training_time' ? 'Время' :
                     key === 'score_val' ? (trainingParams?.evaluation_metric || trainingConfig?.selectedMetric?.toUpperCase() || 'Метрика') :
                     key}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {leaderboard
                .sort((a, b) => (a.rank || 999) - (b.rank || 999))
                .map((row, index) => (
                <tr 
                  key={index} 
                  className={`border-b ${
                    isPycaretRow(row) && hasPycaretData() 
                      ? 'cursor-pointer bg-blue-50 hover:bg-blue-100' 
                      : 'hover:bg-muted/50'
                  }`}
                  onClick={isPycaretRow(row) && hasPycaretData() ? openPycaretModal : undefined}
                  title={isPycaretRow(row) && hasPycaretData() ? "Нажмите для просмотра детальных метрик по каждому ряду" : ""}
                >
                  {Object.entries(row).map(([key, value]) => (
                    <td key={key} className="p-3">
                      {formatCellValue(key, value)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
} 