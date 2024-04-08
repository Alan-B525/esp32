import time
import json
import machine
from machine import Pin
import dht
import uasyncio as asyncio
from umqtt.robust import MQTTClient

# Cargar los parametros de configuracion desde el archivo settings.py
try:
    from settings import SERVIDOR_MQTT, CLIENT_ID
except ImportError:
    print("Error: No se pudo cargar el archivo de configuracion settings.py")
    raise

# Definir pines y configuraciones
RELE_PIN = 14
DHT_PIN = 25
LED_PIN = 2  # Pin para el LED

# Inicializar el cliente MQTT
mqtt = MQTTClient(CLIENT_ID, SERVIDOR_MQTT, port=1883, keepalive=60, ssl=False)

# Inicializar el sensor DHT22
dht_sensor = dht.DHT22(machine.Pin(DHT_PIN))

# Inicializar el LED
led = Pin(LED_PIN, Pin.OUT)
relay = Pin(RELE_PIN, Pin.OUT)

# Estado inicial del termostato
setpoint = 30  # Setpoint inicial de temperatura
periodo = 60  # Periodo de publicación en segundos
modo = "automatico"  # Modo inicial (manual o automatico)
relay_estado = False  # Estado inicial del relé

# Función para manejar los mensajes recibidos
def handle_message(topic, msg):
    global setpoint, periodo, modo, relay_estado
    try:
        payload = json.loads(msg)
        if topic == b"setpoint":
            setpoint = payload.get("setpoint", setpoint)
        elif topic == b"periodo":
            periodo = payload.get("periodo", periodo)
        elif topic == b"modo":
            modo = payload.get("modo", modo)
        elif topic == b"rele" and modo == "manual":
            relay_estado = payload.get("estado", relay_estado)
            controlar_rele()
        elif topic == b"destello":
            destello()
        print("Variables actualizadas:")
        print("Setpoint:", setpoint)
        print("Periodo:", periodo)
        print("Modo:", modo)
        print("Estado del rele:", relay_estado)
    except ValueError:
        print("Error: Mensaje MQTT no valido.")

# Función para realizar un destello del LED
def destello():
    print("Destellando LED")
    for _ in range(3):
        led.value(1)
        time.sleep_ms(500)
        led.value(0)
        time.sleep_ms(500)

# Función para controlar el relé
def controlar_rele():
    global relay_estado
    if modo == "automatico":
        relay_estado = dht_sensor.temperature() > setpoint
    relay.value(relay_estado)

# Función para publicar los datos
async def publicar_datos():
    while True:
        try:
            dht_sensor.measure()
            temperatura = dht_sensor.temperature()
            humedad = dht_sensor.humidity()
            data = {
                "temperatura": temperatura,
                "humedad": humedad,
                "setpoint": setpoint,
                "periodo": periodo,
                "modo": modo,
            }
            mqtt.connect()
            mqtt.publish(CLIENT_ID, json.dumps(data))
            mqtt.disconnect()
            controlar_rele()  # Controlar el relé antes de esperar
            await asyncio.sleep(periodo)
        except OSError:
            print("Error al publicar datos.")
            await asyncio.sleep(5)

# Función para suscribirse a los mensajes MQTT
async def suscribir_mqtt():
    mqtt.set_callback(handle_message)
    mqtt.connect()
    mqtt.subscribe(b"setpoint")
    mqtt.subscribe(b"periodo")
    mqtt.subscribe(b"modo")
    mqtt.subscribe(b"rele")
    mqtt.subscribe(b"destello")
    while True:
        try:
            mqtt.wait_msg()
        except OSError:
            print("Error de conexion MQTT.")
            await asyncio.sleep(5)

# Función principal
async def main():
    await asyncio.gather(publicar_datos(), suscribir_mqtt())

# Iniciar el bucle de eventos asyncio
asyncio.run(main())
