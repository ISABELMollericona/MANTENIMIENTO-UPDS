# Decisiones del proyecto

- El repositorio inicia sin archivos ni historial; se crea una estructura Django desde cero.
- En desarrollo, si `DATABASE_URL` está vacía, se usa SQLite para permitir ejecutar el sistema sin credenciales externas. En producción, configurar PostgreSQL/Neon mediante `DATABASE_URL`; la conexión exige SSL.
- La recuperación de contraseña usa la consola en desarrollo; el envío por correo queda fuera del alcance inicial.
- El despliegue no está definido. Se incluye compatibilidad con Gunicorn y WhiteNoise para un despliegue WSGI estándar.
- Las solicitudes avanzan por registrada → asignada → en reparación → resuelta; se pueden cancelar desde estados abiertos indicando motivo y reabrir una resuelta o cancelada con el permiso dinámico separado `reabrir_solicitud`.
- `seed_demo` crea datos ficticios con claves deterministas y no reemplaza registros existentes; los usuarios demo comparten una clave inicial configurable con `DEMO_PASSWORD` y deben cambiarla al primer acceso. No se debe ejecutar con cuentas demo en producción.
- El módulo M9 usa un enfoque conservador de modo sin conexión: el cliente guarda la operación localmente cuando la red falla, la sincroniza con cola ordenada y reintenta por prioridad de creación; el servidor valida permisos, estados y campos antes de aceptar cada operación, evitando duplicados por `uuid_cliente` y devolviendo mensajes claros en español.
- Revisión de requisitos (12/11/2026): se eliminan los costos (compra, mano de obra, repuestos con precio) y el reporte «reparar o reemplazar» porque el cliente los dejó fuera del alcance. Los repuestos se registran como texto.
- Los estados de equipo están en la tabla `EstadoEquipo` y se editan desde Equipos › Estados. Cada estado tiene un comportamiento fijo (operativo, en reparación, baja) que usa el sistema; el nombre es libre hasta que el cliente apruebe los definitivos. El antiguo «Fuera de servicio» se migró a «En mantenimiento/reparación».
- El mantenimiento preventivo es un cronograma anual por laboratorio con 2 o 3 fechas, cada una pendiente o realizada. Reemplaza al modelo anterior de planes por categoría; las programaciones antiguas no se trasladan.
- Un reparación «no reparable» deja el equipo en «En mantenimiento/reparación» hasta que el responsable registre la baja; la baja oficial la hace Vicerrectoría fuera del sistema.
- El modelo `Ambiente` se conserva, pero el sistema solo usa y crea laboratorios (fuera de alcance: aulas, oficinas, mobiliario).
