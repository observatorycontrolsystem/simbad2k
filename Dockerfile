FROM python:3.6-alpine

WORKDIR /app

# install Python dependencies
COPY requirements.txt .
RUN apk --no-cache add libffi openssl \
        && apk --no-cache add --virtual .build-deps gcc libffi-dev musl-dev openssl-dev \
        && pip install --upgrade 'pip>=19.0.2' \
        && pip --no-cache-dir install -r requirements.txt \
        && apk --no-cache del .build-deps

# install application
COPY . .

# default command
CMD [ "gunicorn", "--worker-class=gevent", "--bind=0.0.0.0:5000", "--access-logfile=-", "--error-logfile=-", "simbad2k:app" ]
