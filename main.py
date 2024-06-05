import json
import machine
import btree
from machine import Pin
import dht
import uasyncio as asyncio
from umqtt.robust import MQTTClient

# Cargar los parámetros de configuración desde el archivo settings.py
try:
    from settings import BROKER, CLIENT_ID, PORT
except ImportError:
    print("Error: No se pudo cargar el archivo de configuración settings.py")
    raise

# Definir pines y configuraciones
RELE_PIN = 14
DHT_PIN = 25
LED_PIN = 2  # Pin para el LED

# Inicializar el cliente MQTT
mqtt = MQTTClient(CLIENT_ID, BROKER, port=PORT, keepalive=60, ssl=False)

# Inicializar el sensor DHT22
dht_sensor = dht.DHT22(machine.Pin(DHT_PIN))

# Inicializar el LED y el relé
led = Pin(LED_PIN, Pin.OUT)
relay = Pin(RELE_PIN, Pin.OUT)

# Almacenar y cargar parámetros en memoria no volátil
def init_storage():
    try:
        f = open("settings.db", "r+b")
    except OSError:
        f = open("settings.db", "w+b")
    return btree.open(f)

db = init_storage()

# Estado inicial del termostato
setpoint = int(db.get(b"setpoint", b"32"))
periodo = int(db.get(b"periodo", b"5"))
modo = db.get(b"modo", b"automatico").decode('utf-8')
relay_estado = bool(int(db.get(b"relay_estado", b"0")))

# Función para actualizar y almacenar los parámetros
def update_params(key, value):
    db[key] = str(value)
    db.flush()

# Función para manejar los mensajes recibidos
def handle_message(topic, msg):
    global setpoint, periodo, modo, relay_estado
    try:
        payload = json.loads(msg)
        if topic == b"setpoint":
            setpoint = payload.get("setpoint", setpoint)
            update_params(b"setpoint", setpoint)
        elif topic == b"periodo":
            periodo = payload.get("periodo", periodo)
            update_params(b"periodo", periodo)
        elif topic == b"modo":
            modo = payload.get("modo", modo)
            update_params(b"modo", modo)
        elif topic == b"rele" and modo == "manual":
            relay_estado = payload.get("estado", relay_estado)
            update_params(b"relay_estado", int(relay_estado))
            controlar_rele()
        elif topic == b"destello":
            asyncio.create_task(destello())
        print("Variables actualizadas:")
        print(f"Setpoint: {setpoint}, Periodo: {periodo}, Modo: {modo}, Estado del rele: {relay_estado}")
    except (ValueError, KeyError) as e:
        print(f"Error: Mensaje MQTT no válido. {e}")

# Función para realizar un destello del LED
async def destello():
    print("Destellando LED")
    for _ in range(3):
        led.value(1)
        await asyncio.sleep(0.5)
        led.value(0)
        await asyncio.sleep(0.5)

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
            mqtt.publish(CLIENT_ID.encode(), json.dumps(data).encode())
            controlar_rele()  # Controlar el relé antes de esperar
        except OSError as e:
            print(f"Error al publicar datos: {e}")
        await asyncio.sleep(periodo)

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
            mqtt.check_msg()  # check_msg instead of wait_msg for non-blocking call
        except OSError as e:
            print(f"Error de conexión MQTT: {e}")
            await asyncio.sleep(5)

# Función principal
async def main():
    # Publicar un mensaje inicial
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
    mqtt.publish(CLIENT_ID.encode(), json.dumps(data).encode())

    # Crear tareas asincrónicas
    tasks = [
        asyncio.create_task(publicar_datos()),
        asyncio.create_task(suscribir_mqtt())
    ]
    await asyncio.gather(*tasks)

# Iniciar el bucle de eventos asyncio
asyncio.run(main())
