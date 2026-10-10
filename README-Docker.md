# Docker - Zulip Server UNAL

## 1. Objetivo

Este documento describe la construcción y ejecución local de Zulip Server mediante Docker y Docker Compose para el proyecto de Fundamentos de DevOps y SRE.

La solución utiliza los siguientes servicios:

- Zulip Server
- PostgreSQL
- RabbitMQ
- Redis
- Memcached
- `zulip-init` como servicio temporal de inicialización

## 2. Arquitectura de contenedores

La solución se ejecuta mediante varios contenedores desacoplados:

```text
                         Navegador
                             |
                           HTTPS
                             |
                             v
                       +-----------+
                       |   Zulip   |
                       +-----+-----+
                             |
       +---------------------+---------------------+
       |                     |                     |
       v                     v                     v
  PostgreSQL             RabbitMQ                Redis
  Persistencia           Mensajería             Datos temporales
       |
       +----------------------------------------------+
                                                      |
                                                      v
                                                  Memcached
                                                    Caché
```

El proceso de arranque se controla mediante `healthchecks` y dependencias:

```text
PostgreSQL ── healthy ─┐
RabbitMQ   ── healthy ─┤
Redis      ── healthy ─┼──► zulip-init
Memcached  ── healthy ─┘        │
                                │ app:init
                                │ Exited (0)
                                ▼
                              Zulip
                                │
                                ▼
                             healthy
```

## 3. Dockerfile

La imagen de Zulip se construye utilizando un proceso **multi-stage**.

### Stage 1 - Build

- Parte de Ubuntu 24.04.
- Instala las herramientas necesarias para construir Zulip.
- Clona el repositorio del equipo.
- Hace checkout del release 12.3.
- Ejecuta el proceso de provisionamiento.
- Genera el artefacto de release de Zulip.

### Stage 2 - Runtime

- Parte de la imagen base.
- Copia únicamente el artefacto generado en la etapa anterior.
- Instala Zulip.
- Elimina archivos temporales.
- Configura `HEALTHCHECK`.
- Expone los puertos 25, 80 y 443.

La construcción multi-stage permite separar las herramientas de construcción de la imagen utilizada para ejecución.

## 4. Construcción de la imagen

Validar primero el Dockerfile:

```powershell
docker build --check -f .\docker\Dockerfile .\docker
```

Construir la imagen:

```powershell
docker build `
  -f .\docker\Dockerfile `
  -t zulip-unal:12.3 `
  .\docker
```

Verificar la imagen:

```powershell
docker images zulip-unal
```

## 5. Configuración

Crear un archivo `.env` local basado en `.env.example`.

Ejemplo:

```env
ZULIP__POSTGRES_PASSWORD=<valor>
ZULIP__MEMCACHED_PASSWORD=<valor>
ZULIP__RABBITMQ_PASSWORD=<valor>
ZULIP__REDIS_PASSWORD=<valor>
ZULIP__SECRET_KEY=<valor>
ZULIP__EMAIL_PASSWORD=<valor>
```

El archivo `.env` contiene valores sensibles y **no debe almacenarse en Git**.

El archivo `.env.example` sí debe permanecer versionado como plantilla para los integrantes del equipo.

## 6. Docker Compose

Docker Compose administra los siguientes servicios:

```text
database
memcached
rabbitmq
redis
zulip-init
zulip
```

Validar la configuración:

```powershell
docker compose config
```

Listar los servicios:

```powershell
docker compose config --services
```

## 7. Inicialización automática

La inicialización de Zulip se realiza automáticamente mediante el servicio temporal `zulip-init`.

Al ejecutar:

```powershell
docker compose up -d --wait
```

Docker Compose realiza el siguiente flujo:

1. Inicia PostgreSQL, RabbitMQ, Redis y Memcached.
2. Espera que los cuatro servicios estén en estado `healthy`.
3. Ejecuta `zulip-init` con el comando `app:init`.
4. Espera que `zulip-init` termine correctamente.
5. Inicia el servicio principal `zulip`.

El servicio `zulip-init` debe finalizar con código `0`.

Para comprobarlo:

```powershell
docker compose ps -a
```

El estado esperado es similar a:

```text
database      Up ... (healthy)
memcached     Up ... (healthy)
rabbitmq      Up ... (healthy)
redis         Up ... (healthy)
zulip-init    Exited (0)
zulip         Up ... (healthy)
```

La inicialización es idempotente: si `app:init` se ejecuta nuevamente sobre una instalación ya inicializada, valida la configuración y no vuelve a aplicar migraciones que ya existen.

## 8. Ejecución del entorno

Levantar la solución completa:

```powershell
docker compose up -d --wait
```

Consultar el estado:

```powershell
docker compose ps
```

Consultar también los servicios finalizados:

```powershell
docker compose ps -a
```

Detener el entorno:

```powershell
docker compose down
```

No utilizar:

```powershell
docker compose down -v
```

salvo que se quiera eliminar también la información persistente del laboratorio.

## 9. Creación de la organización en Zulip

Después de inicializar y levantar correctamente los contenedores, la primera instalación todavía no tendrá una organización creada.

Si al abrir:

```text
https://localhost.localdomain
```

aparece un mensaje indicando que no existe ninguna organización, se debe generar un enlace de creación.

Ejecutar:

```powershell
docker compose exec -u zulip zulip `
  /home/zulip/deployments/current/manage.py `
  generate_realm_creation_link
```

El comando devolverá una URL temporal similar a:

```text
https://localhost.localdomain/new/...
```

Abrir esa URL en el navegador.

> En el laboratorio se utiliza un certificado autofirmado, por lo que el navegador puede mostrar una advertencia de seguridad. Se debe continuar al sitio para completar la configuración.

En el formulario de Zulip:

1. Definir el nombre de la organización.
2. Crear el usuario administrador inicial.
3. Configurar el correo del administrador.
4. Definir la contraseña.
5. Completar la creación de la organización.

Una vez creada, se podrá acceder normalmente mediante:

```text
https://localhost.localdomain
```

### Validación

Comprobar que:

- La organización aparece correctamente.
- El usuario administrador puede iniciar sesión.
- Zulip mantiene la organización después de recrear los contenedores:

```powershell
docker compose down
docker compose up -d --wait
```

Si la organización continúa disponible, se confirma que los datos persistentes están siendo conservados correctamente en los volúmenes.

## 10. Persistencia

Se utilizan volúmenes Docker para conservar información entre recreaciones de contenedores:

- `zulip-data`
- `postgresql-data`
- `rabbitmq-data`
- `redis-data`

Consultar los volúmenes:

```powershell
docker volume ls
```

Los contenedores pueden eliminarse y recrearse sin eliminar la organización ni los datos almacenados mientras los volúmenes permanezcan.

> `docker compose down -v` elimina los volúmenes y, por tanto, los datos persistentes del laboratorio.

## 11. Healthchecks

Se utilizan verificaciones de salud para determinar si los servicios están realmente disponibles y no solo ejecutándose.

### PostgreSQL

```text
pg_isready -U zulip -d zulip
```

### RabbitMQ

```text
rabbitmq-diagnostics -q ping
```

### Redis

La comprobación utiliza autenticación mediante el secret configurado:

```text
redis-cli ping
```

El resultado esperado es:

```text
PONG
```

### Memcached

Se verifica que el servicio esté escuchando en el puerto 11211:

```text
nc -z 127.0.0.1 11211
```

### Dependencias de Zulip

El servicio principal utiliza dependencias condicionadas:

- PostgreSQL: `service_healthy`
- RabbitMQ: `service_healthy`
- Redis: `service_healthy`
- Memcached: `service_healthy`
- `zulip-init`: `service_completed_successfully`

Esto evita que Zulip se inicie antes de que sus dependencias estén realmente disponibles y antes de completar la inicialización.

## 12. HTTPS

Para el laboratorio local se utiliza un certificado autofirmado:

```yaml
CERTIFICATES: "self-signed"
```

Acceso:

```text
https://localhost.localdomain
```

El navegador mostrará una advertencia porque el certificado no está firmado por una autoridad de certificación pública.

Para un ambiente productivo se recomienda utilizar un certificado válido o un reverse proxy que termine TLS y configure explícitamente los proxies confiables.

## 13. Secrets

Las credenciales se administran mediante Docker Secrets y variables provenientes del archivo `.env`.

Los secrets utilizados son:

- `zulip__postgres_password`
- `zulip__memcached_password`
- `zulip__rabbitmq_password`
- `zulip__redis_password`
- `zulip__secret_key`
- `zulip__email_password`

El objetivo es evitar almacenar contraseñas directamente dentro del Dockerfile o del archivo `docker-compose.yml`.

## 14. Comandos de diagnóstico

Estado general:

```powershell
docker compose ps
docker compose ps -a
```

Logs de Zulip:

```powershell
docker compose logs zulip
docker compose logs -f zulip
```

Logs de un servicio específico:

```powershell
docker compose logs database
docker compose logs rabbitmq
docker compose logs redis
docker compose logs memcached
```

Uso de recursos:

```powershell
docker stats
```

Inspección de un contenedor:

```powershell
docker inspect <contenedor>
```

Acceso al contenedor de Zulip:

```powershell
docker compose exec zulip bash
```

## 15. Eliminación del entorno

Eliminar contenedores y red conservando datos:

```powershell
docker compose down
```

Eliminar contenedores, red y volúmenes:

```powershell
docker compose down -v
```

El segundo comando elimina los datos persistentes del laboratorio, incluida la organización creada.

## 16. Flujo recomendado para un integrante nuevo

Un compañero que clone el repositorio puede validar el entorno siguiendo este flujo:

```powershell
git clone https://github.com/facaslo/zulip-server-unal.git
cd zulip-server-unal
```

Crear `.env` a partir de `.env.example` y asignar valores seguros.

Construir y levantar:

```powershell
docker compose up -d --build --wait
```

Validar:

```powershell
docker compose ps -a
```

Generar el enlace para crear la primera organización:

```powershell
docker compose exec -u zulip zulip `
  /home/zulip/deployments/current/manage.py `
  generate_realm_creation_link
```

Abrir:

```text
https://localhost.localdomain
```

y completar la creación de la organización.

## 17. Resultado

La solución permite construir y levantar Zulip Server junto con PostgreSQL, RabbitMQ, Redis y Memcached mediante un único comando:

```powershell
docker compose up -d --build --wait
```

Docker Compose controla el orden de inicio mediante `healthchecks`, ejecuta automáticamente la inicialización de Zulip mediante `zulip-init` y conserva los datos mediante volúmenes persistentes.

El entorno incorpora además:

- construcción multi-stage;
- Docker Secrets;
- HTTPS con certificado autofirmado para laboratorio;
- healthchecks;
- dependencias condicionadas por salud;
- inicialización automática;
- persistencia de datos;
- comandos de diagnóstico y operación.
