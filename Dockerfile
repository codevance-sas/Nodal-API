# --- Etapa 1: Builder ---
# Usamos una imagen base para instalar dependencias.
# Esto incluye herramientas de compilación que no necesitamos en la imagen final.
FROM python:3.11-alpine AS builder

WORKDIR /app

# Alpine necesita estas dependencias para compilar algunos paquetes de Python (ej. psycopg2)
RUN apk add --no-cache gcc musl-dev python3-dev

# Copiamos solo el archivo de requisitos para aprovechar el caché de Docker
COPY requirements.txt .

# Instalamos las dependencias
RUN pip install --no-cache-dir -r requirements.txt


# --- Etapa 2: Final ---
# Esta es la imagen final, mucho más pequeña y segura.
FROM python:3.11-alpine

WORKDIR /app

# Creamos un usuario y grupo específicos para la aplicación para no usar 'root'.
# Esta es una práctica de seguridad importante.
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# Copiamos las dependencias instaladas desde la etapa 'builder'
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copiamos solo el código de nuestra aplicación (ej. la carpeta 'app')
# Es mejor ser específico que usar 'COPY . .'
COPY ./app ./app

# Damos la propiedad de todos los archivos a nuestro usuario no-root
RUN chown -R appuser:appgroup /app

# Cambiamos al usuario no-root
USER appuser

# El CMD ahora usa la variable de entorno $PORT que Railway proporciona.
# Gunicorn es un servidor de producción robusto para aplicaciones Python.
CMD gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind "0.0.0.0:$PORT"
