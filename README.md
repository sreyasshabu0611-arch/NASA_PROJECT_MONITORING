
# SPACECARE – Astronaut Health Monitoring System

## 1. Project Overview

SpaceCare is an advanced Astronaut Health Monitoring System developed using Python FastAPI.

The application monitors astronaut health parameters through simulated sensor readings and displays the information on a real-time web dashboard.

It demonstrates how astronaut health information can be monitored during space missions.

## 2. Technologies Used

### Backend
- Python
- FastAPI
- Uvicorn
- SQLite
- WebSocket

### Frontend
- HTML
- CSS
- JavaScript
- Chart.js

### Development Tools
- Visual Studio Code
- Python 3.10 or newer
- Web Browser

## 3. Main Features

- Real-time astronaut health monitoring.
- Five default astronaut profiles.
- Heart rate monitoring.
- Blood oxygen monitoring (SpO2).
- Body temperature monitoring.
- Blood pressure simulation.
- Respiratory rate monitoring.
- Automatic health alert generation.
- Emergency alert acknowledgement.
- Live health analytics.
- Sensor scenario simulation.
- Astronaut profile creation.
- CSV health report download.
- SQLite database storage.
- WebSocket communication.

## 4. Project Structure

```text
SpaceCare_Advanced/
│
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
│
└── static/
    ├── index.html
    ├── styles.css
    └── app.js
```

## 5. Installation

Install Python 3.10 or newer.

Open the SpaceCare_Advanced folder in VS Code.

Open Terminal → New Terminal.

Create a virtual environment:

```powershell
py -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\activate
```

Install dependencies:

```powershell
py -m pip install -r requirements.txt
```

## 6. Run the Application

Execute:

```powershell
py -m uvicorn app:app --reload
```

Open the following address:

http://127.0.0.1:8000

### Demo admin login

- Username: `admin`
- Password: `SpaceCare@123` (case-sensitive)

Change the credentials in `app.py` before deploying the application.

## 7. API Documentation

FastAPI provides interactive API documentation.

Open:

http://127.0.0.1:8000/docs

## 8. Database

SQLite is used to store astronaut profiles, sensor readings and emergency alerts.

The database file is automatically created when the application starts.

Database filename:

spacecare.db

## 9. Sensor Simulation

The backend generates simulated health readings approximately every two seconds.

Available scenarios:

- Normal health
- High heart rate
- Low oxygen saturation
- Abnormal temperature
- Critical emergency
- Sensor disconnected

## 10. Future Enhancements

- Physical wearable sensor integration.
- MQTT communication.
- ECG monitoring.
- Authentication and user roles.
- PostgreSQL database.
- PDF medical report generation.
- AI-based anomaly detection.
- Mission and spacecraft management.

## 11. Disclaimer

This application is an academic prototype.

It uses simulated health data and is not a certified medical device. It must not be used for actual medical diagnosis or emergency response.
