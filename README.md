# Universal CSV Analytics Platform

#live demo
https://universal-csv-analytics.vercel.app/

A professional, dynamic Data Analytics Platform that can ingest **any** CSV file, automatically analyze its structure, map its columns, and generate a comprehensive interactive dashboard containing KPIs, Plotly charts, AI Business Insights, and downloadable reports.

Built as a 2nd-year Computer Science major project for a Data Analytics Bootcamp.

## ✨ Features

- **Smart Dataset Detection**: Automatically identifies standard metrics like Sales, Profit, Customer, Product, Region, and Date based on common synonyms.
- **Adaptive Dashboard**: Modifies the available charts and insights dynamically. If a dataset doesn't have "Sales", it gracefully falls back to generic statistical analysis (correlations, distributions) without crashing.
- **Interactive Visualizations**: Powered by Plotly, featuring tooltips, zoom, and dynamic rendering.
- **AI Business Insights**: Automatically generates rule-based business insights and recommendations (e.g., Identifying the most profitable category or loss-making products).
- **Data Cleaning Engine**: Automatically handles missing values and drops exact duplicates.
- **Downloadable Reports**: Export the cleaned data to CSV/Excel, or generate a professional PDF Report summarizing the dataset and insights using ReportLab.
- **Modern UI**: Glassmorphism design, gradient text, smooth animations, drag-and-drop file upload, and Dark/Light mode toggle.

## 🛠️ Tech Stack

- **Backend**: Python, Flask
- **Data Processing**: Pandas, NumPy
- **Visualizations**: Plotly, Matplotlib (fallback/generic), Seaborn (fallback/generic)
- **Report Generation**: ReportLab (PDF), OpenPyXL (Excel)
- **Frontend**: HTML5, CSS3 (Vanilla), JavaScript (Vanilla), Bootstrap Icons

## 📂 Project Structure

```
Universal-CSV-Analytics/
│── uploads/                 # Temporary storage for uploaded CSVs
│── reports/                 # Temporary storage for generated PDFs/Excel files
│── templates/
│     └── index.html         # Main Single Page Application UI
│── static/
│     ├── style.css          # Styling & Themes (Dark/Light mode)
│     └── script.js          # API interactions & Chart rendering
│── main.py                  # Flask Application, Routing & Data Cleaning
│── charts.py                # Plotly Chart generation logic
│── requirements.txt         # Project Dependencies
│── README.md                # Documentation
```

## 🚀 Setup & Installation

1. **Clone the repository:**
   ```bash
   git clone <repo_url>
   cd Universal-CSV-Analytics
   ```

2. **Create a virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   python main.py
   ```

5. **Access the application:**
   Open your browser and navigate to `http://127.0.0.1:5000/`

## 📊 How It Works

1. **Upload**: Drag and drop any `.csv` file into the upload zone.
2. **Process**: The backend reads the CSV using Pandas, imputes missing values, and calculates a Data Health Score.
3. **Map**: The system looks for column synonyms (e.g., mapping "Revenue" to "Sales").
4. **Analyze**: The backend generates KPIs and Plotly JSON structures via `charts.py`.
5. **Render**: The frontend consumes the JSON and uses Plotly.js to render beautiful interactive charts.
6. **Export**: Click the download buttons to generate a Python ReportLab PDF or download cleaned data.

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

## 📝 License

This project is open-source and available under the MIT License.
