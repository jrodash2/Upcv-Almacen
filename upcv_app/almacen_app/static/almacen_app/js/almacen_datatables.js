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

    function ensureRihoTableMarkup(table, index) {
        var $table = $(table);
        $table.addClass('display datatables');

        if (!$table.attr('id')) {
            $table.attr('id', 'tabla-almacen-' + (index + 1));
        }

        var $wrapper = $table.parent();
        if (!$wrapper.hasClass('table-responsive')) {
            $table.wrap('<div class="dt-ext table-responsive custom-scrollbar"></div>');
            $wrapper = $table.parent();
        } else {
            $wrapper.addClass('dt-ext custom-scrollbar');
        }

        if (!$table.closest('.card').length) {
            var title = ($table.attr('id') || 'Listado').replace(/^tabla-/, '').replace(/-/g, ' ');
            title = title.charAt(0).toUpperCase() + title.slice(1);
            $wrapper.wrap('<div class="card"><div class="card-body"></div></div>');
            $wrapper.closest('.card').prepend(
                '<div class="card-header pb-0 card-no-border"><h4>' + title + '</h4><span>Listado de registros.</span></div>'
            );
        } else {
            $table.closest('.card').find('> .card-header').addClass('pb-0 card-no-border');
        }
    }

    function initRihoDataTables() {
        if (!$.fn || !$.fn.DataTable) {
            return;
        }

<<<<<<< HEAD
        $('.datatables, table.display').each(function (index) {
            ensureRihoTableMarkup(this, index);
=======
        $('.datatable, table.display').each(function () {
            var $table = $(this);
            $table.addClass('display');

            if (!$table.parent().hasClass('table-responsive')) {
                $table.wrap('<div class="table-responsive"></div>');
            }
>>>>>>> main

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
                    infoFiltered: '(filtrado de _MAX_ registros)',
                    zeroRecords: 'No se encontraron registros',
                    emptyTable: 'No hay datos disponibles',
                    paginate: {
                        previous: 'Anterior',
                        next: 'Siguiente'
                    }
                }
            });
        });
    }

<<<<<<< HEAD
=======
    function normalizeRihoModals() {
        $('.modal-dialog').addClass('modal-dialog-centered');
        $('.modal .modal-footer .btn[data-bs-dismiss], .modal .modal-footer .btn[data-dismiss]').addClass('btn-secondary');
    }

>>>>>>> main
    $(document).ready(function () {
        enhanceRihoUI();
        initRihoDataTables();
<<<<<<< HEAD
        $('.modal-dialog').addClass('modal-dialog-centered');
=======
        normalizeRihoModals();
>>>>>>> main
        if (window.feather) {
            window.feather.replace();
        }
    });
})(window.jQuery);
