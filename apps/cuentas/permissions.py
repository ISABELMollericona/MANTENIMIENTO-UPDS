"""Catálogo de permisos y agrupaciones para la matriz de roles."""

PERMISOS_MODULO = [
    {
        "titulo": "Usuarios",
        "acciones": [("ver_usuarios", "Ver"), ("crear_usuarios", "Crear"), ("editar_usuarios", "Editar"), ("desactivar_usuarios", "Desactivar")],
    },
    {
        "titulo": "Roles y permisos",
        "acciones": [("ver_roles", "Ver"), ("crear_roles", "Crear"), ("editar_roles", "Editar"), ("eliminar_roles", "Eliminar")],
    },
    {
        "titulo": "Ambientes",
        "acciones": [("ver_ambientes", "Ver"), ("crear_ambientes", "Crear"), ("editar_ambientes", "Editar"), ("dar_baja_ambientes", "Dar de baja")],
    },
    {
        "titulo": "Equipos",
        "acciones": [("ver_equipos", "Ver"), ("crear_equipos", "Crear"), ("editar_equipos", "Editar"), ("dar_baja_equipos", "Dar de baja"), ("exportar_equipos", "Exportar")],
    },
    {
        "titulo": "Solicitudes",
        "acciones": [("ver_solicitudes", "Ver"), ("crear_solicitudes", "Crear"), ("editar_solicitudes", "Editar"), ("cancelar_solicitudes", "Cancelar")],
    },
    {
        "titulo": "Intervenciones",
        "acciones": [("ver_intervenciones", "Ver"), ("crear_intervenciones", "Crear"), ("editar_intervenciones", "Editar")],
    },
    {
        "titulo": "Mantenimiento preventivo",
        "acciones": [("ver_preventivos", "Ver"), ("crear_preventivos", "Crear"), ("editar_preventivos", "Editar")],
    },
    {
        "titulo": "Reportes",
        "acciones": [("ver_reportes", "Ver"), ("exportar_reportes", "Exportar")],
    },
    {"titulo": "Panel de inicio", "acciones": [("ver_dashboard", "Ver")]},
]

PERMISOS_ESPECIALES = [
    ("gestionar_usuarios", "Gestionar usuarios y asignar roles"),
    ("gestionar_roles", "Gestionar roles y permisos"),
    ("asignar_tecnico", "Asignar técnicos a solicitudes"),
    ("cambiar_estado_solicitud", "Cambiar el estado de solicitudes asignadas"),
    ("autorizar_baja_equipo", "Autorizar la baja de equipos"),
    ("ver_todas_solicitudes", "Ver todas las solicitudes, no solo las propias"),
]

TODOS_LOS_CODENAMES = [
    codename
    for modulo in PERMISOS_MODULO
    for codename, _ in modulo["acciones"]
] + [codename for codename, _ in PERMISOS_ESPECIALES]


def obtener_matriz_permisos(permisos_seleccionados=()):
    from django.contrib.auth.models import Permission

    permisos = {
        permiso.codename: permiso
        for permiso in Permission.objects.filter(
            content_type__app_label="cuentas",
            content_type__model="catalogopermiso",
            codename__in=TODOS_LOS_CODENAMES,
        )
    }
    seleccionados = {str(valor) for valor in permisos_seleccionados}
    matriz = []
    for modulo in PERMISOS_MODULO:
        acciones = []
        for codename, etiqueta in modulo["acciones"]:
            permiso = permisos.get(codename)
            if permiso:
                acciones.append({"permiso": permiso, "etiqueta": etiqueta, "seleccionado": str(permiso.pk) in seleccionados})
        matriz.append({"titulo": modulo["titulo"], "acciones": acciones})
    especiales = []
    for codename, etiqueta in PERMISOS_ESPECIALES:
        permiso = permisos.get(codename)
        if permiso:
            especiales.append({"permiso": permiso, "etiqueta": etiqueta, "seleccionado": str(permiso.pk) in seleccionados})
    return matriz, especiales
