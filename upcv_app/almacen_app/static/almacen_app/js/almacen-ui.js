/* Mejoras exclusivamente visuales. No cambia valores, validaciones, eventos,
   estado disabled, navegación, inicialización de plugins ni peticiones. */
(function () {
    'use strict';
    function decorate(root) {
        root.querySelectorAll('.modal-title, .modal-heading h5').forEach(function (heading) {
            if (heading.querySelector('i, svg')) return;
            var title = heading.textContent;
            var icon = /eliminar|quitar|desasignar/i.test(title) ? 'trash' :
                /rever/i.test(title) ? 'history' : /transfer|asign/i.test(title) ? 'exchange' :
                /editar/i.test(title) ? 'edit' : /crear|agregar/i.test(title) ? 'plus' : 'file';
            heading.classList.add('almacen-modal-icon', 'almacen-icon-' + icon);
        });
        root.querySelectorAll('.btn').forEach(function (button) {
            var text = button.textContent.trim().replace(/^[←→\s]+/, '');
            var intent;
            if (/^(cancelar|volver|regresar|cerrar)\b/i.test(text)) intent = 'cancel';
            else if (/^(eliminar|quitar)\b/i.test(text)) intent = 'delete';
            else if (/^(revertir|desactivar|anular)\b/i.test(text)) intent = 'warning';
            else if (/^activar\b/i.test(text)) intent = 'activate';
            else if (/^(guardar|crear|confirmar|agregar)\b/i.test(text)) intent = 'save';
            else if (/^editar\b/i.test(text)) intent = 'edit';
            else if (/^(ver|consultar|detalle)\b/i.test(text)) intent = 'view';
            if (intent) button.classList.add('almacen-action-' + intent);
            if (!button.querySelector('i, svg') && /PDF/i.test(text)) button.classList.add('almacen-download-pdf');
            if (!button.querySelector('i, svg') && /Excel/i.test(text)) button.classList.add('almacen-download-excel');
        });
        root.querySelectorAll('input[required]:not([type=hidden]):not([type=checkbox]):not([type=radio]), select[required], textarea[required]').forEach(function (field) {
            // Usar la asociación nativa: también funciona con IDs que contienen caracteres especiales.
            Array.from(field.labels || []).forEach(function (label) {
                if (label.textContent.includes('*') || label.querySelector('.almacen-required')) return;
                var mark = document.createElement('span');
                mark.className = 'almacen-required';
                mark.textContent = '*';
                mark.setAttribute('aria-hidden', 'true');
                label.appendChild(mark);
            });
        });
    }
    document.addEventListener('DOMContentLoaded', function () {
        if (!document.body.classList.contains('almacen-ui')) return;
        decorate(document);
        document.querySelectorAll('.sidebar-wrapper a[href]').forEach(function (link) {
            var target = new URL(link.getAttribute('href'), location.href);
            if (target.origin === location.origin && target.pathname === location.pathname && !target.hash && link.getAttribute('href') !== '#') {
                link.setAttribute('aria-current', 'page');
            }
        });
        document.addEventListener('shown.bs.modal', function (event) { decorate(event.target); });
        if (window.jQuery) {
            window.jQuery(document).on('draw.dt', function (event) { decorate(event.target); });
        }
    });
})();
