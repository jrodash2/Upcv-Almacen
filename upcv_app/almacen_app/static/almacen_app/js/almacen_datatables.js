(function ($) {
    'use strict';

    function hasRealRows(table) {
        var firstBodyRow = table.querySelector('tbody tr');
        if (!firstBodyRow) {
            return false;
        }
        var cells = firstBodyRow.querySelectorAll('td, th');
        return !(cells.length === 1 && cells[0].hasAttribute('colspan'));
    }

    function initRihoDataTables() {
        if (!$.fn || !$.fn.DataTable) {
            return;
        }

        $('.datatable').each(function () {
            if (!$(this).parent().hasClass('table-responsive')) {
                $(this).wrap('<div class="table-responsive riho-table-responsive"></div>');
            } else {
                $(this).parent('.table-responsive').addClass('riho-table-responsive');
            }

            if ($.fn.DataTable.isDataTable(this) || !hasRealRows(this)) {
                return;
            }

            $(this).DataTable({
                pageLength: 10,
                lengthMenu: [10, 25, 50, 100],
                responsive: false,
                autoWidth: false,
                scrollX: true,
                language: {
                    search: 'Buscar:',
                    lengthMenu: 'Mostrar _MENU_ registros',
                    info: 'Mostrando _START_ a _END_ de _TOTAL_ registros',
                    infoEmpty: 'Mostrando 0 a 0 de 0 registros',
                    infoFiltered: '(filtrado de _MAX_ registros totales)',
                    zeroRecords: 'No se encontraron registros',
                    emptyTable: 'No hay datos disponibles',
                    paginate: {
                        first: 'Primero',
                        previous: 'Anterior',
                        next: 'Siguiente',
                        last: 'Último'
                    }
                }
            });
        });
    }

    function classifyModalButton(button) {
        var $button = $(button);
        var text = ($button.text() || '').toLowerCase();

        if ($button.is('[data-bs-dismiss], [data-dismiss]') || text.includes('cancelar') || text.includes('cerrar')) {
            $button.addClass('riho-modal-btn-secondary');
            return;
        }

        if ($button.hasClass('btn-danger') || $button.hasClass('btn-warning') || /eliminar|rechazar|anular|borrar/.test(text)) {
            $button.addClass('riho-modal-btn-danger');
            return;
        }

        if ($button.hasClass('btn-primary') || $button.hasClass('btn-success') || $button.is('[type="submit"]') || /guardar|aceptar|confirmar|crear|asignar|despachar|transferir/.test(text)) {
            $button.addClass('riho-modal-btn-primary');
        }
    }

    function enhanceRihoModal(modal) {
        var $modal = $(modal);
        var $content = $modal.find('.modal-content').first();
        var $body = $modal.find('.modal-body').first();
        var logoUrl = window.ALMACEN_MODAL_LOGO_URL || '/static/assets/images/logo/logo.png';

        if (!$content.length) {
            return;
        }

        $content.addClass('riho-modal');
        $body.addClass('riho-modal-body');

        var $title = $content.find('.riho-modal-title').first();
        if (!$title.length) {
            $title = $content.find('.modal-title, .modal-heading h4, .modal-heading h5, .theme-name').first();
            $title.addClass('riho-modal-title');
        }

        $content.find('img[src*="logo"], img[src*="upcv"]').addClass('riho-modal-logo');

        var hasLogo = $content.find('.riho-modal-logo-wrapper, img.riho-modal-logo').length > 0;
        if (!hasLogo) {
            var $logo = $('<div class="riho-modal-logo-wrapper"><img class="riho-modal-logo" alt="Logo UPCV"></div>');
            $logo.find('img').attr('src', logoUrl);

            if ($title.length) {
                var $anchor = $title.closest('.title-wrapper, .modal-heading, .modal-header');
                ($anchor.length ? $anchor : $title).after($logo);
            } else if ($body.length) {
                $body.prepend($logo);
            } else {
                $content.prepend($logo);
            }
        }

        if (!$content.find('.riho-modal-divider').length) {
            var $footer = $content.children('.modal-footer').first();
            if ($footer.length) {
                $footer.before('<div class="riho-modal-divider"></div>');
            }
        }

        $content.find('.modal-body > p').addClass('riho-modal-text');
        $content.find('.btn').each(function () {
            classifyModalButton(this);
        });
    }

    function enhanceRihoModals() {
        $('.modal').each(function () {
            enhanceRihoModal(this);
        });
    }

    $(document).ready(function () {
        initRihoDataTables();
        enhanceRihoModals();

        document.addEventListener('show.bs.modal', function (event) {
            enhanceRihoModal(event.target);
        });
    });
})(window.jQuery);
