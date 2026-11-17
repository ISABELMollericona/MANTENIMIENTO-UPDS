# Verificación de requisitos del cliente

Revisión del 12/11/2026. Estado **antes** de las correcciones y qué se hizo.

## 1. Tabla de verificación (estado inicial)

| # | Requisito | Estado inicial | Dónde está | Qué faltaba |
|---|---|---|---|---|
| 1.1 | Administrador crea usuarios y asigna roles | ✅ Cumple | `apps/cuentas/views.py`, `forms.py` | — |
| 1.2 | Rol Responsable del área de mantenimiento | ⚠️ Parcial | `seed_roles.py` («Responsable de equipamiento») | Nombre distinto; no podía marcar bajas informadas a Vicerrectoría |
| 1.3 | Técnico ve SOLO lo suyo y registra trabajo y repuestos | ⚠️ Parcial | `solicitudes/views.py`, `services.py` | **Agujero de seguridad**: podía cambiar el estado de cualquier reporte enviando el formulario a la URL; no veía sus preventivos |
| 1.4 | Jefe de carrera registra fallas en nombre de docentes | ❌ Falta | — | Existía «Solicitante», sin campo del docente |
| 1.5 | Estudiante: solo consulta estado de equipos | ❌ Falta | — | No existía el rol |
| 1.6 | Docentes sin cuenta | ⚠️ Parcial | `seed_demo.py` | Los datos demo creaban un usuario «docente» |
| 1.7 | Permisos verificados en vistas y URLs | ⚠️ Parcial | mixins `Acceso*` | Ver 1.3; visitantes sin sesión recibían 403 en lugar del login |
| 2.1 | Campos del equipo | ✅ Cumple | `equipos/models.py` | Sobraba `costo_compra` (fuera de alcance) |
| 2.2 | Periférico (teclado, mouse) asociado a una computadora | ❌ Falta | — | No había relación entre equipos |
| 2.3 | Estados exactos: Operativo · En mantenimiento/reparación · Obsoleto/Dado de baja | ❌ Falta | `Equipo.Estado` | Eran 4 estados distintos («Fuera de servicio» sobraba) |
| 2.4 | Estados en tabla editable | ❌ Falta | — | Fijos en el código (`TextChoices`) |
| 2.5 | Quién cambió el estado y cuándo | ✅ Cumple | `HistorialEquipo` | — |
| 3.1 | Reporte registrado por el jefe de carrera | ⚠️ Parcial | `solicitudes` | Rol inexistente (ver 1.4) |
| 3.2 | Campo «docente solicitante» obligatorio | ❌ Falta | — | — |
| 3.3 | Problema del equipo obligatorio | ✅ Cumple | `Solicitud.descripcion` | — |
| 3.4 | Fallas de periféricos | ❌ Falta | — | Depende de 2.2 |
| 3.5 | Estados y seguimiento | ✅ Cumple | `Solicitud.Estado`, `HistorialSolicitud` | — |
| 3.6 | Responsable ve pendientes y asigna técnico | ✅ Cumple | `AsignarTecnicoView` | — |
| 4.1 | Reparación: fecha de salida y de devolución | ❌ Falta | `Intervencion` | Tenía fecha/hora de inicio y fin |
| 4.2 | Laboratorio de origen | ❌ Falta | — | — |
| 4.3 | Repuestos usados (texto) | ⚠️ Parcial | `RepuestoUsado` | Era una tabla con cantidad y **precio** |
| 4.4 | Vinculada al reporte de falla | ✅ Cumple | `Intervencion.solicitud` | — |
| 4.5 | NO registrar costos | ❌ Falta | `costo_mano_obra`, `costo_unitario`, `costo_compra` | Había costos en 3 modelos, ficha y reportes |
| 4.6 | Completar trabajo después de la salida | ❌ Falta | — | Solo se podía crear, no editar |
| 5.1 | Cronograma ANUAL por laboratorio, 2 o 3 al año | ❌ Falta | `PlanPreventivo`, `MantenimientoProgramado` | Planes por categoría y periodicidad por equipo |
| 5.2 | Marcar realizado o pendiente | ⚠️ Parcial | `CompletarProgramacionView` | Solo «realizado»; no se podía volver a pendiente |
| 6.1 | Baja con todos los códigos del equipo | ⚠️ Parcial | `BajaEquipoView` | Solo cambiaba el estado; sin motivo, fecha ni periféricos |
| 6.2 | «Informado a Vicerrectoría» sí/no + fecha | ❌ Falta | — | — |
| 6.3 | La baja oficial no se hace en el sistema | ⚠️ Parcial | — | No se aclaraba en pantalla |
| 7.1 | Equipos por laboratorio | ✅ Cumple | `reportes/services.py` | Solo contaba el total |
| 7.2 | Equipos en reparación y obsoletos | ⚠️ Parcial | «equipos_fuera_servicio» | Solo mostraba «fuera de servicio» |
| 7.3 | Fallas pendientes y atendidos | ✅ Cumple | «solicitudes» | Sin docente ni filtro pendiente/atendido |
| 7.4 | Historial de cada equipo | ⚠️ Parcial | «historial_equipo» | Listaba intervenciones con costo, no el historial de un equipo |
| 7.5 | Tiempo que estuvo fuera cada equipo | ❌ Falta | — | — |
| 7.6 | Equipos con más fallas | ✅ Cumple | «equipos_mas_fallas» | — |
| 7.7 | Mantenimientos por periodo | ⚠️ Parcial | «costos_periodo» | Era un reporte de costos |
| 8 | Fuera de alcance | ⚠️ Había cosas fuera de alcance | varios | Costos, reporte «reparar o reemplazar», datos demo con proyectores, mobiliario, aulas y oficinas |
| 9.1 | Credenciales en variables de entorno, `.env` en `.gitignore` | ✅ Cumple | `settings.py`, `.gitignore` | `.env` nunca se subió a git |
| 9.2 | `DEBUG=False` en producción, `ALLOWED_HOSTS` para Render | ⚠️ Parcial | `settings.py` | `DEBUG` era `True` por defecto si no se configuraba |
| 9.3 | Validaciones (obligatorios, devolución ≥ salida) | ⚠️ Parcial | formularios | Faltaba devolución ≥ salida, salida ≥ fecha del reporte, fechas futuras |
| 9.4 | Migraciones al día | ✅ Cumple | — | — |

**Después de las correcciones todos los requisitos quedan en ✅.** Pruebas: 88 automáticas (incluida una matriz de acceso por rol), recorrido de 417 páginas y reportes con `DEBUG=False` sin errores, y pruebas en el navegador con cada rol.

## 2. Correcciones

### Roles (`apps/cuentas/management/commands/seed_roles.py`)
- **Antes:** Administrador, Responsable de equipamiento, Técnico, Solicitante, Autoridad.
- **Después:** Administrador, **Responsable de mantenimiento**, Técnico, **Jefe de carrera**, **Estudiante**, cada uno con solo los permisos acordados. Los roles antiguos se **renombran** sin perder usuarios. `--actualizar-permisos` aplica los permisos acordados a bases existentes.
- **Por qué:** son los 5 roles que pidió el cliente; los docentes no tienen cuenta.

### Agujero de seguridad del técnico (`apps/solicitudes/services.py`)
```python
# Antes: solo verificaba el permiso
if not usuario.has_perm(permiso_requerido) and not cancelacion_propia:
    raise PermissionDenied(...)
# Después: además, quien no gestiona todos los reportes solo cambia los que tiene asignados
gestiona_todos = usuario.is_superuser or usuario.has_perm("cuentas.ver_todas_solicitudes")
if not gestiona_todos and not cancelacion_propia and actual.tecnico_asignado_id != usuario.pk:
    raise PermissionDenied("Solo puedes cambiar el estado de los reportes que tienes asignados.")
```
- **Por qué:** un técnico podía cambiar cualquier reporte enviando el formulario a la URL.

### Estados editables (`apps/equipos/models.py`, migraciones 0002–0004)
```python
# Antes
class Estado(models.TextChoices):
    OPERATIVO, EN_MANTENIMIENTO, FUERA_DE_SERVICIO, DADO_DE_BAJA
estado = models.CharField(choices=Estado.choices)
# Después
class EstadoEquipo(models.Model):   # tabla editable desde Equipos › Estados
    nombre, tipo (operativo | reparacion | baja), orden, activo
estado = models.ForeignKey(EstadoEquipo, ...)
```
- Estados iniciales: **Operativo · En mantenimiento/reparación · Obsoleto/Dado de baja**. El nombre se puede cambiar; el «tipo» le dice al sistema cómo tratarlo. La migración convierte los datos existentes («Fuera de servicio» → «En mantenimiento/reparación»).

### Periféricos (`Equipo.equipo_principal`, `CategoriaEquipo.es_periferico`)
- **Antes:** no existía. **Después:** un teclado o mouse se asocia a una computadora; se valida que solo los periféricos tengan computadora y que esta no sea otro periférico. En las listas aparece «(periférico de LAB1-PC01)».

### Reporte de falla (`apps/solicitudes/models.py`, `forms.py`)
- **Después:** campo obligatorio **«Docente solicitante»**, «Problema que presenta el equipo» y «Registrado por» (el jefe de carrera). Se pueden reportar periféricos.

### Reparación (`apps/intervenciones/models.py`, migraciones 0003–0006)
```python
# Antes
fecha_inicio, fecha_fin (fecha y hora), costo_mano_obra, RepuestoUsado(cantidad, costo_unitario)
# Después
laboratorio_origen, fecha_salida, fecha_devolucion, repuestos_usados (texto), resultado
dias_fuera = fecha_devolucion − fecha_salida
```
- Flujo: el técnico registra la **salida** y después el **trabajo y la devolución**. Validaciones: devolución ≥ salida, salida ≥ fecha del reporte, sin fechas futuras, resultado y trabajo obligatorios al devolver. Los repuestos anteriores se pasaron a texto, sin precios.

### Preventivo (`apps/preventivo/`)
- **Antes:** planes por categoría con periodicidad en meses por equipo.
- **Después:** `MantenimientoPreventivo(laboratorio, año, número 1–3, fecha, técnico, estado)`. Pantalla «Cronograma» por año, «Cargar cronograma» (2 fechas obligatorias y 1 opcional, del mismo año y en orden), «Marcar realizado» y «Volver a pendiente». El técnico solo ve y marca los suyos (también en «Mis tareas»).

### Bajas (`apps/equipos/views.py`: `BajaEquipoView`, `ListaBajasView`, `InformeVicerrectoriaView`)
- **Después:** fecha de retiro, motivo, **«Informado a Vicerrectoría» sí/no + fecha**, opción de retirar también sus periféricos, y una pantalla «Bajas» con todos los códigos (inventario, serie, periféricos) donde se marca el informe más tarde. Se aclara que la baja oficial la hace Vicerrectoría.

### Reportes (`apps/reportes/services.py`)
- **Antes:** 7 reportes, 3 con costos y uno «reparar o reemplazar».
- **Después:** los 7 del cliente: equipos por laboratorio (por estado), en reparación y obsoletos, fallas pendientes y atendidos (con docente), historial de un equipo, **tiempo fuera**, equipos con más fallas y mantenimientos por periodo (preventivos y reparaciones). Exportan a Excel y PDF.

### Fuera de alcance quitado
- Costos en equipos, reparaciones y reportes; reporte «reparar o reemplazar»; `REPAIR_REPLACE_THRESHOLD`.
- Laboratorios: el sistema solo usa y crea laboratorios (el modelo `Ambiente` se conserva).
- Datos demo: solo 3 laboratorios de computación con computadoras, teclados y mouse.

### Calidad
- `DEBUG` es `False` por defecto en Render aunque no se configure.
- Visitantes sin sesión van al login (antes 403); usuarios sin permiso ven una página «Acceso restringido».
- Inicio: el panel con indicadores solo lo ven Administrador y Responsable; los demás ven atajos a lo que pueden hacer.

## 3. Comandos

```bash
python manage.py migrate
python manage.py seed_roles --actualizar-permisos
python manage.py test
```

Solo para una base de pruebas (no en producción):

```bash
python manage.py seed_demo
```

En Render, el comando de build debe incluir `python manage.py migrate` y `python manage.py seed_roles --actualizar-permisos`.

## 4. Pruebas manuales por rol

Usuarios demo: `admin.demo`, `responsable.demo`, `tecnico.demo`, `jefe.demo`, `estudiante.demo` (contraseña de `DEMO_PASSWORD`).

1. **Administrador:** entrar a Usuarios › Nuevo usuario, crear uno y asignarle el rol Técnico. Ver Roles y permisos.
2. **Jefe de carrera:** solo ve «Reportar una falla» y «Reportes de falla». Registrar una falla de un mouse indicando el docente. Probar que sin docente no deja guardar. Abrir `/equipos/` o `/reportes/` escribiendo la URL: debe salir «Acceso restringido».
3. **Responsable:** ver el reporte nuevo en «Reportes de falla» y asignarlo al técnico. Registrar un equipo con su teclado («Agregar periférico»). Cargar el cronograma de un laboratorio (2 o 3 fechas). Registrar una baja marcando «Informado a Vicerrectoría» y verla en «Bajas». Cambiar el nombre de un estado en Equipos › Estados. Generar los 7 reportes y exportar uno a Excel y PDF. Abrir `/cuentas/usuarios/`: debe salir «Acceso restringido».
4. **Técnico:** en «Mis tareas» ve solo lo asignado. Registrar la salida; probar una devolución anterior a la salida (debe dar error); registrar el trabajo, los repuestos y la devolución: el reporte queda «Resuelto» y el equipo «Operativo». Marcar realizado un preventivo propio. Escribir la URL de un reporte de otro técnico: «no encontrado».
5. **Estudiante:** el menú solo tiene «Equipos»; ve la lista y la ficha sin botones de editar. Cualquier otra URL da «Acceso restringido».

## 5. Dudas para el cliente

1. **Nombres de los estados:** se dejaron «Operativo», «En mantenimiento/reparación» y «Obsoleto/Dado de baja», editables. ¿Son los definitivos?
2. **Rol «Autoridad»:** existía antes y el cliente no lo pidió. No se borró (puede tener usuarios). ¿Se elimina?
3. **Prioridad del reporte (alta/media/baja):** el cliente no la pidió, pero ayuda a ordenar el trabajo. ¿Se mantiene?
4. **Equipo «no reparable»:** queda en «En mantenimiento/reparación» hasta que el responsable registre la baja. ¿O debe pasar directo a «Obsoleto/Dado de baja»?
5. **¿El responsable puede registrar reportes de falla?** Hoy solo el jefe de carrera (y el administrador).
6. **Programaciones preventivas antiguas:** no se trasladan al nuevo cronograma porque tenían otra estructura. En producción no había datos; confirmar que no hace falta recuperarlas.
7. **Campo «Responsable» del equipo:** no estaba en la lista del cliente; quedó opcional. ¿Se quita?
