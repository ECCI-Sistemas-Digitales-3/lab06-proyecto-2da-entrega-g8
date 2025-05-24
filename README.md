[![Open in Visual Studio Code](https://classroom.github.com/assets/open-in-vscode-2e0aaae1b6195c2367325f4f02e2d04e9abb55f0b24a779b69b11b9e10269abc.svg)](https://classroom.github.com/online_ide?assignment_repo_id=19621610&assignment_repo_type=AssignmentRepo)
# Laboratorio conexión MQTT

## Integrantes

[Brayan Cufiño](https://github.com/BACT99)

[Ivan Castaño ](https://github.com/IFC999)

## Documentación

### Diagrama de flujo



### Sensor de color RGB en Raspberry pi zero 2w por MQTT

- Configuración de los pines GPIO: el sensor TCS3200 usa S0 y S1 para seleccionar la frecuencia de salida (aquí se configura al 100% con HIGH/HIGH), S2 y S3 para seleccionar qué filtro de color está activo (rojo, verde, azul) y OUT proporciona una señal cuadrada cuya frecuencia varía según la intensidad del color.

<img src="sensor.png" alt="Sensor RGB" width="300"/>

- Se hace la configuración del MQTT definiendo el Broker, el host, el topic para la publicación y el topic para la suscripción 

- Para leer los colores tiene 3 fases, primero selecciona el filtro (el sensor tiene matrices de fotodiodos con filtros): 

    Rojo: S2=0, S3=0

    Verde: S2=1, S3=1

    Azul: S2=0, S3=1

- Luego en la función "count_pulses" mide durante un tiempo fijo (duration), cuenta cada transición de HIGH a LOW (flanco descendente) y devuelve el conteo total (proporcional a la intensidad del color).
- Luego le asigna un tiempo al conteo de pulsos para cada color y que tome la lectura
- Despues se hace un cálculo matemático para normalizar el valor que da el sensor y mostrarlo en valores de 0 a 255 

        normalized = ((value - raw_black) / (raw_white - raw_black)) * 255

- luego se hace la comunicación con el broker

        - sensor/color/rgb: Publica valores RGB (ej: {"r":125,"g":30,"b":200})
        - sensor/color/status: Estados del sistema ("ready", "reading", "stopped")
        - sensor/color/control: Comandos de control (start/stop/calibrate)

- Inicia el bucle principal del programa el cual verifica si hay una solicitud de lectura única (prioritaria), si está en modo continuo, lee y publica constantemente los valores leídos y normalizados en un archivo .json el cual se envía por MQTT para ser leído en un flujo de NodeRed. 
