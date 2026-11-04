# Reparación de Asignar artículo desde Detalle de Factura

## Causa comprobada

El commit `36311fa` sustituyó el saldo entero calculado en la vista por
`resumen_global_articulo(...)["disponible_para_division"]`, que devuelve `Decimal`.
El template seguía interpolando `{{ stock_dict|safe }}` dentro de un script.
Con existencias, el navegador recibía `{9876: Decimal('50')}` y lanzaba
`ReferenceError: Decimal is not defined` antes de registrar el evento `input`.
Por ello no había petición AJAX ni selección que actualizara descripción o stock.
El fallo se reprodujo con el template original en Chromium; antes del cambio
`36311fa` el mismo punto recibía enteros. La búsqueda existente ya consultaba
`Articulo.codigo` y `Articulo.nombre`; la descripción del catálogo es `nombre`,
no existe un campo `Articulo.descripcion`.

Había dos defectos adicionales de este mismo procedimiento: no se mostraban los
errores del formulario y la señal `notificar_asignacion` accedía a
`.first().usuario` aun cuando el departamento no tenía usuario asociado. En ese
caso la transacción se revertía. La prueba correspondiente reproduce el fallo
antes de corregirlo. Una cantidad cero también podía guardarse al omitir el
JavaScript; ahora se rechaza explícitamente.

## Cambios delimitados

- `upcv_app/almacen_app/views.py`: `crear_asignacion_detalle` deja de incrustar
  diccionarios Python como código. Conserva la última asignación y muestra errores
  de validación. `buscar_articulos` conserva su contrato normal; únicamente con
  `asignacion_directa=1` añade `existencias`, obtenidas del servicio real y
  serializadas por Django. Ese modo usa los mismos roles de la pantalla
  (Administrador, Almacen o superusuario). No cambia los permisos del catálogo.
- `upcv_app/almacen_app/templates/almacen/crear_asignacion_detalle.html`: mantiene
  Riho y el card Última Asignación, muestra código, descripción, categoría,
  renglón, existencia física, disponibilidad y errores. Usa `json_script` para
  restaurar una selección tras errores de validación y URL resuelta por Django.
- `upcv_app/almacen_app/static/almacen_app/js/asignacion_directa.js`: enlaza la
  búsqueda por código/nombre, mantiene la PK interna para el POST, muestra datos
  aun con stock cero y evita selecciones obsoletas o respuestas AJAX tardías.
  Los fallos HTTP se muestran al usuario; nunca se sustituyen por existencias
  ficticias. Valida cantidades enteras positivas dentro del saldo.
- `upcv_app/almacen_app/form.py`: valida cantidades positivas y suficientes en
  `clean`, conservando el filtro existente de artículos asignables y el bloqueo
  `select_for_update` y recálculo al guardar. Esto también protege el POST directo.
- `upcv_app/almacen_app/signals.py`: no exige un usuario de correo para guardar
  una asignación; conserva la notificación cuando existe un destinatario.
- `upcv_app/almacen_app/test_asignacion_directa.py`: pruebas de búsqueda, límites,
  guardado, historial, permisos, falta de destinatario y concurrencia PostgreSQL.

No se modificaron modelos, migraciones, fórmulas de inventario, confirmación 1H,
servicios de divisiones, reservas, despachos, Kardex, reversiones, precios ni
correlativos. `existencia_general_articulo` representa existencia física;
`resumen_global_articulo` calcula el saldo sin comprometer y ya considera
consumos y reservas. Se reutilizan sin cambiar sus fórmulas. El nombre interno
`disponible_para_division` también es el saldo que el formulario directo ya usaba.
Una asignación directa nueva no registra una asignación de división ni cambia
la existencia física: compromete parte de ella.

## Validación

Desde `upcv_app`, con el Python/venv del proyecto y una base PostgreSQL de pruebas:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test almacen_app.test_asignacion_directa --noinput
python manage.py test almacen_app --noinput
```

Se probó Django 5.1.4 con PostgreSQL 17, señales reales y transacciones. El catálogo
de pruebas usa **PK 9876 / código 675**, con descripción
`Medalla 2.5" Dorada de metal incluye cinta`, categoría y renglón explícitos.
El escenario contiene ingreso confirmado 80 y compromiso a división 30:
existencia física 80 y disponibilidad directa 50. Son fixtures de una base temporal,
no datos agregados al inventario real.

Las 11 pruebas nuevas verifican: búsqueda por código/nombre/texto de descripción;
contrato AJAX compartido; saldos reales y descripción con disponibilidad cero;
permisos conservados; página sin `Decimal(...)`; asignaciones de 1, 25 y 50;
rechazo de 51, cero, negativos, vacío y fracciones; historial anterior intacto;
última asignación; revalidación si cambia el saldo; departamentos sin usuario;
y dos transacciones compitiendo por el mismo saldo (solo una guarda).

Chromium verificó el flujo completo con AJAX real: selección y PK interna,
descripción/categoría/renglón, stock físico/disponible, límites frontend, POST de
25, última asignación, división intacta, descripción con saldo cero, bloqueo de
asignación y respuesta HTTP 500 explícita. No hubo IDs duplicados ni errores de
`asignacion_directa.js`. El template original produjo `Decimal is not defined`.
Persisten errores globales previos de Riho en `sidebar-pin.js` (elemento nulo) y
`custom-list-product.js` (`simpleDatatables` no definido), reproducidos también
con el template original. Se dejan fuera de esta reparación y no se silencian.

La suite completa ejecutó 120 pruebas: **110 aprobadas, 3 fallos y 7 errores**,
sin omisiones. Los diez resultados no aprobados son los mismos de la base inicial:
seis fixtures de reversiones duplican el grupo Gestor, tres pruebas de Kardex
presentan saldos/filas de fixtures incompatibles con los movimientos reales y la
prueba PDF exige firmas comentadas en su plantilla. Por ello no se afirma que
Kardex/reversiones o la suite completa estén totalmente aprobados. Las pruebas
existentes de confirmación 1H, divisiones, disponibilidad administrativa y por
departamento, solicitudes, reservas, conversión y despachos siguen aprobando.
`check` conserva dos advertencias previas: namespace almacen duplicado y ForeignKey
con unique. No se detectaron migraciones nuevas. `collectstatic` se comprobó en
un directorio local externo al checkout y el JavaScript recolectado coincide.

## Datos históricos y artículo 675 real

No se ejecutaron ajustes ni cambios sobre existencias o asignaciones históricas.
Las escrituras de validación ocurrieron únicamente en bases temporales de pruebas,
que se eliminaron al finalizar. La base de desarrollo preparada en la nube no
contiene el artículo 675 y no hay conexión a PostgreSQL de producción; por tanto,
no se puede afirmar que sus saldos reales estén reconciliados.

Para auditar producción sin modificar registros, localizar primero la PK por
`Articulo.codigo='675'` y pasar **esa PK**, no el código comercial, al comando
existente:

```powershell
python manage.py shell -c "from almacen_app.models import Articulo; print(list(Articulo.objects.filter(codigo='675').values('pk','codigo','nombre')))"
python manage.py auditar_articulo_1h --articulo PK_REAL > diagnostico-675.json
```

El comando usa una transacción de solo lectura. Si informa `requiere_revision`,
revisar sus ingresos, compromisos, consumos y orígenes por separado; no crear
inventario, resetear contadores ni eliminar históricos para habilitar el formulario.
También persiste un error previo de la notificación HTML en el modelo que consulta
`Articulo.descripcion`; el modelo registra el error y no impide guardar. No se
modificó ese modelo ni se declara reparado el correo HTML en este trabajo.

## Actualización en Windows Server / IIS

1. Respaldar el despliegue y usar el procedimiento habitual de actualización del
   repositorio. Desplegar juntos los archivos Python, template y JavaScript listados
   arriba. Conservar la configuración PostgreSQL y el venv reales de IIS; no copiar
   `cloud_settings.py` ni la base local de la nube al servidor.
2. Desde la carpeta real `upcv_app`, activar el venv de IIS y ejecutar:

   ```powershell
   python manage.py check
   python manage.py makemigrations --check --dry-run
   python manage.py collectstatic --noinput
   ```

   No hay migraciones nuevas ni script de ajuste de datos que aplicar.
3. Reciclar el Application Pool **AppAlmacen** (o el nombre real del sitio).
4. Recargar completamente el navegador. Comprobar HTTP 200 para
   `static/almacen_app/js/asignacion_directa.js?v=20261104.1` y que el endpoint de
   búsqueda resuelto por Django devuelve `id`, `codigo`, `nombre`, `categoria`,
   `renglon_presupuestario` y `existencias` al usar `asignacion_directa=1` con sesión
   autorizada.
5. Buscar 675 y verificar descripción y saldo contra la auditoría de solo lectura.
   En un ambiente de pruebas, guardar una cantidad válida, comprobar Última
   Asignación, rechazar exceso y revisar un artículo agotado. No crear asignaciones
   de prueba en el inventario productivo.

Los cambios no dependen de rutas Linux, servicios de la nube ni paquetes nuevos.
La comprobación real en IIS queda pendiente del despliegue en ese servidor.
