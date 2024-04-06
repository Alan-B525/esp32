# (C) Copyright Peter Hinch 2017-2019.
# Released under the MIT licence.

from mqtt_as import MQTTClient
from mqtt_local import config
import uasyncio as asyncio
import dht, machine, ujson
import btree

# Definir pines y configuraciones
DHT_PIN = 13
RELAY_PIN = 12

# Inicializar sensor DHT22 y relé
dht_sensor = dht.DHT22(machine.Pin(DHT_PIN))
relay = machine.Pin(RELAY_PIN, machine.Pin.OUT)

# Abrir base de datos BTree para almacenar parámetros
try:
    f = open("parameters.db", "r+b")
except OSError:
    f = open("parameters.db", "w+b")

parameters_db = btree.open(f)

# Función para leer los parámetros almacenados
def read_parameters():
    params = {}
    for key, value in parameters_db.items():
        params[key.decode()] = value.decode()
    return params

# Función para escribir los parámetros almacenados
def write_parameters(params):
    for key, value in params.items():
        parameters_db[key.encode()] = value.encode()
    parameters_db.flush()

# Función de callback para mensajes recibidos
def sub_cb(topic, msg, retained):
    print('Topic = {} -> Valor = {}'.format(topic.decode(), msg.decode()))
    params = read_parameters()
    message = ujson.loads(msg)
    if topic == b"setpoint":
        params["setpoint"] = message["setpoint"]
    elif topic == b"periodo":
        params["period"] = message["periodo"]
    elif topic == b"modo":
        params["mode"] = message["modo"]
    elif topic == b"rele":
        params["relay"] = message["rele"]
        if params["mode"] == "manual" and message["rele"] == "on":
            relay.on()
        elif params["mode"] == "manual" and message["rele"] == "off":
            relay.off()
        write_parameters(params)

# Función para manejar mensajes MQTT
async def conn_han(client):
    await client.subscribe('setpoint', 1)
    await client.subscribe('periodo', 1)
    await client.subscribe('modo', 1)
    await client.subscribe('rele', 1)

# Función para destellar el LED
async def flash_led():
    led_pin = machine.Pin(2, machine.Pin.OUT)
    for _ in range(5):
        led_pin.on()
        await asyncio.sleep(0.5)
        led_pin.off()
        await asyncio.sleep(0.5)

# Función para publicar datos
async def publish_data(client):
    while True:
        try:
            dht_sensor.measure()
            temperature = dht_sensor.temperature()
            humidity = dht_sensor.humidity()
            params = read_parameters()
            payload = {
                "temperatura": temperature,
                "humedad": humidity,
                "setpoint": params.get("setpoint", "N/A"),
                "periodo": params.get("periodo", "N/A"),
                "modo": params.get("mode", "N/A")
            }
            await client.publish('ID_del_dispositivo', ujson.dumps(payload), qos=1)
            if params["mode"] == "automatico" and temperature > float(params["setpoint"]):
                relay.on()
            else:
                relay.off()
            await asyncio.sleep(float(params.get("periodo", "60")))  # Esperar antes de enviar la próxima lectura
        except OSError as e:
            print("Error de lectura del sensor:", e)
            await asyncio.sleep(5)  # Esperar antes de intentar de nuevo

# Define configuración
config['subs_cb'] = sub_cb
config['connect_coro'] = conn_han
config['ssl'] = True

# Configurar cliente MQTT
MQTTClient.DEBUG = True  # Opcional
client = MQTTClient(config)

# Ejecutar el bucle principal
try:
    asyncio.run(publish_data(client))
finally:
    client.close()
    f.close()  # Cerrar la base de datos BTree
    asyncio.new_event_loop()
