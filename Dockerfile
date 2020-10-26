FROM python:3.8-slim

WORKDIR /app

# install Python dependencies
COPY requirements.txt .
RUN apt update && apt install openssl \
        && pip install --upgrade 'pip>=19.0.2' \
        && pip --no-cache-dir install -r requirements.txt \
        && apt clean

# install application
COPY . .

# default command
CMD [ "gunicorn", "--worker-class=gevent", "--bind=0.0.0.0:5000", "--access-logfile=-", "--error-logfile=-", "simbad2k:app" ]
