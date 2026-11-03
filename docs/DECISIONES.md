# Decisiones del proyecto

- El repositorio inicia sin archivos ni historial; se crea una estructura Django desde cero.
- En desarrollo, si `DATABASE_URL` está vacía, se usa SQLite para permitir ejecutar el sistema sin credenciales externas. En producción, configurar PostgreSQL/Neon mediante `DATABASE_URL`; la conexión exige SSL.
- La recuperación de contraseña usa la consola en desarrollo; el envío por correo queda fuera del alcance inicial.
- El despliegue no está definido. Se incluye compatibilidad con Gunicorn y WhiteNoise para un despliegue WSGI estándar.
- Se incorpora `costo_compra` opcional al equipo, en bolivianos, porque el indicador informativo de reparar o reemplazar necesita compararlo con los costos de intervención. Se conserva vacío cuando el dato no está disponible.
- Las solicitudes avanzan por registrada → asignada → en reparación → resuelta; se pueden cancelar desde estados abiertos indicando motivo y reabrir una resuelta o cancelada con el permiso dinámico separado `reabrir_solicitud`.
- El costo de cada intervención se calcula como mano de obra más la suma de cantidad × costo unitario de cada repuesto; todos los montos se registran en bolivianos y no afectan inventario físico.
