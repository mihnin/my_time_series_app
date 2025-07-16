import React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/card.jsx';
import { Button } from '../ui/button.jsx';
import { Progress } from '../ui/progress.jsx';
import { Play, Clock, TrendingUp, CheckCircle, AlertCircle } from 'lucide-react';

export default function TrainingControl({
  getTrainingStatus,
  handleStartTraining,
  trainingConfig,
  uploadedFile,
  getCurrentProgress,
  elapsedTime,
  getStatusMessage,
  globalTrainingStatus
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center space-x-2">
          <Play className="text-primary" size={20} />
          <span>Управление обучением</span>
        </CardTitle>
        <CardDescription>
          Запустите процесс обучения моделей
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center space-x-4">
          <Button 
            onClick={handleStartTraining}
            disabled={getTrainingStatus() === 'running' || !trainingConfig || !uploadedFile}
            className="bg-primary hover:bg-primary/90"
          >
            <Play size={16} className="mr-2" />
            Начать обучение
          </Button>
        </div>

        {getTrainingStatus() === 'running' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Общий прогресс</span>
              <span className="text-sm text-muted-foreground">{getCurrentProgress()}%</span>
            </div>
            <Progress value={getCurrentProgress()} className="w-full" />
            <div className="flex items-center space-x-4 text-sm text-muted-foreground">
              <div className="flex items-center space-x-2">
                <Clock size={16} />
                <span>Время: {Math.floor(elapsedTime / 60)}:{(elapsedTime % 60).toString().padStart(2, '0')}</span>
              </div>
              <div className="flex items-center space-x-2">
                <TrendingUp size={16} />
                <span>{getStatusMessage()}</span>
              </div>
            </div>
          </div>
        )}

        {getTrainingStatus() === 'completed' && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-center space-x-2">
              <CheckCircle className="text-green-600" size={20} />
              <div>
                <p className="font-medium text-green-800">Обучение завершено успешно</p>
                <p className="text-sm text-green-600">
                  Все модели обучены. Результаты доступны в таблице ниже.
                </p>
              </div>
            </div>
          </div>
        )}

        {getTrainingStatus() === 'error' && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-center space-x-2">
              <AlertCircle className="text-red-600" size={20} />
              <div>
                <p className="font-medium text-red-800">Ошибка при обучении</p>
                <p className="text-sm text-red-600">
                  {globalTrainingStatus?.error || 'Произошла ошибка в процессе обучения'}
                </p>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
} 