FROM python:3.10-alpine

WORKDIR /app

COPY ./pyproject.toml ./poetry.lock ./

# install Python dependencies
RUN apk update && apk --no-cache add --virtual .build_deps gcc g++ libffi-dev openssl \
        && pip install --upgrade pip && pip install poetry \
        && pip install -r <(poetry export | grep "numpy") \
        && pip install -r <(poetry export) \
        && apk --no-cache del .build_deps

# install application
COPY . .

# default command
CMD [ "gunicorn", "--worker-class=gevent", "--bind=0.0.0.0:5000", "--access-logfile=-", "--error-logfile=-", "simbad2k.simbad2k:app" ]
