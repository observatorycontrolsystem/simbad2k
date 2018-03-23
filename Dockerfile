FROM python:3.5
MAINTAINER Las Cumbres Observatory <webmaster@lco.global>

EXPOSE 80
ENTRYPOINT [ "/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf" ]

RUN apt-get update \
        && apt-get -y install git nginx supervisor \
        && apt-get -y clean \
        && rm -rf /var/lib/apt/lists/*

RUN rm -f /etc/nginx/sites-enabled/default

COPY requirements.txt /var/www/simbad2k/
RUN pip --no-cache-dir --trusted-host=buildsba.lco.gtn install -r /var/www/simbad2k/requirements.txt

COPY docker/ /
COPY . /var/www/simbad2k/
