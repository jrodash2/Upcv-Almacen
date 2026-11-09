/* Conservar el modal y mostrar el motivo real sin borrar filas por error. */
(function () {
  'use strict';
  document.addEventListener('DOMContentLoaded', function () {
    const element = document.getElementById('confirmDeleteModal');
    const button = document.getElementById('confirmDeleteButton');
    const reason = document.getElementById('motivoEliminarDetalle');
    const message = document.getElementById('errorEliminarDetalle');
    if (!element || !button || !message || !reason) return;
    const modal = bootstrap.Modal.getOrCreateInstance(element);
    let deleteUrl = '';
    let busy = false;
    document.querySelectorAll('.eliminar-detalle-btn').forEach(function (trigger) {
      trigger.addEventListener('click', function () {
        if (busy) return;
        deleteUrl = trigger.dataset.url;
        reason.value = '';
        message.hidden = true;
        message.textContent = '';
        modal.show();
      });
    });
    // No permitir cambiar de fila mientras la eliminación está en curso.
    element.addEventListener('hide.bs.modal', function (event) {
      if (busy) event.preventDefault();
    });
    button.addEventListener('click', async function () {
      if (busy || !deleteUrl) return;
      if (!reason.reportValidity()) return;
      busy = true;
      button.disabled = true;
      message.hidden = true;
      try {
        const csrf = document.querySelector('[name=csrfmiddlewaretoken]');
        if (!csrf) throw new Error('Recargue la página para renovar la protección de la solicitud.');
        const response = await fetch(deleteUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {'X-CSRFToken': csrf.value, 'Accept': 'application/json'},
          body: new URLSearchParams({requerimiento_id: element.dataset.requerimientoId, motivo: reason.value.trim()}),
        });
        const json = (response.headers.get('content-type') || '').includes('application/json');
        if (response.redirected || !json) {
          throw new Error(response.status === 403 ?
            'La solicitud fue rechazada. Compruebe sus permisos y recargue la página para renovar la sesión.' :
            'No se recibió una confirmación válida. Recargue la página y compruebe su sesión antes de reintentar.');
        }
        const data = await response.json();
        if (!response.ok || data.success !== true) {
          throw new Error(data.error || 'No se pudo eliminar el detalle (HTTP ' + response.status + ').');
        }
        window.location.reload();
      } catch (error) {
        message.textContent = error instanceof TypeError ?
          'No se pudo confirmar la eliminación por un problema de conexión. Recargue para comprobar el estado antes de reintentar.' : error.message;
        message.hidden = false;
      } finally {
        busy = false;
        button.disabled = false;
      }
    });
  });
})();
