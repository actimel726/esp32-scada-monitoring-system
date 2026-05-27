
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
import threading
import queue
import joblib
import pandas as pd

from pymodbus.client import ModbusTcpClient

ESP32_IP = "192.168.0.133"
ESP32_PORT = 502
DEVICE_ID = 1

POLL_INTERVAL = 1.0
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "tank_log.jsonl"
NORM_LOG_FILE = LOG_DIR / "tank_log_norm.jsonl"

#AI_MODEL_FILE = Path("models/tank_anomaly_model.joblib")
AI_MODEL_FILE = Path("models/tank_anomaly_model_2.0.joblib")
ai_model = joblib.load(AI_MODEL_FILE) if AI_MODEL_FILE.exists() else None


AI_FEATURES = [
    "level_mm",
    "level_pct",
    "temp_c",
    "distance_mm",
    "level_change_rate",
    "pump_cmd",
    "pump_feedback",
    "auto_mode",
    "low_alarm",
    "high_alarm",
    "temp_alarm",
    "sensor_fault",
    "system_ok",
    "status_word",
]

previous_level_mm = None
previous_timestamp = None

last_alarm_states = {
    "low_level_alarm": None,
    "high_level_alarm": None,
    "high_temp_alarm": None,
    "sensor_fault": None,
}


def compute_level_change_rate(snapshot: dict) -> float:
    global previous_level_mm, previous_timestamp

    current_level = snapshot["process"]["level_mm"]
    current_time = datetime.fromisoformat(snapshot["timestamp"])

    if previous_level_mm is None or previous_timestamp is None:
        previous_level_mm = current_level
        previous_timestamp = current_time
        return 0.0

    delta_level = current_level - previous_level_mm
    delta_time = (current_time - previous_timestamp).total_seconds()

    previous_level_mm = current_level
    previous_timestamp = current_time

    if delta_time <= 0:
        return 0.0

    return delta_level / delta_time


def detect_ai_anomaly(snapshot: dict) -> bool:
    if ai_model is None:
        return False

    p = snapshot["process"]
    s = snapshot["state"]

    row = {
        "level_mm": p["level_mm"],
        "level_pct": p["level_percent"],
        "temp_c": p["temperature_c"],
        "distance_mm": p["distance_mm_raw"],
        "level_change_rate": p["level_change_rate"],
        "pump_cmd": int(s["pump_cmd"]),
        "pump_feedback": int(s["pump_feedback"]),
        "auto_mode": int(s["auto_mode"]),
        "low_alarm": int(s["low_level_alarm"]),
        "high_alarm": int(s["high_level_alarm"]),
        "temp_alarm": int(s["high_temp_alarm"]),
        "sensor_fault": int(s["sensor_fault"]),
        "system_ok": int(s["system_ok"]),
        "status_word": int(s["status_word"]),
    }

    X = pd.DataFrame([row], columns=AI_FEATURES)
    prediction = ai_model.predict(X)[0]

    return bool(prediction == -1)


def log_alarm_transitions(snapshot: dict) -> None:
    global last_alarm_states

    s = snapshot["state"]
    current = {
        "low_level_alarm": s["low_level_alarm"],
        "high_level_alarm": s["high_level_alarm"],
        "high_temp_alarm": s["high_temp_alarm"],
        "sensor_fault": s["sensor_fault"],
    }

    for name, value in current.items():
        old = last_alarm_states[name]
        if old is not None and old != value:
            record = {
                "ts": snapshot["timestamp"],
                "event_type": "alarm_transition",
                "asset": "esp32_tank_station",
                "asset_ip": ESP32_IP,
                "proto": "modbus_tcp",
                "unit_id": DEVICE_ID,
                "alarm": name,
                "old": old,
                "new": value,
            }
            with NORM_LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        last_alarm_states[name] = value


def check(result, label: str) -> None:
    if result.isError():
        raise RuntimeError(f"{label} failed: {result}")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def decode_status_word(status_word: int) -> dict:
    return {
        "auto_mode_bit": bool(status_word & (1 << 0)),
        "pump_cmd_bit": bool(status_word & (1 << 1)),
        "low_level_alarm_bit": bool(status_word & (1 << 2)),
        "high_level_alarm_bit": bool(status_word & (1 << 3)),
        "high_temp_alarm_bit": bool(status_word & (1 << 4)),
        "sensor_fault_bit": bool(status_word & (1 << 5)),
        "alarm_latched_bit": bool(status_word & (1 << 6)),
    }


def read_snapshot(client: ModbusTcpClient) -> dict:
    hr = client.read_holding_registers(0, count=10, device_id=DEVICE_ID)
    di = client.read_discrete_inputs(0, count=6, device_id=DEVICE_ID)
    co = client.read_coils(0, count=3, device_id=DEVICE_ID)

    check(hr, "read HR")
    check(di, "read DI")
    check(co, "read CO")

    status_word = hr.registers[9]

    snapshot = {
        "timestamp": now_iso(),
        "source": "esp32_tank_station",
        "device_ip": ESP32_IP,
        "modbus": {
            "holding_registers": {
                "level_mm": hr.registers[0],
                "level_percent": hr.registers[1],
                "temperature_c_x10": hr.registers[2],
                "low_level_threshold_percent": hr.registers[3],
                "high_level_threshold_percent": hr.registers[4],
                "high_temp_threshold_c_x10": hr.registers[5],
                "tank_height_mm": hr.registers[6],
                "headspace_mm": hr.registers[7],
                "distance_mm_raw": hr.registers[8],
                "status_word": status_word,
            },
            "discrete_inputs": {
                "low_level_alarm": bool(di.bits[0]),
                "high_level_alarm": bool(di.bits[1]),
                "high_temp_alarm": bool(di.bits[2]),
                "sensor_fault": bool(di.bits[3]),
                "pump_feedback": bool(di.bits[4]),
                "system_ok": bool(di.bits[5]),
            },
            "coils": {
                "pump_cmd": bool(co.bits[0]),
                "auto_mode": bool(co.bits[1]),
                "alarm_ack": bool(co.bits[2]),
            },
        },
        "process": {
            "level_mm": hr.registers[0],
            "level_percent": hr.registers[1],
            "temperature_c": hr.registers[2] / 10.0,
            "distance_mm_raw": hr.registers[8],
        },
        "thresholds": {
            "low_level_threshold_percent": hr.registers[3],
            "high_level_threshold_percent": hr.registers[4],
            "high_temp_threshold_c": hr.registers[5] / 10.0,
            "tank_height_mm": hr.registers[6],
            "headspace_mm": hr.registers[7],
        },
        "state": {
            "pump_cmd": bool(co.bits[0]),
            "auto_mode": bool(co.bits[1]),
            "alarm_ack": bool(co.bits[2]),
            "low_level_alarm": bool(di.bits[0]),
            "high_level_alarm": bool(di.bits[1]),
            "high_temp_alarm": bool(di.bits[2]),
            "sensor_fault": bool(di.bits[3]),
            "pump_feedback": bool(di.bits[4]),
            "system_ok": bool(di.bits[5]),
            "status_word": status_word,
            "status_bits": decode_status_word(status_word),
        },
    }
    return snapshot


def print_snapshot(snapshot: dict) -> None:
    ts = snapshot["timestamp"]   
    p = snapshot["process"]
    s = snapshot["state"]
    t = snapshot["thresholds"]
    
    ai_status = snapshot.get("ai", {}).get("status", "N/A")
    level_rate = p.get("level_change_rate", 0.0)

    print(
        f"[{ts}] "
        f"level={p['level_mm']}mm ({p['level_percent']}%) | "
        f"temp={p['temperature_c']:.1f}C | "
        f"dist={p['distance_mm_raw']}mm | "
        f"rate={level_rate:.2f}mm/s | "
        f"pump_cmd={'ON' if s['pump_cmd'] else 'OFF'} | "
        f"pump_fb={'ON' if s['pump_feedback'] else 'OFF'} | "
        f"mode={'AUTO' if s['auto_mode'] else 'MANUAL'} | "
        f"low_alarm={int(s['low_level_alarm'])} | "
        f"high_alarm={int(s['high_level_alarm'])} | "
        f"temp_alarm={int(s['high_temp_alarm'])} | "
        f"fault={int(s['sensor_fault'])} | "
        f"ok={int(s['system_ok'])} | "
        f"low_th={t['low_level_threshold_percent']}% | "
        f"high_th={t['high_level_threshold_percent']}% | "
        f"high_temp_th={t['high_temp_threshold_c']:.1f}C | "
        f"status_word={s['status_word']}"
        f" | AI={ai_status}"
    )
    

def log_snapshot(snapshot: dict) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")


def log_telemetry_normalized(snapshot: dict) -> None:
    p = snapshot["process"]
    s = snapshot["state"]

    record = {
        "ts": snapshot["timestamp"],
        "event_type": "telemetry",
        "asset": "esp32_tank_station",
        "asset_ip": ESP32_IP,
        "proto": "modbus_tcp",
        "unit_id": DEVICE_ID,
        "level_mm": p["level_mm"],
        "level_pct": p["level_percent"],
        "temp_c": p["temperature_c"],
        "distance_mm": p["distance_mm_raw"],
        "level_change_rate": p.get("level_change_rate", 0.0),
        "pump_cmd": s["pump_cmd"],
        "pump_fb": s["pump_feedback"],
        "auto_mode": s["auto_mode"],
        "low_alarm": s["low_level_alarm"],
        "high_alarm": s["high_level_alarm"],
        "temp_alarm": s["high_temp_alarm"],
        "sensor_fault": s["sensor_fault"],
        "system_ok": s["system_ok"],
        "status_word": s["status_word"],
        "ai_model": snapshot.get("ai", {}).get("model"),
        "ai_anomaly": snapshot.get("ai", {}).get("anomaly"),
        "ai_status": snapshot.get("ai", {}).get("status"),
    }

    with NORM_LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def log_event(event: dict) -> None:
    record = {
        "ts": now_iso(),
        "event_type": "command",
        "asset": "esp32_tank_station",
        "asset_ip": ESP32_IP,
        "proto": "modbus_tcp",
        "unit_id": DEVICE_ID,
        **event
    }

    with NORM_LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def write_coil(client: ModbusTcpClient, address: int, value: bool, label: str, cmd: str = "") -> None:
    rr = client.write_coil(address=address, value=value, device_id=DEVICE_ID)
    check(rr, label)
    log_event({
        "event_type": "command",
        "command": cmd,
        "action": label,
        "coil_address": address,
        "value": value
    })


def pulse_alarm_ack(client: ModbusTcpClient) -> None:
    write_coil(client, 2, True, "alarm_ack ON", cmd="ack")
    time.sleep(0.2)
    write_coil(client, 2, False, "alarm_ack OFF", cmd="ack")


def print_help() -> None:
    print()
    print("Commands:")
    print("  a      -> set AUTO mode")
    print("  m      -> set MANUAL mode")
    print("  on     -> pump command ON")
    print("  off    -> pump command OFF")
    print("  ack    -> acknowledge alarm")
    print("  help   -> show commands")
    print("  q      -> quit")
    print()


command_queue: queue.Queue[str] = queue.Queue()


def input_worker() -> None:
    while True:
        try:
            cmd = input().strip().lower()
            command_queue.put(cmd)
        except EOFError:
            break

def handle_command(client: ModbusTcpClient, cmd: str) -> bool:
    if not cmd:
        return True

    if cmd == "q":
        return False
    if cmd == "help":
        print_help()
        return True
    if cmd == "a":
        write_coil(client, 1, True, "auto_mode ON", cmd="a")
        print("-> AUTO mode set")
        return True
    if cmd == "m":
        write_coil(client, 1, False, "auto_mode OFF", cmd="m")
        print("-> MANUAL mode set")
        return True
    if cmd == "on":
        write_coil(client, 0, True, "pump_cmd ON", cmd="on")
        print("-> Pump command ON")
        return True
    if cmd == "off":
        write_coil(client, 0, False, "pump_cmd OFF", cmd="off")
        print("-> Pump command OFF")
        return True
    if cmd == "ack":
        pulse_alarm_ack(client)
        print("-> Alarm acknowledged")
        return True

    print(f"Unknown command: {cmd}")
    print_help()
    return True


def main() -> None:
    print(f"Connecting to {ESP32_IP}:{ESP32_PORT} ...")
    client = ModbusTcpClient(host=ESP32_IP, port=ESP32_PORT, timeout=2)

    if not client.connect():
        raise RuntimeError(f"Could not connect to {ESP32_IP}:{ESP32_PORT}")

    print(f"Connected. Logging to: {LOG_FILE}")
    print_help()

    input_thread = threading.Thread(target=input_worker, daemon=True)
    input_thread.start()

    try:
        running = True
        while running:
            snapshot = read_snapshot(client)
            snapshot["process"]["level_change_rate"] = compute_level_change_rate(snapshot)
            ai_anomaly = detect_ai_anomaly(snapshot)
            snapshot["ai"] = {
                "model": "IsolationForest",
                "anomaly": ai_anomaly,
                "status": "ANOMALY" if ai_anomaly else "NORMAL",
            }

            print_snapshot(snapshot)
            log_alarm_transitions(snapshot)
            log_snapshot(snapshot)
            log_telemetry_normalized(snapshot)

            start = time.time()
            while time.time() - start < POLL_INTERVAL:
                try:
                    cmd = command_queue.get_nowait()
                except queue.Empty:
                    cmd = None
                
                if cmd is not None:
                    running = handle_command(client, cmd)
                if not running:
                    break
                time.sleep(0.05)

    finally:
        client.close()
        print("Disconnected.")


if __name__ == "__main__":
    main()