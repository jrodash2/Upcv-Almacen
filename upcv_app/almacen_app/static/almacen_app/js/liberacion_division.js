(function () {
  'use strict';
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.form-liberar-stock').forEach(function (form) {
      // Estimación informativa; el servidor revalida bajo bloqueo al confirmar.
      const preview = form.querySelector('.preview-liberacion-general');
      form.elements.cantidad.addEventListener('input', function () {
        const quantity = Number(this.value);
        const balance = Number(form.dataset.saldoGeneral);
        preview.textContent = this.value && Number.isFinite(quantity) && Number.isFinite(balance) && quantity > 0 ?
          formatoCantidad(Math.max(0, balance + quantity)) : 'Se recalculará al confirmar';
      });
      form.addEventListener('submit', function (event) {
        const justification = form.elements.justificacion;
        justification.setCustomValidity(justification.value.trim() ? '' : 'Ingrese una justificación.');
        if (!form.reportValidity() || !window.confirm('¿Confirma liberar esta cantidad al almacén general? La operación quedará registrada y no modifica el Kardex.')) {
          event.preventDefault();
          return;
        }
        form.querySelector('button[type="submit"]').disabled = true;
      });
      form.elements.justificacion.addEventListener('input', function () { this.setCustomValidity(''); });
    });
  });
})();
