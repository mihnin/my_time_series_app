# 📊 Universal Forecasting Platform for Business Optimization

### Executive Summary
This project is not just a code repository; it is a deployable, strategic planning tool designed to empower businesses across any industry—from manufacturing and logistics to finance and services. It enables companies to make data-driven decisions, transforming complex forecasting tasks into a simple, automated process accessible to business users without a background in Data Science.

---

### 📈 Business Impact & Core Features

* **Direct Cost Reduction:** By automating forecasting, this platform frees up valuable analyst and manager time, allowing them to focus on high-level strategy instead of manual data processing.
* **Process Optimization:** Accurate forecasts drive efficiency in supply chains, inventory management, production planning, and workforce allocation.
* **Universal Data Analysis:** The platform is engineered to analyze any time-series data, including financial flows, sales figures, logistical metrics, equipment workloads, and more.
* **Data Democratization:** Thanks to an intuitive web interface, any manager can upload data (from Excel or a database) and receive a visualized forecast in minutes, bridging the gap between raw data and actionable insights.

---

### 🏆 Proven Results: Net Working Capital Optimization Case Study

This solution has been successfully deployed in **five industrial and service companies** to address a critical financial challenge: forecasting **Net Working Capital (NWC)** components one month ahead.

**Implementation Results:**
* **A 40% reduction in operational costs** by enabling more precise cash flow planning and minimizing the need for costly external financing.
* **Enhanced quality of managerial decision-making** by providing early warnings of potential liquidity gaps.

---

### ✈️ Relevance for the Airline Industry

This platform is uniquely suited to address the core challenges faced by a modern airline, directly contributing to **enhanced operational efficiency and customer experiences**.

Potential applications include:

* **Passenger Demand Forecasting:** Accurately predict passenger volume on specific routes to optimize flight schedules, fleet allocation, and pricing strategies.
* **Crew Scheduling Optimization:** Forecast staffing requirements for pilots and cabin crew to build more efficient and cost-effective schedules.
* **Predictive Maintenance (MRO):** Analyze sensor data from aircraft components to predict potential failures, allowing for proactive maintenance scheduling that minimizes aircraft downtime and improves safety.
* **Load & Catering Optimization:** Forecast passenger and baggage loads to streamline ground handling and reduce waste and costs associated with in-flight catering.
* **Financial & Operational Planning:** Predict key operational metrics, from future aviation fuel prices to revenue streams, contributing to a more robust financial strategy.

---

## 🚀 Live Demo & Technical Guide

This section provides all the necessary information to run the application locally and test its functionality.

### Technical Stack
* **Backend:** Python, FastAPI, AutoGluon (for automated machine learning)
* **Core Libraries:** Pandas, NumPy, Scikit-learn
* **Frontend:** Vue.js
* **Deployment:** Docker, Docker Compose

### Quick Start with Docker (Recommended)

1.  Clone the repository and navigate to the project folder:
    ```sh
    cd my_time_series_app
    ```

2.  Run all services with a single command:
    ```sh
    docker-compose up --build
    ```

* After building and launching:
    * **Frontend** will be available at: `http://localhost:4173`
    * **Backend (API)** will be available at: `http://localhost:8000`

> **Note:** After opening the application for the first time, set up a secret word. This will be used for configuring the database connection later. To do this, select advanced user settings, go to DB connection settings, and enter the secret word.

### Application Usage (User Guide)

#### 1. Connect to a Database (Optional)
* To load data from or save results to a database, connect to PostgreSQL using the button in the top-right corner.
* Enter your username and password, then test the connection.

#### 2. Load Data
* **From a file:** Click "Choose File" and upload a CSV/Excel file.
* **From a database:** After connecting, select a schema and table, then click "Load Data from DB".

#### 3. Select Columns for Training
* You must select:
    * The **date** column
    * The **ID** column
    * The **target variable** column
* (Optional) You can also select **static features**.

#### 4. Configure Parameters
* **Data frequency:** auto/day/month/hour, etc.
* **Method for filling missing values:** default is Forward fill.
* **Quality metric:** Choose a metric to evaluate model performance.
* **Models:** AutoGluon is recommended for automatic model selection.
* **Training time limit:** Set a time limit for the training process.
* **Prediction horizon:** Define the forecast period (days/weeks/months).

#### 5. Start Training
* Click "Start Training". The progress will be displayed on the screen.
* Upon completion, a table with results and a model leaderboard will appear.

#### 6. Get Forecast
* Click "Make Forecast". The results will be displayed in a table and on charts.
* You can download the forecast as an Excel/CSV file or save it to the database.

#### 7. Additional Features
* **Data Analysis:** Check for missing values, anomalies, seasonality, correlations, and concept drift.
* **Logs:** View, download, and clear logs via the ⚙️ menu.
* **Memory Management:** Use the "Clear Memory" button when handling large files.

---

### Manual Start (Alternative)

1.  **Prerequisites:** Install Python 3.10+ and Node.js 18+.

2.  **Install Dependencies:**
    * **Backend:** `pip install -r backend/requirements.txt`
    * **Frontend:** `cd frontend && npm install && npm run build-only`

3.  **Start the Backend:**
    ```sh
    cd backend/app
    uvicorn main:app --host 0.0.0.0 --port 8000
    ```

4.  **Start the Frontend:**
    ```sh
    cd frontend
    npm run preview -- --host --port 4173
    ```
