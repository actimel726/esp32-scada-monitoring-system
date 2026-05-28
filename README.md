# ESP32 SCADA Monitoring System

Industrial IoT monitoring and control system based on ESP32, Modbus TCP, SCADA visualization and AI-assisted anomaly detection.

## Overview

This project implements a small-scale industrial monitoring architecture inspired by real SCADA/ICS environments. An ESP32 development board acts as a lightweight PLC that acquires sensor data, exposes telemetry through Modbus TCP and allows remote monitoring and control through a SCADA interface.

The system integrates:
- ESP32-based data acquisition and control
- Modbus TCP communication
- ScadaBR HMI/SCADA visualization
- Python telemetry monitoring and logging
- AI-based anomaly detection using Isolation Forest

The project simulates a smart water tank process where the tank level is estimated using an ultrasonic sensor, while temperature is monitored using a DS18B20 sensor. A relay module simulates pump activation and the system supports both automatic and manual operation modes.

The monitoring pipeline was designed to resemble a realistic industrial architecture where:
- the ESP32 performs local control
- SCADA provides operational visualization
- the Python monitoring component performs telemetry analysis and anomaly detection

Modern SCADA systems increasingly integrate IoT connectivity, remote monitoring and advanced analytics capabilities. :contentReference[oaicite:0]{index=0}

---

## System Architecture

```text
ESP32 + Sensors
        │
        │ Modbus TCP over WiFi
        ▼
   Python Monitoring Client
        │
        ├── JSONL Telemetry Logging
        ├── AI Anomaly Detection
        └── Real-Time Monitoring
        │
        ▼
      ScadaBR
   HMI / Visualization
```

<img width="756" height="1073" alt="image" src="https://github.com/user-attachments/assets/caa64e23-f860-4528-b48e-d3e8ef42a5ce" />


## Features
- ESP32 Modbus TCP server
- WiFi-based telemetry acquisition
- Real-time SCADA visualization using ScadaBR
- Automatic and manual process control
- Relay-based pump simulation
- Alarm handling and acknowledgement
- Python Modbus monitoring client
- Structured JSONL telemetry logging
- AI-assisted anomaly detection using Isolation Forest
- Normalized telemetry dataset generation

## Hardware Components
- ESP32 development board
- HC-SR04 ultrasonic sensor
- DS18B20 temperature sensor
- Relay module
- LEDs and push buttons
- Breadboard and jumper wires
## Software Stack
### Embedded
- PlatformIO
- Arduino Framework
- ModbusIP_ESP8266 library
### Monitoring & SCADA
- Python 3
- pymodbus
- ScadaBR
### AI / Analytics
- pandas
- scikit-learn
- Isolation Forest

## Modbus Register Map
### Coils
- 0	Pump command
- 1	Auto/Manual mode
- 2	Alarm acknowledge
### Discrete Inputs
- 0	Low level alarm
- 1	High level alarm
- 2	High temperature alarm
- 3	Sensor fault
- 4	Pump feedback
- 5	System OK
### Holding Registers
- 0	Level (mm)
- 1	Level (%)
- 2	Temperature (°C x10)
- 3	Low level threshold
- 4	High level threshold
- 5	High temperature threshold
- 6	Tank height
- 7	Headspace
- 8	Raw ultrasonic distance
- 9	Status word

## AI Anomaly Detection

The project integrates a lightweight anomaly detection pipeline based on the Isolation Forest algorithm.
The AI model is trained on normal telemetry behaviour and detects:

- sudden level changes
- abnormal sensor readings
- inconsistent process states
- sensor faults
- unusual process dynamics

Unlike embedded TinyML inference, the model runs in the Python monitoring layer. This design better reflects realistic industrial architectures where advanced analytics are usually performed at the monitoring or gateway level using telemetry aggregated from multiple PLCs.
The model uses features such as:

- tank level
- temperature
- pump state
- alarm states
- level change rate

## Dataset Generation

A synthetic telemetry dataset representing several days of normal industrial operation was generated for AI training and testing purposes.
The generated dataset includes:

- realistic filling and draining cycles
- stable temperature evolution
- normal operational states

Anomalies include:

- sudden level jumps
- sensor faults
- temperature spikes
- process contradictions
- unstable oscillations

# Quick Setup

1. Clone the repository

```bash
git clone https://github.com/actimel726/esp32-scada-monitoring-system.git
cd esp32-scada-monitoring-system
```
2. Configure WiFi credentials
Create:

include/secrets.h

Example:
```C++
#pragma once

#define WIFI_SSID "YOUR_WIFI"
#define WIFI_PASS "YOUR_PASSWORD"
```
3. Upload firmware to ESP32

Using PlatformIO:
```
pio run --target upload
```

4. Create Python virtual environment
Windows
```
python -m venv .venv
.venv\Scripts\activate
```
Install dependencies:
```
pip install pandas pymodbus scikit-learn joblib
```
5. Train the AI model
```
python train_anomaly_model.py
```
6. Start monitoring and AI detection
```
python monitoring_AI.py
```
Example output:

level=152mm (76%) | temp=22.4C | AI=NORMAL

7. SCADA Integration
Configure a Modbus TCP data source in ScadaBR:
```
IP = ESP32 IP
Port = 502
Slave ID = 1
```

The system supports:

- real-time visualization
- pump control
- alarm monitoring
- AI-assisted anomaly detection

## Results
SCADA Web Interface
<img width="1267" height="826" alt="image" src="https://github.com/user-attachments/assets/3270fba7-23ab-4072-b02f-48698d5a6654" />

Normal vs anomaly detection example logs


```text
{"ts": "2026-05-27T22:43:59.038815+03:00", "event_type": "telemetry", "asset": "esp32_tank_station", "asset_ip": "192.168.0.133", "proto": "modbus_tcp", "unit_id": 1, "level_mm": 178, "level_pct": 89, "temp_c": 28.6, "distance_mm": 52, "level_change_rate": -2.4777743639553207, "pump_cmd": false, "pump_fb": false, "auto_mode": true, "low_alarm": false, "high_alarm": false, "temp_alarm": false, "sensor_fault": false, "system_ok": true, "status_word": 65, "ai_model": "IsolationForest", "ai_anomaly": false, "ai_status": "NORMAL"}

{"ts": "2026-05-27T22:44:01.195899+03:00", "event_type": "telemetry", "asset": "esp32_tank_station", "asset_ip": "192.168.0.133", "proto": "modbus_tcp", "unit_id": 1, "level_mm": 183, "level_pct": 91, "temp_c": 28.7, "distance_mm": 47, "level_change_rate": 4.602352170147119, "pump_cmd": false, "pump_fb": false, "auto_mode": true, "low_alarm": false, "high_alarm": false, "temp_alarm": false, "sensor_fault": false, "system_ok": true, "status_word": 65, "ai_model": "IsolationForest", "ai_anomaly": true, "ai_status": "ANOMALY"}
```



