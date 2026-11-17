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
python manage.py seed_demo
python manage.py runserver
```

Configura `SECRET_KEY`, `DEBUG` y `ALLOWED_HOSTS` en `.env`. Para Neon, agrega la URL PostgreSQL en `DATABASE_URL`; el proyecto requiere SSL. Sin `DATABASE_URL`, se usa SQLite local.

## Comandos

- `python manage.py test`: ejecutar pruebas.
- `python manage.py createsuperuser`: crear la primera cuenta administradora.
- `python manage.py seed_roles`: crear los roles acordados (Administrador, Responsable de mantenimiento, Técnico, Jefe de carrera, Estudiante). Con `--actualizar-permisos` deja cada rol con sus permisos acordados.
- `python manage.py seed_demo`: cargar datos ficticios idempotentes (3 laboratorios de computación, 12 computadoras con teclado y mouse, reportes de falla, reparaciones y cronograma preventivo).

## Cuentas y roles

Los roles usan los modelos nativos `Group` y `Permission` de Django. Crea el usuario inicial con `createsuperuser`, ejecuta `seed_roles` y accede a **Roles y permisos** para administrar la matriz. La recuperación de contraseña imprime el enlace en la consola cuando `DEBUG=True`.

`seed_demo` crea estas cuentas para pruebas locales, todas con `Demo-UPDS-2026!` por defecto y cambio obligatorio de contraseña al primer acceso:

- `admin.demo` (Administrador)
- `responsable.demo` (Responsable de mantenimiento)
- `tecnico.demo` (Técnico)
- `jefe.demo` (Jefe de carrera)
- `estudiante.demo` (Estudiante)

Puedes cambiar la contraseña compartida estableciendo `DEMO_PASSWORD` antes de ejecutar el comando. Estas cuentas y claves son solo para desarrollo; no las uses en producción.

## Despliegue

Usa Gunicorn con `gunicorn mantenimiento.wsgi:application`, configura `DEBUG=False`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` y `DATABASE_URL`, y ejecuta `python manage.py migrate` y `python manage.py collectstatic`.
