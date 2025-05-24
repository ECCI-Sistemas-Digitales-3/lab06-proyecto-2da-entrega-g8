import RPi.GPIO as GPIO
import time
import paho.mqtt.client as mqtt
import json
import os
from datetime import datetime

# Configuracion de pines
S0, S1, S2, S3 = 17, 18, 27, 22
OUT = 23
OE = 24  # Opcional

# Configuracion MQTT
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC_RGB = "sensor/color/rgb"
TOPIC_STATUS = "sensor/color/status"
TOPIC_CONTROL = "sensor/color/control"

# Archivo de calibracion
CALIB_FILE = "/home/brayan_cufino/Desktop/tcs3200_calibration.json"

# Variables de estado
calibration = {
    'white': {'r': 255, 'g': 255, 'b': 255},  # Valores normalizados
    'black': {'r': 0, 'g': 0, 'b': 0},
    'raw_white': {'r': 1, 'g': 1, 'b': 1},    # Valores crudos
    'raw_black': {'r': 0, 'g': 0, 'b': 0}
}

reading_active = False
single_reading_requested = False

def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(S0, GPIO.OUT)
    GPIO.setup(S1, GPIO.OUT)
    GPIO.setup(S2, GPIO.OUT)
    GPIO.setup(S3, GPIO.OUT)
    GPIO.setup(OUT, GPIO.IN)

    if 'OE' in globals():
        GPIO.setup(OE, GPIO.OUT)
        GPIO.output(OE, GPIO.LOW)
    GPIO.output(S0, GPIO.HIGH)
    GPIO.output(S1, GPIO.HIGH)  # 100% frecuencia

def load_calibration():
    global calibration
    if os.path.exists(CALIB_FILE):
        try:
            with open(CALIB_FILE, 'r') as f:
                calibration = json.load(f)
            print("\nCalibracion cargada:")
            print(f"Blanco: R={calibration['white']['r']} G={calibration['white']['g']} B={calibration['white']['b']}")
            print(f"Negro: R={calibration['black']['r']} G={calibration['black']['g']} B={calibration['black']['b']}")
        except Exception as e:
            print(f"\nError cargando calibracion: {str(e)}")

def save_calibration():
    try:
        with open(CALIB_FILE, 'w') as f:
            json.dump(calibration, f, indent=4)
        print("\nCalibracion guardada")
    except Exception as e:
        print(f"\nError guardando calibracion: {str(e)}")

def count_pulses(duration=0.1):
    count = 0
    timeout = time.time() + duration
    while time.time() < timeout:
        if GPIO.input(OUT) == GPIO.LOW:
            count += 1
            while GPIO.input(OUT) == GPIO.LOW and time.time() < timeout:
                time.sleep(0.0001)
    return count

def read_raw_colors():
    # Leer rojo
    GPIO.output(S2, GPIO.LOW)
    GPIO.output(S3, GPIO.LOW)
    time.sleep(0.05)
    r = count_pulses(0.15)

    # Leer verde
    GPIO.output(S2, GPIO.HIGH)
    GPIO.output(S3, GPIO.HIGH)
    time.sleep(0.03)
    g = count_pulses(0.1)

    # Leer azul
    GPIO.output(S2, GPIO.LOW)
    GPIO.output(S3, GPIO.HIGH)
    time.sleep(0.03)
    b = count_pulses(0.1)

    return r, g, b

def normalize_rgb(r, g, b):
    def normalize_value(value, color):
        raw_white = calibration['raw_white'][color]
        raw_black = calibration['raw_black'][color]
        if raw_white == raw_black:
            return 0
        normalized = int(((value - raw_black) / (raw_white - raw_black)) * 255)
        return max(0, min(255, normalized))

    return {
        'r': normalize_value(r, 'r'),
        'g': normalize_value(g, 'g'),
        'b': normalize_value(b, 'b'),
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'type': 'single' if single_reading_requested else 'continuous'
    }

def calibrate(color_type):
    print(f"\nCalibrando {color_type.upper()}...")
    samples = []
    for _ in range(5):
        r, g, b = read_raw_colors()
        samples.append({'r': r, 'g': g, 'b': b})
        time.sleep(0.2)

    avg_r = sum(s['r'] for s in samples) // 5
    avg_g = sum(s['g'] for s in samples) // 5
    avg_b = sum(s['b'] for s in samples) // 5

    calibration[f'raw_{color_type}'] = {'r': avg_r, 'g': avg_g, 'b': avg_b}
    calibration[color_type] = {'r': 255 if color_type == 'white' else 0,
                              'g': 255 if color_type == 'white' else 0,
                              'b': 255 if color_type == 'white' else 0}
    save_calibration()
    print(f"Calibracion {color_type.upper()} completada")

def on_connect(client, userdata, flags, rc):
    client.subscribe(TOPIC_CONTROL)
    client.publish(TOPIC_STATUS, json.dumps({'status': 'ready'}))

def on_message(client, userdata, msg):
    global reading_active, single_reading_requested

    try:
        command = json.loads(msg.payload)
        action = command.get('action', '')

        if action == 'start':
            reading_active = True
            single_reading_requested = False
            client.publish(TOPIC_STATUS, json.dumps({'status': 'reading'}))
        elif action == 'stop':
            reading_active = False
            client.publish(TOPIC_STATUS, json.dumps({'status': 'stopped'}))
        elif action == 'read_once':
            single_reading_requested = True
        elif action == 'calibrate_white':
            calibrate('white')
        elif action == 'calibrate_black':
            calibrate('black')

    except Exception as e:
        print(f"Error procesando mensaje: {str(e)}")

def perform_single_reading(client):
    global single_reading_requested
    r, g, b = read_raw_colors()
    rgb_norm = normalize_rgb(r, g, b)
    client.publish(TOPIC_RGB, json.dumps(rgb_norm))
    print(f"\nLectura unica: R={rgb_norm['r']:3d} G={rgb_norm['g']:3d} B={rgb_norm['b']:3d}")
    single_reading_requested = False

def main():
    setup_gpio()
    load_calibration()

    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()

        print("\nSistema TCS3200 - Control Completo")
        print("Comandos MQTT disponibles:")
        print("- start: Lectura continua")
        print("- stop: Detener lectura")
        print("- read_once: Lectura unica")
        print("- calibrate_white: Calibrar blanco")
        print("- calibrate_black: Calibrar negro")
    
        while True:
            if single_reading_requested:
                perform_single_reading(mqtt_client)
            elif reading_active:
                r, g, b = read_raw_colors()
                rgb_norm = normalize_rgb(r, g, b)
                mqtt_client.publish(TOPIC_RGB, json.dumps(rgb_norm))
                print(f"\rContinuo: R={rgb_norm['r']:3d} G={rgb_norm['g']:3d} B={rgb_norm['b']:3d}", end='')

            time.sleep(0.1)            

    except KeyboardInterrupt:
        print("\nDeteniendo...")
    finally:
        mqtt_client.disconnect()
        GPIO.cleanup()

if __name__ == "__main__":
    main()

