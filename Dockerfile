FROM python:3.7

ARG SEND_CRON_TEST
ARG TELEGRAM_CHAT_ID
ARG TELEGRAM_BOT_TOKEN

RUN apt-get update && apt-get -y install cron vim
WORKDIR /app
COPY crontab /etc/cron.d/crontab
COPY src /app/
RUN pip install -r requirements.txt
RUN chmod 0644 /etc/cron.d/crontab
RUN /usr/bin/crontab /etc/cron.d/crontab
COPY run.sh /app/
COPY cron_job.sh /app/
COPY .env /app/
RUN chmod 755 cron_job.sh
