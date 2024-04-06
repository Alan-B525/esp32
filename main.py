from machine import Pin
import dht
import time

d = dht.DHT22(Pin(25))
rele = Pin(14, Pin.OUT)
rele.value(0)

while(True):
    rele.value(not rele.value())
    d.measure()
    temperatura=d.temperature()
    print(f"la temperatura actual es de {temperatura} °C")
    humedad=d.humidity()
    print(f"la humedad actual es de {humedad} %")
    time.sleep(1)
