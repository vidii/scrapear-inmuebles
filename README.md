# scrapear-inmuebles
Buscador de inmuebles + alertas en bot de telegram


## Para usar en un entorno propio -> /src
1. Crear un ambiente e instalar requirements.txt
2. Modificar el script segun los parametros de la busqueda que se quieran. 
3. Setear las variables de entorno `TELEGRAM_BOT_TOKEN`y `TELEGRAM_CHAT_ID`
4. Crear un cron para llamar al script `home_finder.py` cada 1 hora

## Con Docker
1. Clonar el repositorio
2. Copiar .env.example a .env y completar  `TELEGRAM_BOT_TOKEN`y `TELEGRAM_CHAT_ID`
3. Build via `docker compose build`
4. Ejecutar con `docker-compose up`

Listo, server con cron cada 1 hora ya está funcionando


###Cron
El intervalo del cron se puede modificar en `./crontab`