# src/help_page.py
# Обновленный файл src/help_page.py
# src/help_page.py
import streamlit as st

def show_help_page():
    st.title("📊 Справка по работе с приложением")
    
    st.markdown("""
    # 🔍 Руководство пользователя
    
    ## 📝 Требования к данным
    
    ### Обязательные файлы:
    1. **Train.xlsx/.csv** – исторические данные (Train)
    
    ### Структура данных:
    ```csv
    Дата,ID,Сумма,Регион,Канал
    2023-01-01,Store_001,1500.50,Москва,Онлайн
    2023-01-01,Store_002,2100.75,Москва,Офлайн
    ```
       
    - Формат CSV (разделитель `;`, `,`, UTF-8) или Excel (.xls/.xlsx).
    - Если при чтении CSV возникает ошибка кодировки, сохраните файл в UTF-8.
    
    #### ⚡️ Минимальные требования:
    - Колонка с датой
    - Колонка с целевой переменной (Target)
    - Колонка ID (опционально, если несколько временных рядов)
    
    ---

    ## 🎯 Пошаговая инструкция
    
    ### 1️⃣ Загрузка и настройка данных
    
    **Выбор столбцов**:
    ```python
    {
      'Колонка с датой': <название столбца с датами>,
      'Колонка target': <название столбца с целевой переменной>,
      'Колонка ID': <название столбца с идентификатором> (если несколько рядов),
      'Статические признаки': ['Регион', 'Канал', ...]  # до 3-х признаков
    }
    ```
    
    **Настройки для больших файлов**:
    - Для файлов > 100 МБ рекомендуется использовать загрузку чанками
    - Настройте размер чанка (по умолчанию 100 000 строк)
    
    ### 2️⃣ Обработка данных
    
    **Методы заполнения пропусков**:
    - 🔵 None (оставить как есть)
    - 🔵 Constant=0 (заполнить нулями)
    - 🔵 Forward fill (протянуть значения вперёд/назад)
    - 🔵 Group mean (среднее по группе)
    - 🔵 Interpolate (линейная интерполяция)
    - 🔵 KNN imputer (заполнение методом k ближайших соседей)
    
    **Частота данных (freq)**:
    - 📅 auto (угадать)
    - 📅 D (день)
    - 🕐 H (час)
    - 📅 M (месяц)
    - 📅 B (рабочие дни)
    - 📅 W (неделя)
    - 📅 Q (квартал)
    
    ### 3️⃣ Настройка модели
    
    ```python
    {
      'prediction_length': 10,   # горизонт прогноза (по умолчанию)
      'time_limit': 60,         # время на обучение (сек)
      'metric': 'MASE/SQL/...',
      'models': ['* (все)'] или ['DeepAR', 'AutoETS', ...],
      'presets': 'medium_quality'  # режим (fast_training / medium_quality / high_quality / best_quality)
    }
    ```
    
    ### 4️⃣ Расширенный анализ данных (новая страница)
    
    **Валидация данных**:
    - Проверка типов данных и структуры
    - Анализ пропусков
    - Обнаружение аномалий
    
    **Анализ целевой переменной**:
    - Распределение и статистики
    - Визуализация временного ряда
    - Обнаружение и обработка выбросов
    - Трансформации (log, sqrt, Box-Cox, Yeo-Johnson)
    
    **Корреляции и статические признаки**:
    - Анализ корреляций
    - Обнаружение мультиколлинеарности
    - Расчет VIF (Variance Inflation Factor)
    
    **Временной ряд и сезонность**:
    - Декомпозиция временного ряда (тренд, сезонность, остатки)
    - Генерация временных признаков (год, месяц, день, циклические признаки)
    - Создание лаговых признаков
    - Создание скользящих признаков (среднее, std, мин, макс)
    
    **Выявление концепт-дрифта**:
    - Обнаружение изменений в распределении с течением времени
    - Визуализация дрифта
    - Рекомендации по переобучению модели
    
    **Разделение данных**:
    - Разделение по дате или доле данных
    - Опция для создания валидационной выборки
    - Анализ различий между выборками
    
    ### 5️⃣ Получение результатов
    
    **Результаты включают**:
    - Прогнозы (по квантилям, если включено)
    - Графики по каждому ID
    - Логи обучения
    - Excel-файл с итогами
    - Опция проверки концепт-дрифта в прогнозе

    ## ❓ Часто задаваемые вопросы (FAQ)
    
    ### 🔹 Работа с логами
    
    **Q: Как работать с логами?**
    - ✅ Просмотр через кнопку «Показать логи»
    - ✅ Скачивание через «Скачать логи»
    - ✅ Очистка через ввод «delete» (в соответствующем поле)
    
    **Q: Как управлять памятью для больших файлов?**
    - ✅ При загрузке больших файлов используйте настройки чанка
    - ✅ Используйте кнопку "Очистить память" в боковом меню
    - ✅ Следите за индикатором использования памяти
    
    **Q: Можно ли менять `prediction_length` без обучения заново?**  
    **A:** Нет, AutoGluon «привязывает» горизонт прогноза к обученной модели.  
    Чтобы сделать прогноз на другом горизонте, придётся перезапустить обучение.
    
    **Q: Как учесть российские праздники?**  
    **A:** Включите чекбокс «Учитывать праздники РФ?» и повторно обучите модель, 
    тогда автоматически будет создан дополнительный признак `russian_holiday`.

    ---

    ## 💾 Сохранение результатов
    Вы можете сохранить результаты в CSV или Excel.  
    Если появляется ошибка вида `PermissionError: [Errno 13] Permission denied`, 
    значит файл **открыт** в Excel. Закройте его и повторите сохранение.
    
    **По умолчанию (при сохранении в Excel)** создаются листы:
    - `Predictions` – итоговые прогнозы
    - `Leaderboard` – сравнение моделей
    - `WeightedEnsembleInfo` – (опционально) если лучшая модель – ансамбль 
      (WeightedEnsemble), то здесь появится её состав и веса.
    
    Обратите внимание, что:
    - **Train**-данные и признак `russian_holiday` (если был добавлен) 
      **не сохраняются** в Excel-файле для экономии места.
    - Вы можете также скачать архив с обученными моделями и логами.

    ### 🔹 Дополнительно: Сохранение результатов
    **Q: Как сохранить результаты?**
    - ✅ Excel-файл (кнопка «Сохранить результаты в Excel» или «Обучение, Прогноз и Сохранение»)
    - ✅ CSV-файл (только сами прогнозы)
    - ✅ Архив с моделями + логами (кнопка «Скачать архив (модели + логи)»)

    ### 🔹 Праздничные дни
    **Q: Как учитываются праздники РФ?**
    - ✅ Автоматическое определение (через библиотеку `holidays`)
    - ✅ Включение/отключение через чекбокс «Учитывать праздники РФ?»
    - ✅ Может повысить точность прогноза в некоторых случаях
    
    ---

    ## 💡 Полезные советы
    
    1. **Валидация данных**:
       - Всегда проверяйте данные на странице "Анализ данных" перед обучением
       - Обращайте внимание на предупреждения о пропусках, выбросах и аномалиях
       - Используйте трансформации целевой переменной для улучшения прогноза
    
    2. **Генерация признаков**:
       - Для временных рядов важны лаговые признаки
       - Используйте скользящие признаки для учета долгосрочных трендов
       - Циклические временные признаки (sin/cos) часто полезны для сезонности
    
    3. **Подготовка данных**:
       - Проверьте пропуски и аномалии
       - Настройте правильную частоту
       - Убедитесь, что даты корректно парсятся (datetime)
       - Используйте декомпозицию ряда для понимания сезонности

    4. **Обнаружение концепт-дрифта**:
       - Если обнаружен дрифт, стоит переобучить модель на новых данных
       - Регулярно проверяйте актуальность прогнозов
       - Установите процесс мониторинга для долгосрочных прогнозов

    5. **Оптимизация**:
       - Начинайте с `fast_training`
       - `medium_quality` – хороший баланс между скоростью и качеством
       - `high_quality` / `best_quality` для максимальной точности (более долгий фит)
       - Для больших данных используйте чанкинг и управление памятью

    6. **Сохранение результатов**:
       - Регулярно выгружайте прогнозы
       - Используйте архив для полной копии моделей + логов
       - Следите за объёмом данных, чтобы Excel-файл не был слишком большим
     
    ## 🔄 Повторный запуск и исчезнувшие колонки
    Если модель обучалась раньше и в её настройках были статические признаки (например, "Country"), 
    а в **новом** датасете колонки "Country" больше нет, приложение 
    **автоматически** уберёт "Country" из session_state.  
    Это защищает от ошибок вида:
    `StreamlitAPIException: The default value 'Country' is not in the options`.
    """)