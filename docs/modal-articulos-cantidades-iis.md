# Modal de artículos y formato de cantidades

## Cambios

- `crear_solicitud_requerimiento.html` y `solicitudes/modal_articulos.html`: Agregar ítem abre un modal Bootstrap/Riho con búsqueda por código/nombre, categorías seleccionadas y origen. Cada asignación conserva su identificador D/V, muestra sus saldos y deshabilita fuentes agotadas. Una fuente repetida acumula cantidades en su fila; fuentes diferentes siguen separadas. Se mantienen controles originales del formset, eliminación mediante API de DataTables y envío de filas activas.
- `views.py`: el catálogo del modal solicita explícitamente `incluir_agotados=1`; conserva autorización y filtrado de categorías. Las demás consultas mantienen su contrato anterior. Metadatos de categoría para las etiquetas.
- `formatos_cantidades.py`, `templatetags/cantidad_filters.py`, `templatetags/custom_filters.py` y `static/almacen_app/js/cantidades.js`: formato visual central; `1250.00` → `1,250`, `1.50` → `1.5`, sin redondear fracciones reales. El filtro anterior `cantidad_limpia` reutiliza el mismo helper. `quetzales` permanece intacto.
- Plantillas HTML/PDF de Formulario 1H, stock, departamentos, asignaciones, divisiones, solicitudes, requerimientos, Kardex, carga inicial, reversiones, transferencias y Libro Mayor: formato exclusivamente de cantidades físicas. `base.html` carga el helper JavaScript; dashboard y mensajes dinámicos lo usan para cantidades.
- `views.py`: cantidades numéricas de Excel de Formulario 1H y Libro Mayor con máscara `#,##0` o decimales opcionales según su precisión; importes monetarios conservan sus máscaras. PDF programático de ingresos utiliza el mismo formato visual.
- `form.py` y `disponibilidad.py`: únicamente formato de cantidades en etiquetas y mensajes, sin cambios a cálculos.
- Pruebas nuevas: `test_modal_articulos.py` y `test_formatos_cantidades.py`.

No se modifican modelos, migraciones, datos históricos, fórmulas de inventario, permisos ni cálculos financieros. Las cantidades fraccionarias existentes se conservan visualmente con toda su precisión; no se reclasifican unidades del catálogo. Solicitudes continúa exigiendo enteros positivos conforme a su validación existente. Los atributos y valores enviados al servidor siguen siendo números sin separadores.

## Validación

Entorno de prueba: Django 5.1.4, Python 3.12.14 y PostgreSQL 17. No se accedió a IIS ni a datos de producción.

- 66 pruebas específicas aprobadas: modal/backend, formatos, PDFs y Excel reales, categorías/justificación, disponibilidad y filas activas/eliminadas.
- 14 comprobaciones del helper JavaScript: enteros, separadores, fracciones largas, exponentes y valores no numéricos.
- Chromium/Playwright contra Django y PostgreSQL: filtros, agotados, visualización móvil, dos fuentes del mismo artículo, acumulación, cantidades inválidas, Quitar y POST real; verificación de detalles y reservas en base de datos.
- `check` y `makemigrations --check --dry-run`: sin migraciones nuevas; permanecen las advertencias previas de namespace duplicado y ForeignKey único.
- Suite completa: 83 pruebas, con los mismos 3 fallos de Kardex y 6 errores de fixtures de Reversiones presentes en la línea base; no se agregaron fallos nuevos. Los fallos previos se documentan, sin modificar sus cálculos ni fixtures en esta tarea.

La plantilla Riho ya registra excepciones de scripts genéricos (`top`, `classList`, `simpleDatatables`) en el entorno local; esta tarea no las modifica. La certificación final en Python 3.13.1/Windows requiere la comprobación en el servidor IIS.

## IIS

En `C:\Users\Administrador\Documents\AppAlmacen\upcv_app`, usando el Python/entorno virtual configurado para IIS:

```powershell
python manage.py check
python manage.py collectstatic --noinput
```

Reciclar el Application Pool **AppAlmacen** y hacer una recarga completa del navegador para renovar JavaScript. No se requieren migraciones por este cambio.

Comprobar con un Gestor: elegir departamento y categorías, abrir Agregar ítem, buscar por código/nombre, seleccionar Directo y División, quitar una fila y guardar. Confirmar cantidades y fuentes guardadas, sin reservas duplicadas. Revisar un entero de 1,250 unidades y una fracción real en pantalla/PDF/Excel; los valores monetarios deben mantener dos decimales.
