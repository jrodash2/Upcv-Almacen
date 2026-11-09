# Cancelación individual y liberación de reserva

## Comportamiento

En Detalle de Requerimiento se puede eliminar una fila pendiente, sin despachos
ni Kardex, indicando un motivo de 3 a 500 caracteres. La operación cancela la
fila y la retira del listado operativo; no la borra físicamente. El requerimiento,
su correlativo y las otras filas se conservan. Si no quedan detalles activos, la
pantalla lo indica y el backend no permite despachar un requerimiento vacío.

La tabla «Historial de detalles eliminados» de la misma pantalla conserva
artículo, cantidad original, usuario, fecha, motivo y fuente original. El vínculo
protegido con `DetalleSolicitudRequerimiento` permanece intacto. La solicitud
convertida conserva su desglose original y no puede volver a convertirse.

- Directo con solicitud: la reserva se calcula desde sus registros activos. Al
  cancelar la fila, deja de participar en ese cálculo, sin cambiar la cantidad
  asignada al departamento.
- División: se verifica el vínculo exacto y se contrasta el contador reservado
  con todas las reservas vigentes de esa fuente. Se resta exclusivamente la
  cantidad de la fila, manteniendo asignación de división, distribución a la
  ubicación y consumo.
- Directo sin solicitud: deja de contribuir a la reserva implícita del
  requerimiento. No se atribuye artificialmente a una asignación específica.

En todos los casos las unidades vuelven a estar disponibles en su fuente,
no al inventario general sin asignar. No se crea una entrada de Kardex ni se
cambian fórmulas globales de stock. Una cabecera con origen de solicitud y una
fila sin vínculo exacto se rechaza para revisión; no se reconstruye su origen
por coincidencia de artículo/departamento. Tampoco se ajustan contadores
inconsistentes para permitir la operación.

## Cambios y justificación técnica

- `models.py`: añade `cancelado_en`, `cancelado_por` y `motivo_cancelacion` a
  `DetalleRequerimiento`. El manager operativo `objects` excluye cancelados;
  `all_objects`, también base manager para relaciones históricas, los conserva.
  Esto permite que edición, despacho, listados y reservas implícitas operen
  sobre filas activas y que los vínculos históricos sigan resolviéndose.
- `migrations/0061_cancelacion_individual_detalle.py`: campos de auditoría y
  opciones de managers. Es necesaria porque no existía un estado de cancelación
  por fila con usuario/fecha/motivo. No contiene RunPython ni modifica cantidades.
  Los registros anteriores quedan activos por tener `cancelado_en = NULL`.
- `cancelacion_detalle.py`: servicio transaccional `cancelar_detalle_pendiente`.
  Bloquea artículo, departamento/fuentes, cabecera y detalle en ese orden;
  valida cantidad, origen, pertenencia, estado y Kardex antes de liberar.
- `views.py`: delega la eliminación al servicio, conserva validación de grupos,
  CSRF y errores JSON; carga el historial de cancelados para usuarios con acceso
  a la pantalla del requerimiento.
- `disponibilidad.py`: excluye explícitamente las filas canceladas de reservas
  directas y de `liberar_reservas_division`. Anular después no libera otra vez
  su reserva. No se modifica el cálculo de consumos físicos.
- `templates/almacen/detalle_requerimiento.html`: motivo obligatorio, explicación
  de la operación, mensaje de requerimiento vacío e historial; oculta el botón
  de despacho cuando no hay filas activas. Conserva el diseño existente.
- `static/almacen_app/js/eliminar_detalle_requerimiento.js`: envía motivo y cabecera,
  valida el campo y conserva bloqueo durante la petición, mensajes reales y
  confirmación explícita de éxito. Versión estática `20261109.2`.
- `test_eliminar_detalle_requerimiento.py` y `test_cancelacion_individual.py`:
  pruebas específicas, de regresión y de concurrencia.

La cancelación y la escritura de auditoría comparten transacción. Una excepción
revierte incluso una liberación ya efectuada. Dos peticiones simultáneas no
liberan dos veces: la segunda encuentra la fila fuera del manager operativo y
recibe 404. El borrado físico de la solicitud o de sus vínculos protegidos no
forma parte de esta operación.

## Verificación

```console
python manage.py test almacen_app.test_cancelacion_individual almacen_app.test_eliminar_detalle_requerimiento --noinput
```

22 pruebas correctas: reservas directas, división y sin solicitud; dos filas del
mismo artículo con fuentes distintas; conservación de otras filas; auditoría;
última fila; estados no permitidos; Kardex con contador cero; motivos inválidos;
orígenes ambiguos, reserva inconsistente; permisos, departamento ajeno, CSRF,
identificador de cabecera; reintentos; rollback posterior a la liberación;
anulación y conversión posteriores; despacho restante. Cuatro pruebas utilizan
conexiones PostgreSQL independientes para competir con otra cancelación,
anulación, conversión repetida y despacho de una cabecera enviada.

Suite completa: 201 pruebas, 191 correctas, los mismos 10 fallos previos
(3 aserciones y 7 errores de impresión/Kardex/fixtures de reversiones), sin nuevos
fallos frente al registro anterior. Esa ejecución incluye las cinco pruebas de
optimizaciones de Asignar Artículo que ya estaban pendientes; esas optimizaciones
no forman parte de esta reparación.

Chromium: motivo obligatorio; rechazo HTTP 500 sin retirar la fila; reintento;
doble clic con una sola petición; cancelación de división con reserva directa
intacta; historial visible y Kardex sin cambios. `check` conserva las dos
advertencias previas (namespace y ForeignKey única). Sintaxis JavaScript,
`makemigrations --check --dry-run`, `collectstatic` y `git diff --check` correctos.

Todas las modificaciones de datos se reprodujeron en bases de pruebas. No se
operó sobre el requerimiento 869 real ni se alteraron asignaciones históricas,
Formularios 1H, precios, correlativos, Kardex, despachos o inventario real.

## Actualizar Windows Server / IIS

Después de publicar y copiar esta versión, realizar el despliegue con el pool
detenido mientras se aplica la migración para que el sitio no consulte las nuevas
columnas antes de existir. Desde la carpeta que contiene `manage.py`, con el
mismo Python/configuración de base de datos utilizados por IIS:

```powershell
C:\Python\python.exe manage.py migrate
C:\Python\python.exe manage.py collectstatic --noinput
```

La migración nueva es `almacen_app.0061_cancelacion_individual_detalle`, posterior
a `0060_liberacion_stock_division`. La creación de columnas no cancela ni ajusta
filas existentes. Iniciar/reciclar el application pool después y recargar con
Ctrl+F5. Verificar que el archivo estático con `?v=20261109.2` carga correctamente.

Probar primero con un requerimiento de prueba: eliminar una sola fila, comprobar
la reserva de su fuente y el historial, y confirmar que las otras filas siguen
reservadas. No ejecutar scripts de ajuste de inventario.

Esta implementación no se ha publicado en GitHub; requiere solicitud expresa.
Las optimizaciones anteriores pendientes de Asignar Artículo siguen separadas.
