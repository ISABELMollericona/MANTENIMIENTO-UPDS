# Sistema de Gestión de Mantenimiento y Equipamiento Universitario

Aplicación web para la gestión de mantenimiento y equipamiento de la UPDS, sede Cochabamba.

## Requisitos

- Python 3.12 o superior.
- PostgreSQL (Neon en despliegue) o SQLite para desarrollo local.

## Instalación local

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_roles
python manage.py runserver
```

Configura `SECRET_KEY`, `DEBUG` y `ALLOWED_HOSTS` en `.env`. Para Neon, agrega la URL PostgreSQL en `DATABASE_URL`; el proyecto requiere SSL. Sin `DATABASE_URL`, se usa SQLite local.

## Comandos

- `python manage.py test`: ejecutar pruebas.
- `python manage.py createsuperuser`: crear la primera cuenta administradora.
- `python manage.py seed_roles`: crear roles iniciales, asignar el rol Administrador a superusuarios y poder editarlos luego desde la interfaz.
- `python manage.py seed_demo`: cargar datos ficticios (planificado para Sprint 3).

## Cuentas y roles

Los roles usan los modelos nativos `Group` y `Permission` de Django. Crea el usuario inicial con `createsuperuser`, ejecuta `seed_roles` y accede a **Roles y permisos** para administrar la matriz. La recuperación de contraseña imprime el enlace en la consola cuando `DEBUG=True`.

## Despliegue

Usa Gunicorn con `gunicorn mantenimiento.wsgi:application`, configura `DEBUG=False`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` y `DATABASE_URL`, y ejecuta `python manage.py migrate` y `python manage.py collectstatic`.
