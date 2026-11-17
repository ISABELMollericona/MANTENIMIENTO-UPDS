from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from apps.ubicaciones.models import Ambiente

from .forms import CronogramaForm, MarcarRealizadoForm
from .models import MantenimientoPreventivo


class AccesoPreventivo(LoginRequiredMixin, PermissionRequiredMixin):
    @property
    def raise_exception(self):
        # Sin sesión: redirige al login (y vuelve aquí). Con sesión y sin permiso: 403.
        return self.request.user.is_authenticated


def gestiona_cronograma(usuario):
    """Quien carga el cronograma ve todos los mantenimientos; un técnico, solo los suyos."""
    return usuario.is_superuser or usuario.has_perm("cuentas.crear_preventivos")


def _anio(valor):
    try:
        anio = int(valor)
    except (TypeError, ValueError):
        return timezone.localdate().year
    return anio if 2020 <= anio <= 2100 else timezone.localdate().year


class CronogramaView(AccesoPreventivo, TemplateView):
    template_name = "preventivo/cronograma.html"
    permission_required = "cuentas.ver_preventivos"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user
        anio = _anio(self.request.GET.get("anio"))
        mantenimientos = MantenimientoPreventivo.objects.filter(anio=anio).select_related("laboratorio", "tecnico")
        if not gestiona_cronograma(usuario):
            mantenimientos = mantenimientos.filter(tecnico=usuario)
        estado = self.request.GET.get("estado", "")
        if estado in MantenimientoPreventivo.Estado.values:
            mantenimientos = mantenimientos.filter(estado=estado)
        filas = {}
        for mantenimiento in mantenimientos:
            fila = filas.setdefault(mantenimiento.laboratorio_id, {"laboratorio": mantenimiento.laboratorio, "mantenimientos": {}})
            fila["mantenimientos"][mantenimiento.numero] = mantenimiento
        filas_ordenadas = sorted(filas.values(), key=lambda fila: (fila["laboratorio"].bloque, fila["laboratorio"].nombre))
        for fila in filas_ordenadas:
            fila["celdas"] = [fila["mantenimientos"].get(numero) for numero in (1, 2, 3)]
        sin_cronograma = []
        if gestiona_cronograma(usuario) and not estado:
            sin_cronograma = Ambiente.laboratorios().exclude(pk__in=filas.keys())
        pendientes = mantenimientos.filter(estado=MantenimientoPreventivo.Estado.PENDIENTE)
        context.update({
            "anio": anio,
            "anios": range(timezone.localdate().year - 2, timezone.localdate().year + 3),
            "filas": filas_ordenadas,
            "sin_cronograma": sin_cronograma,
            "estados": MantenimientoPreventivo.Estado.choices,
            "estado": estado,
            "gestiona": gestiona_cronograma(usuario),
            "total_realizados": mantenimientos.filter(estado=MantenimientoPreventivo.Estado.REALIZADO).count(),
            "total_pendientes": pendientes.count(),
            "total_vencidos": pendientes.filter(fecha_programada__lt=timezone.localdate()).count(),
        })
        return context


class CargarCronogramaView(AccesoPreventivo, View):
    """Crea o actualiza el cronograma anual (2 o 3 fechas) de un laboratorio."""

    permission_required = "cuentas.crear_preventivos"

    def get(self, request):
        inicial = {}
        laboratorio = request.GET.get("laboratorio", "")
        anio = _anio(request.GET.get("anio"))
        if laboratorio.isdigit():
            inicial.update({"laboratorio": laboratorio, "anio": anio})
            existentes = MantenimientoPreventivo.objects.filter(laboratorio_id=laboratorio, anio=anio)
            for mantenimiento in existentes:
                inicial[f"fecha_{mantenimiento.numero}"] = mantenimiento.fecha_programada
                if mantenimiento.tecnico_id:
                    inicial["tecnico"] = mantenimiento.tecnico_id
        return render(request, "preventivo/cronograma_formulario.html", {"form": CronogramaForm(initial=inicial)})

    def post(self, request):
        form = CronogramaForm(request.POST)
        if not form.is_valid():
            return render(request, "preventivo/cronograma_formulario.html", {"form": form})
        datos = form.cleaned_data
        laboratorio, anio, tecnico = datos["laboratorio"], datos["anio"], datos.get("tecnico")
        with transaction.atomic():
            for numero in (1, 2, 3):
                fecha = datos.get(f"fecha_{numero}")
                existente = MantenimientoPreventivo.objects.filter(laboratorio=laboratorio, anio=anio, numero=numero).first()
                if not fecha:
                    if existente and existente.estado == MantenimientoPreventivo.Estado.PENDIENTE:
                        existente.delete()
                    continue
                if existente:
                    existente.fecha_programada = fecha
                    existente.tecnico = tecnico
                    existente.actualizado_por = request.user
                    existente.full_clean()
                    existente.save()
                else:
                    nuevo = MantenimientoPreventivo(laboratorio=laboratorio, anio=anio, numero=numero, fecha_programada=fecha, tecnico=tecnico, creado_por=request.user)
                    nuevo.full_clean()
                    nuevo.save()
        messages.success(request, f"Se guardó el cronograma {anio} de {laboratorio.nombre}.")
        return redirect(f"{reverse('preventivo:cronograma')}?anio={anio}")


class MarcarRealizadoView(AccesoPreventivo, View):
    permission_required = "cuentas.editar_preventivos"

    def get_mantenimiento(self, request, pk):
        mantenimiento = get_object_or_404(MantenimientoPreventivo.objects.select_related("laboratorio", "tecnico"), pk=pk)
        if not gestiona_cronograma(request.user) and mantenimiento.tecnico_id != request.user.pk:
            raise PermissionDenied("Solo puedes marcar los mantenimientos que tienes asignados.")
        return mantenimiento

    def get(self, request, pk):
        mantenimiento = self.get_mantenimiento(request, pk)
        return render(request, "preventivo/marcar_realizado.html", {"mantenimiento": mantenimiento, "form": MarcarRealizadoForm(instance=mantenimiento)})

    def post(self, request, pk):
        mantenimiento = self.get_mantenimiento(request, pk)
        form = MarcarRealizadoForm(request.POST, instance=mantenimiento)
        if not form.is_valid():
            return render(request, "preventivo/marcar_realizado.html", {"mantenimiento": mantenimiento, "form": form})
        mantenimiento = form.save(commit=False)
        mantenimiento.estado = MantenimientoPreventivo.Estado.REALIZADO
        mantenimiento.actualizado_por = request.user
        mantenimiento.save()
        messages.success(request, f"{mantenimiento} quedó marcado como realizado.")
        return redirect("intervenciones:mis_tareas" if not gestiona_cronograma(request.user) else "preventivo:cronograma")


class MarcarPendienteView(AccesoPreventivo, View):
    """Corrige un mantenimiento marcado como realizado por error."""

    permission_required = "cuentas.editar_preventivos"

    def post(self, request, pk):
        mantenimiento = get_object_or_404(MantenimientoPreventivo, pk=pk)
        if not gestiona_cronograma(request.user) and mantenimiento.tecnico_id != request.user.pk:
            raise PermissionDenied("Solo puedes cambiar los mantenimientos que tienes asignados.")
        mantenimiento.estado = MantenimientoPreventivo.Estado.PENDIENTE
        mantenimiento.fecha_realizada = None
        mantenimiento.actualizado_por = request.user
        mantenimiento.save(update_fields=["estado", "fecha_realizada", "actualizado_por", "actualizado_en"])
        messages.info(request, f"{mantenimiento} volvió a estar pendiente.")
        return redirect(f"{reverse('preventivo:cronograma')}?anio={mantenimiento.anio}")
