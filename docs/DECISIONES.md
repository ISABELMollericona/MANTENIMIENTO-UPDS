# Decisiones del proyecto

- El repositorio inicia sin archivos ni historial; se crea una estructura Django desde cero.
- En desarrollo, si `DATABASE_URL` está vacía, se usa SQLite para permitir ejecutar el sistema sin credenciales externas. En producción, configurar PostgreSQL/Neon mediante `DATABASE_URL`; la conexión exige SSL.
- La recuperación de contraseña usa la consola en desarrollo; el envío por correo queda fuera del alcance inicial.
- El despliegue no está definido. Se incluye compatibilidad con Gunicorn y WhiteNoise para un despliegue WSGI estándar.
