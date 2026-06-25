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

        $('.page-body table').not('.no-datatable, .riho-detail-table').each(function () {
            var $table = $(this);
            if (!$table.hasClass('datatable')) {
                $table.addClass('display datatables table table-hover riho-table datatable');
            }
            if (!$table.attr('id')) {
                $table.attr('id', 'tabla-riho-' + ($('.page-body table').index(this) + 1));
            }
        });

        $('.datatable').each(function () {
            if (!$(this).parent().hasClass('table-responsive')) {
                $(this).wrap('<div class="table-responsive theme-scrollbar"></div>');
            }

            if ($.fn.DataTable.isDataTable(this) || !hasRealRows(this)) {
                return;
            }

            $(this).DataTable({
                pageLength: 10,
                lengthMenu: [10, 25, 50, 100],
                responsive: true,
                autoWidth: false,
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



    function enhanceRihoUI() {
        $('.page-body .card').addClass('riho-card');
        $('.page-body table').not('.riho-detail-table').addClass('display datatables table table-hover riho-table');
        $('.page-body .table-responsive').addClass('theme-scrollbar');
        $('.page-body select').addClass('form-select').removeClass('form-control');
        $('.page-body input:not([type=checkbox]):not([type=radio]), .page-body textarea').addClass('form-control');
        $('.page-body input[type=checkbox]').addClass('form-check-input');
        $('.page-body label').addClass('form-label');
        $('.page-body td:last-child, .page-body .card-header .text-end, .page-body .form-footer').addClass('riho-actions');

        var iconMap = [
            [/crear|nuevo|agregar|añadir/i, 'plus-circle'],
            [/editar|actualizar/i, 'edit'],
            [/eliminar|borrar|anular/i, 'trash-2'],
            [/ver|detalle|seguimiento/i, 'eye'],
            [/pdf|imprimir/i, 'file-text'],
            [/guardar|confirmar|asignar|despachar|convertir/i, 'check-circle'],
            [/cancelar|volver|cerrar/i, 'x-circle']
        ];
        $('.page-body .btn').each(function () {
            var $btn = $(this);
            if ($btn.find('svg.feather, i[data-feather]').length) return;
            var text = $.trim($btn.text());
            for (var i = 0; i < iconMap.length; i++) {
                if (iconMap[i][0].test(text)) {
                    $btn.prepend('<i data-feather="' + iconMap[i][1] + '"></i> ');
                    break;
                }
            }
        });
        if (window.feather) { window.feather.replace(); }
    }

    function enhanceRihoModals() {
        $('.modal').each(function () {
            enhanceRihoModal(this);
        });
    }

    $(document).ready(function () {
        enhanceRihoUI();
        initRihoDataTables();
        enhanceRihoModals();

        document.addEventListener('show.bs.modal', function (event) {
            enhanceRihoModal(event.target);
        });
    });
})(window.jQuery);
