# Diseño institucional de Almacén

## Archivos y alcance

- `upcv_app/almacen_app/static/almacen_app/css/almacen-ui.css`: capa de presentación sobre Riho y Bootstrap, limitada a `.almacen-ui` y a pantalla. Variables de colores, superficies, tipografía Montserrat existente, bordes, sombras, espaciados y transiciones. Unifica botones, formularios, cards, modales, tablas/DataTables, paginación, badges, alertas, menú y barra superior. Contempla modo oscuro y movimiento reducido.
- `upcv_app/almacen_app/static/almacen_app/js/almacen-ui.js`: añade clases de intención visual a botones, iconos decorativos, asteriscos en etiquetas de campos que **ya** tienen `required` e indicador `aria-current` en enlaces del menú. Decora nuevamente al abrir un modal y al dibujar DataTables. No cambia valores, obligatoriedad, IDs, nombres, tipos de botón, estado disabled, eventos de negocio ni inicialización de plugins.
- `upcv_app/almacen_app/templates/almacen/base.html`: carga única de CSS después de los estilos Riho, JS diferido y versión `?v=20261021.1`. Idioma español. Centralización de las reglas locales de perfil/footer y corrección del cierre de contenedor condicional de la frase del día: el menú vuelve a quedar dentro de `.page-wrapper` tanto con frase como sin ella. Iconos y logos del layout usan `{% static %}`; conserva el logo institucional configurado y ofrece el logo existente como respaldo.
- `upcv_app/almacen_app/templates/almacen/agregar_detalle_factura.html`: elimina el bloque local que redefinía todas las cards y contenedores; el detalle queda en una card común. El contenedor interior deja de duplicar `.page-body`. Encabezados de tabla heredan el contraste común. Mantiene campos, IDs, rutas, POST y scripts originales.
- `upcv_app/almacen_app/templates/almacen/crear_solicitud_requerimiento.html` y `solicitudes/modal_articulos.html`: indicadores visuales de obligatoriedad en Tipo de solicitud y Cantidad a agregar, cuyas validaciones ya existían; no cambian atributos ni procesamiento.

No se editan archivos de terceros, modelos, migraciones, permisos, URLs, APIs, cálculos, inventario, reservas, moneda ni PDFs/Excel. Las plantillas de impresión no cargan la nueva capa de pantalla. No se incorporan bibliotecas: Bootstrap 5.3.0, DataTables, Font Awesome, Feather y Riho ya estaban incluidos. No se detectó carga activa de SweetAlert2 ni Select2 en el layout; los estilos compatibles no cargan ni inicializan esas bibliotecas.

Los `!important` se limitan a colores de botones semánticos (Riho ya fija esos colores con `!important`) y a la accesibilidad de movimiento reducido. No se alteran indiscriminadamente las utilidades Bootstrap. Al modificar CSS/JS en el futuro, incrementar su versión en `base.html` y ejecutar `collectstatic`.

## Revisión y pruebas

Pantallas revisadas: Dashboard, Artículos, Formulario 1H, detalle de factura, Stock, Kardex, listado y detalle de Divisiones, Asignaciones, Mis Artículos Asignados, Crear Solicitud, listado de Solicitudes, Requerimientos, detalle/despacho, historial de Reversiones, Libro Mayor, Carga Inicial y Configuración institucional. La configuración de empleados, con otro layout, no se modifica.

Se utiliza una base PostgreSQL de prueba con artículos, asignaciones, división, factura y requerimiento; no datos productivos. Verificación en Chromium mediante Playwright, en escritorio y teléfono, con apertura/cierre de modales presentes, restauración de backdrop/scroll, carga del CSS común y capturas para inspección. El flujo real de solicitud cubre filtros, dos fuentes del mismo artículo, acumulación sin duplicados, Quitar, retiro por categoría, recarga, guardado POST y reservas en base de datos.

Resultado de revisión: 18 pantallas a 1440px y 390px, sin desbordamiento horizontal de página una vez concluyen las transiciones; las tablas anchas conservan su scroll interno. Comprobación adicional a 768px: foco visible, movimiento reducido, asteriscos, contraste de Cancelar, modales, menú y ausencia de reinicialización de DataTables. La comparación de errores JavaScript con las mismas pantallas y plantillas anteriores no detectó excepciones nuevas.

Comandos de regresión:

```bash
python manage.py check
python manage.py test almacen_app --noinput
```

La suite ejecutó 83 pruebas: 74 aprobadas, con los mismos 3 fallos previos de Kardex y 6 errores previos de fixtures de Reversiones. La comparación con la línea base no mostró casos nuevos que fallen. Persisten las advertencias conocidas de namespace duplicado y ForeignKey único.

La comparación del navegador contra las plantillas anteriores identificó excepciones previas de scripts en algunas vistas: `series is not defined`, `$ is not defined`, `simpleDatatables is not defined`, acceso a `classList`/`top` y `_DT_CellIndex` en tablas con filas especiales. Se documentan sin modificar su lógica en una tarea exclusivamente visual. No equivalen a una certificación de todas las operaciones de negocio de esos módulos.

Entorno local: Python 3.12.14, Django 5.1.4 y PostgreSQL 17. IIS/Windows no se ejecutó desde este entorno.

## Despliegue en IIS

Con el código actualizado y el entorno virtual de producción activo:

```powershell
cd "C:\Users\Administrador\Documents\AppAlmacen\upcv_app"
C:\Python\python.exe manage.py check
C:\Python\python.exe manage.py collectstatic --noinput
```

Usar el ejecutable real del entorno de IIS si difiere de `C:\Python\python.exe`. Reciclar el Application Pool **AppAlmacen** y recargar el navegador completamente. Comprobar HTTP 200 para `almacen-ui.css?v=20261021.1` y `almacen-ui.js?v=20261021.1` en la pestaña Red. No se necesitan migraciones ni cambios de datos.

Validación en servidor: recorrer los módulos anteriores con sus roles habituales; comprobar navegación y submenús, botones, campos obligatorios, orden/búsqueda/paginación, apertura y cierre de modales y selección de fuentes. Guardar una solicitud de prueba según el procedimiento de la institución. Revisar a 390px, 768px y escritorio, y con preferencia de movimiento reducido. Confirmar que los PDFs/Excel y cantidades/moneda conservan su formato anterior.
