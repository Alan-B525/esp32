import dht, machine, time

d = dht.DHT22(machine.Pin(25))



while True:
    measure = d.measure()
    temp = d.temperature()
    humedad = d.humidity()

    print('------Datos------')
    print('Measure', measure)
    print('Temperatura', temp)
    print('Humedad', humedad)
    print('------------------')
    time.sleep_ms(3000)