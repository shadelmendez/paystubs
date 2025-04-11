# Paystub Service

Este proyecto permite generar comprobantes de pago en formato PDF a partir de un archivo CSV, y posteriormente enviar dichos documentos por correo electrónico a sus respectivos destinatarios.

---

## Características

- Procesamiento de archivos CSV con datos de nómina
- Validación de datos con Pydantic (vía Pandantic)
- Generación de PDFs personalizados usando `fpdf2`
- Envío automático de comprobantes de pago por correo
- API construida con FastAPI
- Contenedorización con Docker
- Soporte para autenticación con usuario y contraseña
- Soporte multilenguaje para títulos (ES / EN) basado en el país

---

## Tecnologías utilizadas

- **FastAPI** - Backend web moderno, rápido y asíncrono
- **Uvicorn** - ASGI server para desarrollo y despliegue
- **bcrypt** - Hasheo y validación segura de contraseñas
- **Pandas** - Procesamiento de datos desde CSV
- **Pandantic** - Validación de DataFrames con Pydantic
- **fpdf2** - Generación de PDFs personalizables
- **smtplib** - Envío de correos mediante SMTP
- **Docker** y **Docker Compose**
- **Coverage** - Medición de cobertura de pruebas unitarias

---

## Configuración del entorno

Antes de ejecutar el proyecto, crea un archivo `.env` en la raíz con las siguientes variables:

```env
USER="usuario-autorizado"
PASSWORD="contraseña"
FROM_EMAIL="email@ejemplo.com"
PASSWORD_EMAIL="contraseña-del-email"
```

## Ejecutar el proyecto con Docker

Ejecutar el siguiente comando para construir y levantar los servicios:
`docker compose up --build`
