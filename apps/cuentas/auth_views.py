from django.contrib.auth.views import PasswordChangeView, PasswordResetConfirmView


class CambioContrasenaView(PasswordChangeView):
    def form_valid(self, form):
        response = super().form_valid(form)
        usuario = self.request.user
        if usuario.force_password_change:
            usuario.force_password_change = False
            usuario.save(update_fields=["force_password_change"])
        return response


class RestablecerContrasenaConfirmView(PasswordResetConfirmView):
    def form_valid(self, form):
        response = super().form_valid(form)
        if self.user and self.user.force_password_change:
            self.user.force_password_change = False
            self.user.save(update_fields=["force_password_change"])
        return response
