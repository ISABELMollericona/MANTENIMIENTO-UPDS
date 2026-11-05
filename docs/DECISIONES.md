# Decisiones del proyecto

- El repositorio inicia sin archivos ni historial; se crea una estructura Django desde cero.
- En desarrollo, si `DATABASE_URL` está vacía, se usa SQLite para permitir ejecutar el sistema sin credenciales externas. En producción, configurar PostgreSQL/Neon mediante `DATABASE_URL`; la conexión exige SSL.
- La recuperación de contraseña usa la consola en desarrollo; el envío por correo queda fuera del alcance inicial.
- El despliegue no está definido. Se incluye compatibilidad con Gunicorn y WhiteNoise para un despliegue WSGI estándar.
- Se incorpora `costo_compra` opcional al equipo, en bolivianos, porque el indicador informativo de reparar o reemplazar necesita compararlo con los costos de intervención. Se conserva vacío cuando el dato no está disponible.
- Las solicitudes avanzan por registrada → asignada → en reparación → resuelta; se pueden cancelar desde estados abiertos indicando motivo y reabrir una resuelta o cancelada con el permiso dinámico separado `reabrir_solicitud`.
- El costo de cada intervención se calcula como mano de obra más la suma de cantidad × costo unitario de cada repuesto; todos los montos se registran en bolivianos y no afectan inventario físico.
- Las periodicidades preventivas se suman como meses calendario y ajustan al último día del mes cuando la fecha no existe (por ejemplo, 31 de enero → 28/29 de febrero); el vencimiento se deriva de estado pendiente y fecha programada anterior al día actual.
- El indicador reparar/reemplazar usa como umbral inicial el 50 % del costo de compra (`REPAIR_REPLACE_THRESHOLD=0.5`); es una sugerencia informativa y se puede ajustar por entorno.
- `seed_demo` crea datos ficticios con claves deterministas y no reemplaza registros existentes; los usuarios demo comparten una clave inicial configurable con `DEMO_PASSWORD` y deben cambiarla al primer acceso. No se debe ejecutar con cuentas demo en producción.
- El módulo M9 usa un enfoque conservador de modo sin conexión: el cliente guarda la operación localmente cuando la red falla, la sincroniza con cola ordenada y reintenta por prioridad de creación; el servidor valida permisos, estados y campos antes de aceptar cada operación, evitando duplicados por `uuid_cliente` y devolviendo mensajes claros en español.
