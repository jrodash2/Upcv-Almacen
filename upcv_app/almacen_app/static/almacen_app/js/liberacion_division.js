(function () {
  'use strict';
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.form-liberar-stock').forEach(function (form) {
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
