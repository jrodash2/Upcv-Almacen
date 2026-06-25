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

        $('.datatable, table.display').each(function () {
            var $table = $(this);
            $table.addClass('display');

            if (!$table.parent().hasClass('table-responsive')) {
                $table.wrap('<div class="table-responsive"></div>');
            }

            if ($.fn.DataTable.isDataTable(this) || !hasRealRows(this)) {
                return;
            }

            $table.DataTable({
                pageLength: 10,
                lengthMenu: [10, 25, 50, 100],
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

    function normalizeRihoModals() {
        $('.modal-dialog').addClass('modal-dialog-centered');
        $('.modal .modal-footer .btn[data-bs-dismiss], .modal .modal-footer .btn[data-dismiss]').addClass('btn-secondary');
    }

    $(document).ready(function () {
        enhanceRihoUI();
        initRihoDataTables();
        normalizeRihoModals();
        if (window.feather) {
            window.feather.replace();
        }
    });
})(window.jQuery);
