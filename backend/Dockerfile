FROM python:3.13

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ./app /app

RUN chmod +x /app/scripts/start.sh
RUN chmod +x /app/scripts/prestart.sh

CMD ["/app/scripts/start.sh"]