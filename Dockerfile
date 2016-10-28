FROM python:3.5
MAINTAINER Austin Riba <ariba@lcogt.net>

EXPOSE 80
ENTRYPOINT [ "/usr/bin/supervisord", "-n" ]
WORKDIR /var/www/simbad2k

RUN apt-get update && apt-get install -y supervisor nginx

COPY requirements.txt /var/www/simbad2k
RUN pip install -r /var/www/simbad2k/requirements.txt --trusted-host=buildsba.lco.gtn

run echo "daemon off;" >> /etc/nginx/nginx.conf
run rm /etc/nginx/sites-enabled/default
COPY docker/nginx-app.conf /etc/nginx/sites-enabled/
COPY docker/supervisor-app.conf /etc/supervisor/conf.d/
COPY docker/uwsgi.ini /etc/
COPY . /var/www/simbad2k/