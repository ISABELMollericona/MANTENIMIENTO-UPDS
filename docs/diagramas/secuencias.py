"""Diagramas de secuencia estilo UML dibujados con matplotlib.

Uso: python secuencias.py [carpeta_salida]
Pasos admitidos en `dibujar_secuencia`:
  ("msg", origen, destino, texto)   llamada (flecha sólida, numerada)
  ("ret", origen, destino, texto)   respuesta (flecha punteada)
  ("self", participante, texto)     llamada a sí mismo
  ("nota", participante, texto)     nota a la derecha del participante
  ("alt", condicion) / ("sino", condicion) / ("fin",)   fragmento alternativo
  ("loop", condicion) / ("fin",)                         fragmento de repetición
  ("seccion", texto)                separador con título
"""
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Ellipse, FancyBboxPatch, Rectangle  # noqa: E402

AZUL = "#064B87"
GRIS = "#4B6378"
CLARO = "#EAF2F8"
plt.rcParams["font.family"] = "Arial"


def _envolver(texto, ancho_pulgadas, tam=8.5):
    caracteres = max(14, int(ancho_pulgadas * 72 / (tam * 0.5)))
    return "\n".join(textwrap.fill(linea, caracteres) for linea in texto.split("\n"))


def dibujar_secuencia(participantes, pasos, archivo, titulo=None, dpi=130):
    n = len(participantes)
    col = min(1.75, 9.6 / n)
    margen = 0.55
    ancho = margen * 2 + col * n
    x = {pid: margen + col * (i + 0.5) for i, (pid, _, _) in enumerate(participantes)}
    y = 0.95 if titulo else 0.35
    alto_cabecera = 0.72
    y_cabecera = y
    y = y + alto_cabecera + 0.3

    # Primera pasada: posiciones verticales.
    plan, pila, numero = [], [], 0
    for paso in pasos:
        tipo = paso[0]
        if tipo in ("msg", "ret"):
            a, b, texto = paso[1], paso[2], paso[3]
            if tipo == "msg":
                numero += 1
                texto = f"{numero}. {texto}"
            envuelto = _envolver(texto, max(abs(x[b] - x[a]) - 0.15, col * 0.9))
            lineas = envuelto.count("\n") + 1
            y += 0.13 * lineas
            plan.append((tipo, a, b, envuelto, y))
            y += 0.24
        elif tipo == "self":
            numero += 1
            envuelto = _envolver(f"{numero}. {paso[2]}", col * 1.15)
            lineas = envuelto.count("\n") + 1
            plan.append((tipo, paso[1], envuelto, y, lineas))
            y += max(0.42, 0.14 * lineas + 0.2)
        elif tipo == "nota":
            envuelto = _envolver(paso[2], col * 1.25, 8)
            lineas = envuelto.count("\n") + 1
            alto = 0.13 * lineas + 0.12
            plan.append((tipo, paso[1], envuelto, y, alto))
            y += alto + 0.14
        elif tipo in ("alt", "loop"):
            pila.append(len(plan))
            plan.append([tipo, paso[1], y, None, []])
            y += 0.34
        elif tipo == "sino":
            plan[pila[-1]][4].append((paso[1], y))
            y += 0.34
        elif tipo == "fin":
            inicio = pila.pop()
            plan[inicio][3] = y
            y += 0.18
        elif tipo == "seccion":
            plan.append((tipo, paso[1], y))
            y += 0.42
    alto_total = y + 0.25

    fig = plt.figure(figsize=(ancho, alto_total), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, ancho)
    ax.set_ylim(alto_total, 0)
    ax.axis("off")
    if titulo:
        ax.text(ancho / 2, 0.45, titulo, ha="center", va="center", fontsize=13, fontweight="bold", color=AZUL)

    # Participantes y líneas de vida.
    for pid, nombre, tipo in participantes:
        cx = x[pid]
        ax.plot([cx, cx], [y_cabecera + alto_cabecera, alto_total - 0.1], ls=(0, (4, 3)), color="#9AB5CC", lw=1, zorder=0)
        if tipo == "actor":
            cy = y_cabecera + 0.12
            ax.add_patch(plt.Circle((cx, cy), 0.07, fill=False, ec=AZUL, lw=1.4))
            ax.plot([cx, cx], [cy + 0.07, cy + 0.3], color=AZUL, lw=1.4)
            ax.plot([cx - 0.13, cx + 0.13], [cy + 0.15, cy + 0.15], color=AZUL, lw=1.4)
            ax.plot([cx, cx - 0.11], [cy + 0.3, cy + 0.45], color=AZUL, lw=1.4)
            ax.plot([cx, cx + 0.11], [cy + 0.3, cy + 0.45], color=AZUL, lw=1.4)
            ax.text(cx, y_cabecera + alto_cabecera + 0.04, nombre, ha="center", va="top", fontsize=8.5, color=AZUL, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
        elif tipo == "bd":
            w, h = col * 0.78, 0.5
            top = y_cabecera + 0.12
            ax.add_patch(Rectangle((cx - w / 2, top), w, h, fc="white", ec=AZUL, lw=1.2))
            ax.add_patch(Ellipse((cx, top), w, 0.16, fc="white", ec=AZUL, lw=1.2))
            ax.add_patch(Ellipse((cx, top + h), w, 0.16, fc="white", ec=AZUL, lw=1.2, zorder=0))
            ax.text(cx, top + h / 2 + 0.03, nombre, ha="center", va="center", fontsize=8.5, color="black", fontweight="bold")
        else:
            w, h = col * 0.86, 0.56
            ax.add_patch(FancyBboxPatch((cx - w / 2, y_cabecera + 0.08), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=CLARO, ec=AZUL, lw=1.2))
            ax.text(cx, y_cabecera + 0.08 + h / 2, nombre, ha="center", va="center", fontsize=8.5, fontweight="bold", color="black")

    izquierda = margen * 0.35
    derecha = ancho - margen * 0.35
    for elemento in plan:
        tipo = elemento[0]
        if tipo in ("msg", "ret"):
            _, a, b, texto, yy = elemento
            estilo = dict(arrowstyle="-|>", color=GRIS, lw=1.2, mutation_scale=11) if tipo == "msg" else dict(arrowstyle="->", color=GRIS, lw=1.0, ls=(0, (4, 3)), mutation_scale=11)
            ax.annotate("", xy=(x[b], yy), xytext=(x[a], yy), arrowprops=estilo)
            ax.text((x[a] + x[b]) / 2, yy - 0.04, texto, ha="center", va="bottom", fontsize=8.5, color="black" if tipo == "msg" else "#33475B",
                    style="normal" if tipo == "msg" else "italic", linespacing=1.15)
        elif tipo == "self":
            _, p, texto, yy, lineas = elemento
            cx = x[p]
            s = -1 if cx + col * 1.3 > ancho else 1  # sin espacio a la derecha: se dibuja hacia la izquierda
            ax.plot([cx, cx + 0.32 * s, cx + 0.32 * s], [yy, yy, yy + 0.2], color=GRIS, lw=1.2)
            ax.annotate("", xy=(cx + 0.02 * s, yy + 0.2), xytext=(cx + 0.32 * s, yy + 0.2), arrowprops=dict(arrowstyle="-|>", color=GRIS, lw=1.2, mutation_scale=10))
            ax.text(cx + 0.4 * s, yy - 0.04, texto, ha="left" if s > 0 else "right", va="top", fontsize=8.5, linespacing=1.15)
        elif tipo == "nota":
            _, p, texto, yy, alto = elemento
            cx = x[p] + 0.12
            w = col * 1.3
            ax.add_patch(Rectangle((cx, yy - 0.05), w, alto, fc="#FFF8E1", ec="#E0A800", lw=1))
            ax.text(cx + 0.07, yy + 0.02, texto, ha="left", va="top", fontsize=8, linespacing=1.15)
        elif tipo == "seccion":
            _, texto, yy = elemento
            ax.add_patch(Rectangle((izquierda, yy), derecha - izquierda, 0.28, fc="#DCE9F5", ec="none", zorder=0.5))
            ax.text(ancho / 2, yy + 0.14, texto, ha="center", va="center", fontsize=9.5, fontweight="bold", color=AZUL)
        elif tipo in ("alt", "loop"):
            _, condicion, y0, y1, separadores = elemento
            ax.add_patch(Rectangle((izquierda, y0), derecha - izquierda, y1 - y0, fill=False, ec=AZUL, lw=1.1, zorder=0.6))
            ax.add_patch(Rectangle((izquierda, y0), 0.5, 0.22, fc=AZUL, ec=AZUL, zorder=0.7))
            ax.text(izquierda + 0.25, y0 + 0.11, tipo, ha="center", va="center", fontsize=8, color="white", fontweight="bold")
            ax.text(izquierda + 0.58, y0 + 0.11, f"[{condicion}]", ha="left", va="center", fontsize=8.5, color=AZUL, fontweight="bold")
            for texto, ys in separadores:
                ax.plot([izquierda, derecha], [ys, ys], ls=(0, (5, 3)), color=AZUL, lw=1)
                ax.text(izquierda + 0.1, ys + 0.12, f"[{texto}]", ha="left", va="center", fontsize=8.5, color=AZUL, fontweight="bold")

    fig.savefig(archivo, dpi=dpi, facecolor="white")
    plt.close(fig)


DIAGRAMAS = {
    "07_secuencia_reportar_falla": (
        "Secuencia · registrar un reporte de falla",
        [("jefe", "Jefe de\ncarrera", "actor"), ("nav", "Navegador", "c"), ("vista", "CrearSolicitudView", "c"),
         ("form", "SolicitudForm", "c"), ("modelo", "Solicitud\n(modelo)", "c"), ("bd", "Base de\ndatos", "bd")],
        [
            ("msg", "jefe", "nav", "Abre «Reportar una falla»"),
            ("msg", "nav", "vista", "GET /solicitudes/nueva/"),
            ("self", "vista", "Sesión iniciada y permiso crear_solicitudes"),
            ("msg", "vista", "form", "Crea el formulario"),
            ("msg", "form", "bd", "Equipos que no están de baja (periféricos con su computadora)"),
            ("ret", "bd", "form", "lista de equipos"),
            ("ret", "vista", "nav", "200 · formulario"),
            ("msg", "jefe", "nav", "Completa docente, equipo, problema y prioridad"),
            ("msg", "nav", "vista", "POST /solicitudes/nueva/ + token CSRF"),
            ("msg", "vista", "form", "is_valid()"),
            ("alt", "datos incompletos o inválidos"),
            ("ret", "form", "vista", "errores por campo"),
            ("ret", "vista", "nav", "200 · formulario con mensajes"),
            ("sino", "datos válidos"),
            ("msg", "vista", "modelo", "Guarda: registrado por = usuario, estado = Registrada"),
            ("msg", "modelo", "bd", "INSERT reporte de falla"),
            ("ret", "bd", "modelo", "id del reporte"),
            ("ret", "vista", "nav", "302 · detalle «El reporte de falla se registró correctamente»"),
            ("fin",),
        ],
    ),
    "08_secuencia_asignar_tecnico": (
        "Secuencia · asignar un técnico",
        [("resp", "Responsable", "actor"), ("nav", "Navegador", "c"), ("vista", "AsignarTecnicoView", "c"),
         ("serv", "asignar_tecnico()\n(servicio)", "c"), ("modelo", "Solicitud ·\nHistorial · Auditoría", "c"), ("bd", "Base de\ndatos", "bd")],
        [
            ("msg", "resp", "nav", "Abre un reporte «Registrada»"),
            ("msg", "nav", "vista", "GET /solicitudes/<id>/ (permiso ver_todas_solicitudes)"),
            ("ret", "vista", "nav", "200 · detalle con técnicos activos (sin superusuarios)"),
            ("msg", "resp", "nav", "Elige el técnico y pulsa «Asignar»"),
            ("msg", "nav", "vista", "POST /solicitudes/<id>/asignar-tecnico/"),
            ("self", "vista", "Permiso asignar_tecnico; formulario válido"),
            ("msg", "vista", "serv", "asignar_tecnico(reporte, técnico, usuario)"),
            ("msg", "serv", "bd", "SELECT … FOR UPDATE (bloquea el reporte)"),
            ("alt", "estado no es Registrada/Asignada o el técnico no tiene permiso"),
            ("ret", "serv", "vista", "ValidationError"),
            ("ret", "vista", "nav", "302 · detalle con mensaje de error"),
            ("sino", "válido"),
            ("msg", "serv", "modelo", "técnico asignado; estado = Asignada"),
            ("msg", "serv", "modelo", "HistorialSolicitud Registrada → Asignada"),
            ("msg", "serv", "modelo", "AuditoriaSeguridad «tecnico_asignado»"),
            ("msg", "modelo", "bd", "UPDATE / INSERT"),
            ("ret", "vista", "nav", "302 · «El técnico quedó asignado»"),
            ("fin",),
            ("nota", "resp", "El técnico ve el reporte en «Mis tareas»."),
        ],
    ),
    "09_secuencia_reparacion": (
        "Secuencia · reparación (salida y devolución)",
        [("tec", "Técnico", "actor"), ("nav", "Navegador", "c"), ("vista", "Crear / Editar\nIntervencionView", "c"),
         ("form", "IntervencionForm", "c"), ("serv", "cambiar_estado()\n(servicio)", "c"), ("bd", "Base de\ndatos", "bd")],
        [
            ("seccion", "Salida del equipo"),
            ("msg", "tec", "nav", "«Registrar salida» en Mis tareas"),
            ("msg", "nav", "vista", "GET /intervenciones/solicitud/<id>/nueva/"),
            ("self", "vista", "¿Es el técnico asignado y el reporte está Asignado? (si no: 403/404)"),
            ("msg", "nav", "vista", "POST fecha de salida + diagnóstico"),
            ("msg", "vista", "form", "clean(): salida ≥ fecha del reporte, no futura"),
            ("msg", "vista", "bd", "INSERT reparación (laboratorio de origen = laboratorio del equipo)"),
            ("msg", "vista", "serv", "cambiar_estado(En reparación)"),
            ("msg", "serv", "bd", "Reporte Asignada → En reparación + historial; equipo → En mantenimiento/reparación"),
            ("ret", "vista", "nav", "302 · «Se registró la salida del equipo»"),
            ("seccion", "Trabajo y devolución"),
            ("msg", "nav", "vista", "POST trabajo, repuestos, fecha de devolución, resultado"),
            ("msg", "vista", "form", "clean(): devolución ≥ salida; resultado y trabajo obligatorios"),
            ("msg", "vista", "bd", "UPDATE reparación (días fuera = devolución − salida)"),
            ("msg", "vista", "serv", "cambiar_estado(Resuelta, no_reparable)"),
            ("alt", "Reparado / Reparado parcialmente"),
            ("msg", "serv", "bd", "Reporte → Resuelta; equipo → Operativo (historial)"),
            ("sino", "No reparable"),
            ("msg", "serv", "bd", "Reporte → Resuelta; el equipo sigue en reparación (espera la baja)"),
            ("fin",),
            ("ret", "vista", "nav", "302 · «Se registró la devolución y el reporte quedó resuelto»"),
        ],
    ),
    "10_secuencia_baja": (
        "Secuencia · registrar la baja de un equipo",
        [("resp", "Responsable", "actor"), ("nav", "Navegador", "c"), ("vista", "BajaEquipoView", "c"),
         ("form", "BajaEquipoForm", "c"), ("modelo", "Equipo\n(modelo)", "c"), ("bd", "Base de\ndatos", "bd")],
        [
            ("msg", "resp", "nav", "«Registrar baja» en la ficha del equipo"),
            ("msg", "nav", "vista", "GET /equipos/<id>/dar-de-baja/"),
            ("self", "vista", "Permisos dar_baja_equipos y autorizar_baja_equipo"),
            ("ret", "vista", "nav", "200 · códigos, serie, periféricos; fecha de retiro = hoy"),
            ("msg", "resp", "nav", "Estado de baja, fecha, motivo, ¿informado? + fecha"),
            ("msg", "nav", "vista", "POST + incluir periféricos"),
            ("msg", "vista", "form", "is_valid(): motivo obligatorio, sin fechas futuras"),
            ("msg", "form", "modelo", "clean(): si está informado exige fecha; informe ≥ retiro"),
            ("alt", "datos inválidos"),
            ("ret", "vista", "nav", "200 · formulario con errores"),
            ("sino", "válido"),
            ("msg", "vista", "modelo", "save() dentro de una transacción"),
            ("msg", "modelo", "bd", "UPDATE equipo + HistorialEquipo (estado, Vicerrectoría)"),
            ("loop", "cada periférico activo"),
            ("msg", "vista", "modelo", "Copia estado, fechas e informe; save()"),
            ("fin",),
            ("ret", "vista", "nav", "302 · ficha «La baja oficial la realiza Vicerrectoría»"),
            ("fin",),
            ("nota", "resp", "Después puede marcar el informe a Vicerrectoría desde la lista de Bajas."),
        ],
    ),
    "11_secuencia_login": (
        "Secuencia · inicio de sesión y control de permisos",
        [("usr", "Usuario", "actor"), ("nav", "Navegador", "c"), ("mw", "Middleware\n(sesión, CSRF, clave)", "c"),
         ("login", "LoginView", "c"), ("auth", "Autenticación\n(Usuario)", "c"), ("vista", "Vista protegida\n(p. ej. Equipos)", "c")],
        [
            ("msg", "usr", "nav", "Entra a /cuentas/ingresar/"),
            ("msg", "nav", "login", "GET formulario (cookie CSRF)"),
            ("msg", "usr", "nav", "Usuario y contraseña"),
            ("msg", "nav", "login", "POST credenciales + token CSRF"),
            ("msg", "login", "auth", "authenticate() (contraseña cifrada)"),
            ("alt", "credenciales incorrectas"),
            ("ret", "login", "nav", "200 · mensaje de credenciales incorrectas"),
            ("sino", "correctas"),
            ("ret", "login", "nav", "302 · sesión nueva → «next» o Inicio"),
            ("fin",),
            ("msg", "nav", "mw", "GET /equipos/"),
            ("alt", "force_password_change = sí"),
            ("ret", "mw", "nav", "302 · /cuentas/contrasena/"),
            ("msg", "nav", "auth", "POST nueva contraseña (validadores) → force_password_change = no"),
            ("sino", "no debe cambiarla"),
            ("msg", "mw", "vista", "dispatch()"),
            ("self", "vista", "LoginRequired y has_perm('cuentas.ver_equipos')"),
            ("ret", "vista", "nav", "200 página · 403 «Acceso restringido» sin permiso"),
            ("fin",),
        ],
    ),
}


if __name__ == "__main__":
    salida = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent
    for nombre, (titulo, participantes, pasos) in DIAGRAMAS.items():
        dibujar_secuencia(participantes, pasos, salida / f"{nombre}.png", titulo)
        print("ok", nombre)
