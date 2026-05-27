#include <Arduino.h>
#include <WiFi.h>
#include <ModbusIP_ESP8266.h>
#include <OneWire.h>
#include <DallasTemperature.h>

///////////////////////////////////////////////////////////////////////////////////////
// aprindere led pe board
///////////////////////////////////////////////////////////////////////////////////////

// void setup() {
//   pinMode(2, OUTPUT); // onboard LED (usually)
// }

// void loop() {
//   digitalWrite(2, HIGH);
//   delay(500);
//   digitalWrite(2, LOW);
//   delay(500);
// }


///////////////////////////////////////////////////////////////////////////////////////
// potentiometru + releu -> trimitere valori serial si visualizare cu serial plotter
///////////////////////////////////////////////////////////////////////////////////////

// #define LEVEL_PIN 34
// #define RELAY_PIN 25

// void setup() {
//   Serial.begin(115200);
//   pinMode(RELAY_PIN, OUTPUT);
// }

// void loop() {
//   int level = analogRead(LEVEL_PIN);
//   int percent = map(level, 0, 4095, 0, 100);

//   bool relayOn = level < 1500;
//   digitalWrite(RELAY_PIN, relayOn ? HIGH : LOW);

//   Serial.print("ADC: ");
//   Serial.print(level);
//   Serial.print(" | Level: ");
//   Serial.print(percent);
//   Serial.print("% | Relay: ");
//   Serial.println(relayOn ? "ON" : "OFF");

//   delay(300);
// }



///////////////////////////////////////////////////////////////////////////////////////
// potentiometru + releu -> trimitere valori prin modbus/tcp over wifi
///////////////////////////////////////////////////////////////////////////////////////


// const char* WIFI_SSID = "DIGI-V3eR";
// const char* WIFI_PASS = "mRVMHbdM4m";

// #define LEVEL_PIN 34
// #define RELAY_PIN 25

// // Modbus object
// ModbusIP mb;

// // Register map
// const uint16_t HREG_LEVEL_RAW     = 0;  // Holding register 0
// const uint16_t HREG_LEVEL_PERCENT = 1;  // Holding register 1
// const uint16_t COIL_RELAY_STATE   = 0;  // Coil 0

// // Adjust for your relay board if needed
// const bool RELAY_ACTIVE_HIGH = true;

// // Threshold for relay logic
// const int LEVEL_THRESHOLD = 1500;

// void setRelay(bool on) {
//   if (RELAY_ACTIVE_HIGH) {
//     digitalWrite(RELAY_PIN, on ? HIGH : LOW);
//   } else {
//     digitalWrite(RELAY_PIN, on ? LOW : HIGH);
//   }
// }

// void setup() {
//   Serial.begin(115200);

//   pinMode(RELAY_PIN, OUTPUT);
//   setRelay(false);

//   WiFi.mode(WIFI_STA);
//   WiFi.begin(WIFI_SSID, WIFI_PASS);

//   Serial.print("Connecting to WiFi");
//   while (WiFi.status() != WL_CONNECTED) {
//     delay(500);
//     Serial.print(".");
//   }

//   Serial.println();
//   Serial.print("WiFi connected. ESP32 IP address: ");
//   Serial.println(WiFi.localIP());

//   // Create Modbus registers
//   mb.server(); // Start Modbus TCP server
//   mb.addHreg(HREG_LEVEL_RAW, 0);
//   mb.addHreg(HREG_LEVEL_PERCENT, 0);
//   mb.addCoil(COIL_RELAY_STATE, false);
// }

// void loop() {
//   mb.task();

//   int levelRaw = analogRead(LEVEL_PIN);
//   int levelPercent = map(levelRaw, 0, 4095, 0, 100);

//   bool relayOn = (levelRaw < LEVEL_THRESHOLD);
//   setRelay(relayOn);

//   // Update Modbus values
//   mb.Hreg(HREG_LEVEL_RAW, levelRaw);
//   mb.Hreg(HREG_LEVEL_PERCENT, levelPercent);
//   mb.Coil(COIL_RELAY_STATE, relayOn);

//   // Debug only
//   static unsigned long lastPrint = 0;
//   if (millis() - lastPrint > 1000) {
//     lastPrint = millis();
//     Serial.print("IP: ");
//     Serial.print(WiFi.localIP());
//     Serial.print(" | Raw: ");
//     Serial.print(levelRaw);
//     Serial.print(" | %: ");
//     Serial.print(levelPercent);
//     Serial.print(" | Relay: ");
//     Serial.println(relayOn ? "ON" : "OFF");
//   }

//   delay(1800);
// }


///////////////////////////////////////////////////////////////////////////////////////
// potentiometru + releu -> trimitere valori prin modbus/tcp over wifi
///////////////////////////////////////////////////////////////////////////////////////


#include <WiFi.h>
#include <ModbusIP_ESP8266.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <secrets.h>

//---------------- WIFI ----------------
const char* wifi_ssid = WIFI_SSID;
const char* wifi_pass = WIFI_PASS;

// ---------------- PINS ----------------
#define RELAY_PIN          25
#define DS18B20_PIN         4
#define ULTRASONIC_TRIG     5
#define ULTRASONIC_ECHO    18

#define BTN_AUTO_MANUAL    26
#define BTN_MANUAL_PUMP    27
#define BTN_ALARM_RESET    19

#define LED_GREEN          21
#define LED_RED            22

// ---------------- MODBUS ----------------
ModbusIP mb;

// Coils
const uint16_t COIL_PUMP_CMD   = 0;
const uint16_t COIL_AUTO_MODE  = 1;
const uint16_t COIL_ALARM_ACK  = 2;

// Discrete Inputs
const uint16_t DI_LOW_LEVEL    = 0;
const uint16_t DI_HIGH_LEVEL   = 1;
const uint16_t DI_HIGH_TEMP    = 2;
const uint16_t DI_SENSOR_FAULT = 3;
const uint16_t DI_PUMP_FB      = 4;
const uint16_t DI_SYSTEM_OK    = 5;

// Holding Registers
const uint16_t HR_LEVEL_MM         = 0;
const uint16_t HR_LEVEL_PERCENT    = 1;
const uint16_t HR_TEMP_C_X10       = 2;
const uint16_t HR_LOW_LVL_TH_PCT   = 3;
const uint16_t HR_HIGH_LVL_TH_PCT  = 4;
const uint16_t HR_HIGH_TEMP_TH_X10 = 5;
const uint16_t HR_TANK_HEIGHT_MM   = 6;
const uint16_t HR_HEADSPACE_MM     = 7;
const uint16_t HR_DISTANCE_MM_RAW  = 8;
const uint16_t HR_STATUS_WORD      = 9;

// ---------------- DS18B20 ----------------
OneWire oneWire(DS18B20_PIN);
DallasTemperature tempSensors(&oneWire);

// ---------------- CONFIG ----------------
const bool RELAY_ACTIVE_HIGH = true;

// Debounce
unsigned long lastDebounceAuto = 0;
unsigned long lastDebouncePump = 0;
unsigned long lastDebounceAck  = 0;
const unsigned long debounceMs = 200;

// Process update
unsigned long lastProcessUpdate = 0;
const unsigned long processIntervalMs = 1000; // 1 second

// Button states
bool lastAutoBtnState = HIGH;
bool lastPumpBtnState = HIGH;
bool lastAckBtnState  = HIGH;

// Alarm states
bool alarmLatched = false;   // remembers that an alarm happened
bool activeAlarm = false;    // true only while alarm condition exists now


// ---------------- HELPERS ----------------
void setRelay(bool on) {
  if (RELAY_ACTIVE_HIGH) {
    digitalWrite(RELAY_PIN, on ? HIGH : LOW);
  } else {
    digitalWrite(RELAY_PIN, on ? LOW : HIGH);
  }
}

long readDistanceMM() {
  digitalWrite(ULTRASONIC_TRIG, LOW);
  delayMicroseconds(2);

  digitalWrite(ULTRASONIC_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(ULTRASONIC_TRIG, LOW);

  unsigned long duration = pulseIn(ULTRASONIC_ECHO, HIGH, 30000); // timeout ~30 ms

  if (duration == 0) {
    return -1; // no echo / invalid
  }

  // speed of sound based formula: distance(cm) = duration / 58 approx
  long distanceMM = (duration * 10) / 58;
  return distanceMM;
}

void updateButtons() {
  bool autoBtn = digitalRead(BTN_AUTO_MANUAL);
  bool pumpBtn = digitalRead(BTN_MANUAL_PUMP);
  bool ackBtn  = digitalRead(BTN_ALARM_RESET);

  if (autoBtn == LOW && lastAutoBtnState == HIGH && millis() - lastDebounceAuto > debounceMs) {
    bool autoMode = mb.Coil(COIL_AUTO_MODE);
    mb.Coil(COIL_AUTO_MODE, !autoMode);
    lastDebounceAuto = millis();
  }

  if (pumpBtn == LOW && lastPumpBtnState == HIGH && millis() - lastDebouncePump > debounceMs) {
    bool autoMode = mb.Coil(COIL_AUTO_MODE);
    if (!autoMode) {
      bool pumpCmd = mb.Coil(COIL_PUMP_CMD);
      mb.Coil(COIL_PUMP_CMD, !pumpCmd);
    }
    lastDebouncePump = millis();
  }

  if (ackBtn == LOW && lastAckBtnState == HIGH && millis() - lastDebounceAck > debounceMs) {
    // Clear latched alarm only if there is no active alarm right now
    if (!activeAlarm) {
      alarmLatched = false;
      }
      mb.Coil(COIL_ALARM_ACK, true);
      lastDebounceAck = millis();
    } else {
      mb.Coil(COIL_ALARM_ACK, false);
    }
    
  lastAutoBtnState = autoBtn;
  lastPumpBtnState = pumpBtn;
  lastAckBtnState  = ackBtn;
}

void setupModbus() {
  mb.server();

  mb.addCoil(COIL_PUMP_CMD, false);
  mb.addCoil(COIL_AUTO_MODE, true);
  mb.addCoil(COIL_ALARM_ACK, false);

  mb.addIsts(DI_LOW_LEVEL, false);
  mb.addIsts(DI_HIGH_LEVEL, false);
  mb.addIsts(DI_HIGH_TEMP, false);
  mb.addIsts(DI_SENSOR_FAULT, false);
  mb.addIsts(DI_PUMP_FB, false);
  mb.addIsts(DI_SYSTEM_OK, true);

  mb.addHreg(HR_LEVEL_MM, 0);
  mb.addHreg(HR_LEVEL_PERCENT, 0);
  mb.addHreg(HR_TEMP_C_X10, 0);
  mb.addHreg(HR_LOW_LVL_TH_PCT, 30);
  mb.addHreg(HR_HIGH_LVL_TH_PCT, 80);
  mb.addHreg(HR_HIGH_TEMP_TH_X10, 300); // 30.0 C
  mb.addHreg(HR_TANK_HEIGHT_MM, 200);
  mb.addHreg(HR_HEADSPACE_MM, 30);
  mb.addHreg(HR_DISTANCE_MM_RAW, 0);
  mb.addHreg(HR_STATUS_WORD, 0);
}

void setup() {
  Serial.begin(115200);

  pinMode(RELAY_PIN, OUTPUT);
  pinMode(ULTRASONIC_TRIG, OUTPUT);
  pinMode(ULTRASONIC_ECHO, INPUT);

  pinMode(BTN_AUTO_MANUAL, INPUT_PULLUP);
  pinMode(BTN_MANUAL_PUMP, INPUT_PULLUP);
  pinMode(BTN_ALARM_RESET, INPUT_PULLUP);

  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_RED, OUTPUT);

  setRelay(false);
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_RED, LOW);

  tempSensors.begin();

  WiFi.mode(WIFI_STA);
  WiFi.begin(wifi_ssid, wifi_pass);

  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.print("Connected. IP: ");
  Serial.println(WiFi.localIP());

  setupModbus();
}

void loop() {
  mb.task();
  updateButtons();

  if (millis() - lastProcessUpdate >= processIntervalMs) {
    lastProcessUpdate = millis();

    // ---- Read temperature ----
    tempSensors.requestTemperatures();
    float tempC = tempSensors.getTempCByIndex(0);
    bool tempValid = (tempC > -100.0 && tempC < 125.0);

    // ---- Read ultrasonic ----
    long distanceMM = readDistanceMM();
    bool distanceValid = (distanceMM >= 20 && distanceMM <= 4000);

    uint16_t tankHeightMM = mb.Hreg(HR_TANK_HEIGHT_MM);
    uint16_t headspaceMM  = mb.Hreg(HR_HEADSPACE_MM);

    long levelMM = 0;
    int levelPercent = 0;

    if (distanceValid) {
      long usableDistance = distanceMM - headspaceMM;
      if (usableDistance < 0) usableDistance = 0;

      levelMM = tankHeightMM - usableDistance;
      if (levelMM < 0) levelMM = 0;
      if (levelMM > tankHeightMM) levelMM = tankHeightMM;

      levelPercent = (int)((levelMM * 100L) / tankHeightMM);
    }

    bool sensorFault = !(tempValid && distanceValid);

    int tempX10 = tempValid ? (int)(tempC * 10.0f) : 0;

    uint16_t lowThPct   = mb.Hreg(HR_LOW_LVL_TH_PCT);
    uint16_t highThPct  = mb.Hreg(HR_HIGH_LVL_TH_PCT);
    uint16_t highTempTh = mb.Hreg(HR_HIGH_TEMP_TH_X10);

    bool lowLevelAlarm  = distanceValid ? (levelPercent < lowThPct) : false;
    bool highLevelAlarm = distanceValid ? (levelPercent >= 95) : false;
    bool highTempAlarm  = tempValid ? (tempX10 > highTempTh) : false;

    // Live alarm state
    activeAlarm = lowLevelAlarm || highLevelAlarm || highTempAlarm || sensorFault;
    
    // Latch alarm memory whenever an active alarm appears
    if (activeAlarm) {
      alarmLatched = true;
    }


    bool autoMode = mb.Coil(COIL_AUTO_MODE);
    bool pumpCmd  = mb.Coil(COIL_PUMP_CMD);

    if (autoMode && !sensorFault) {
      if (levelPercent < lowThPct) {
        pumpCmd = true;
      } else if (levelPercent >= highThPct) {
        pumpCmd = false;
      }
      mb.Coil(COIL_PUMP_CMD, pumpCmd);
    }

    setRelay(pumpCmd);

    mb.Hreg(HR_LEVEL_MM, (uint16_t)levelMM);
    mb.Hreg(HR_LEVEL_PERCENT, (uint16_t)levelPercent);
    mb.Hreg(HR_TEMP_C_X10, (uint16_t)tempX10);
    mb.Hreg(HR_DISTANCE_MM_RAW, distanceValid ? (uint16_t)distanceMM : 0);

    mb.Ists(DI_LOW_LEVEL, lowLevelAlarm);
    mb.Ists(DI_HIGH_LEVEL, highLevelAlarm);
    mb.Ists(DI_HIGH_TEMP, highTempAlarm);
    mb.Ists(DI_SENSOR_FAULT, sensorFault);
    mb.Ists(DI_PUMP_FB, pumpCmd);
    mb.Ists(DI_SYSTEM_OK, !activeAlarm);

    uint16_t statusWord = 0;
    statusWord |= (autoMode      ? 1 << 0 : 0);
    statusWord |= (pumpCmd       ? 1 << 1 : 0);
    statusWord |= (lowLevelAlarm ? 1 << 2 : 0);
    statusWord |= (highLevelAlarm? 1 << 3 : 0);
    statusWord |= (highTempAlarm ? 1 << 4 : 0);
    statusWord |= (sensorFault   ? 1 << 5 : 0);
    statusWord |= (alarmLatched  ? 1 << 6 : 0);

    mb.Hreg(HR_STATUS_WORD, statusWord);

    digitalWrite(LED_GREEN, !activeAlarm ? HIGH : LOW);
    digitalWrite(LED_RED, activeAlarm ? HIGH : LOW);

    Serial.print("Level=");
    Serial.print(levelMM);
    Serial.print(" mm, ");
    Serial.print(levelPercent);
    Serial.print("% | Temp=");
    Serial.print(tempC);
    Serial.print(" C | Pump=");
    Serial.print(pumpCmd ? "ON" : "OFF");
    Serial.print(" | Auto=");
    Serial.print(autoMode ? "YES" : "NO");
    Serial.print(" | Fault=");
    Serial.println(sensorFault ? "YES" : "NO");
  }
}

