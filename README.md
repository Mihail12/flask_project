# inactive_doc_backend

Firstly, start eias project and add there 
/admin/oauth2_provider/application/

```
applications with  
name = inactive_doc_backend  
client_id = spYyuoVOMZ2s1BspNkBVkcsVlZUsQNpKdbTjY8fY  
client_secret = YYdg17KorLmq38NLAwLwmtvn4VuWZ44DazgissPwOhElX3zKZ4aBrX8UFudzMJqTvdK0Nktn2xEFge1SVgWEiwWue0hutgYpMqY4hgua8wRO7v8fnxteq265W7uUctuR  
```

as it on the picture  
![](readme_img/add_appliaction_eias.PNG)  
than save changes  
Configurate flask project:

add an interpreter in pycharm:  
![](readme_img/pycharm_settings.PNG)  
![](readme_img/adding_interpreter_docker.PNG)  

after interpreter you could configure flask project  

![](readme_img/flask_configuration.PNG)  

now you able to start flask in debug mode

# Deploy and Development
To start project you should have **config.conf** in project directory:
The example of such config:
```
POSTGRES_USER=test
POSTGRES_PASSWORD=password
POSTGRES_HOST=inactive_db
POSTGRES_PORT=5432
POSTGRES_DB=inactive_db

RABBITMQ_DEFAULT_USER=rabbitmq
RABBITMQ_DEFAULT_PASS=rabbitmq
FLOWER_PORT=8888
CELERY_BROKER_URL=amqp://rabbitmq:rabbitmq@rabbit:5672/

FLASK_ENV=development

EIAS_BASE_URL=http://192.168.66.20/

AUTHLIB_INSECURE_TRANSPORT=1
OAUTHLIB_INSECURE_TRANSPORT=1

FRONTED_URL=http://localhost:3000/
SECRET_KEY=secret

EIAS_OAUTH2_KEY=spYyuoVOMZ2s1BspNkBVkcsVlZUsQNpKdbTjY8fY
EIAS_OAUTH2_SECRET=YYdg17KorLmq38NLAwLwmtvn4VuWZ44DazgissPwOhElX3zKZ4aBrX8UFudzMJqTvdK0Nktn2xEFge1SVgWEiwWue0hutgYpMqY4hgua8wRO7v8fnxteq265W7uUctuR
```


In order to save user ip if you up the docker you should have nginx outside docker container? directly in machine  
It should be like:
```
http {
    upstream backend {
        server 127.0.0.1:5000;
    }
    server {
        listen 80;
        server_name _;
        set_real_ip_from 0.0.0.0/0;
        
        location / {
            proxy_pass http://backend;
            proxy_set_header   Connection "";
            proxy_http_version 1.1;
            proxy_set_header        Host            $http_host;
            proxy_set_header        X-Real-IP       $remote_addr;
            proxy_set_header        X-Forwarded-For $proxy_add_x_forwarded_for;
        }
            location ^~ /static/  {
            root /root/inactive_doc_backend/;
        }
    }
}
```

# Passport urls that used
  
/api/v1/get_state/  
/api/v1/get_state/<int:id>/  
/api/v1/service/get_dmsudep/ 
/api/v1/service/get_dmsudep/<int:id>/  
/api/v1/service/get_doc_type/  
/api/v1/service/get_doc_type/<int:id>/  
/api/v1/service/get_doc_status/  
/api/v1/service/get_doc_status/<int:id>/  
/api/v1/get_user/  
/api/v1/get_user/<int:id>/  
/logout/  
/get_session/<user_id>/
/api/v1/get_passport/


# Develop with pycharm debugger

For develop in pycharm and use its debugger you could use docker-compose as an interpreter  
for this you should create an interpreter from **web** container and in docker-compose uncomment this code:
```
#        command: >
#            /bin/bash -c "
#                apt-get update;
#                apt-get --assume-yes install netcat;
#                while ! nc -z web 5000;
#                do
#                  echo sleeping;
#                  sleep 1;
#                done;
#                echo Connected!;
#                nginx -g 'daemon off;'"
```

And also uncomment in **web** all additional services you need
```
depends_on:
    - database
#   - nginx
#   - worker
#   - rabbit
#   - flower
```

and comment 
#    links:
#        - web


otherwise the project should up by command:

`docker-compose up`

and stop with

`docker-compose stop`

to remove containers use

`docker-compose rm`


# Tests

to run tests please use
`docker-compose run --rm --entrypoint "python3 -m unittest" web`

Also you could create *venv* and run tests under virtual python environment

# Migrations

Flask project allows migrations

if you have changed database in production use following commands:

`flask db init` (only once you have to inti migrations)

after each changes use:

`flask db migrate`
`flask db upgrade`  

*Note: you should do it only in base project dir*