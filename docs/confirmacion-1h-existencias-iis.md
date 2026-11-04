# Confirmar un ingreso 1H sin usar el stock histórico como límite

## Por qué persistía el rechazo

La confirmación anterior hacía `DivisionArticulo.save()`, que llamaba a
`full_clean()` y después, desde `clean()`, a los cálculos de compromiso y existencia.
Confirmar primero la factura no evitaba esa segunda consulta: una inconsistencia
histórica seguía bloqueando el ingreso nuevo. La comparación seguía siendo global.

Ahora hay dos operaciones distintas:

* `confirmacion_1h.confirmar_ingreso_form1h`: autoriza exclusivamente la distribución
  del ingreso NUEVO según los detalles actuales bloqueados en la base de datos.
* `DivisionArticulo.save()`: conserva la validación de STOCK EXISTENTE mediante
  `validar_stock_existente()` bajo bloqueo del artículo. Las pantallas de asignación
  manual siguen usando sus cálculos de disponibilidad, reservas y compromisos.

`DivisionArticulo.clean()` conserva la validación estructural de cantidad positiva.
`full_clean()` conserva campos, estructura, unicidad y constraints. La regla contra
sobreasignar stock y la regla de no reducir lo asignado por debajo de las ubicaciones
se ejecutan en el guardado normal; no son límites para distribuir un ingreso nuevo.
No se añaden banderas al POST, parámetros skip_validation, variables globales,
cambios de campos ni migraciones.

El servicio es la única operación especializada: lee y bloquea el documento, comprueba
los ingresos Kardex y la distribución completa, calcula TODOS los incrementos desde
esas líneas y valida cada instancia con full_clean antes de escribirla. Solo dentro
de ese servicio se llama al guardado base del modelo para persistir los incrementos
respaldados por el documento; no se expone una función para guardar cantidades
arbitrarias sin validación. Las rutas de stock existente siguen usando save normal.

## Confirmación atómica

1. Bloquea cabecera; devuelve resultado idempotente si ya está confirmada y rechaza
   otros estados que no sean borrador.
2. Bloquea detalles por PK y artículos por PK. Cantidades y artículos proceden de la BD.
3. Valida filas completas, pertenencia al documento, números finitos positivos,
   divisiones activas (bloqueadas) y suma EXACTA por detalle. Un POST no puede cambiar
   la cantidad autorizada. La distribución previa de un borrador exige revisión.
4. Verifica un único ingreso Kardex correcto por detalle.
5. Agrupa todas las líneas por artículo/división y valida la asignación resultante
   una sola vez, sin consultar existencia ni compromisos históricos.
6. Confirma, registra DetalleFacturaDivision y añade únicamente esos incrementos,
   con creado_por/asignado_por. Todo está en transaction.atomic; la vista captura
   ValidationError después de salir de la transacción, nunca antes del rollback.

Los bloqueos por artículo son los mismos que usan las asignaciones manuales. No se
modifican reservas, consumos, ubicaciones, precios, salidas, permisos ni diseño Riho.
Si falla cualquier validación o escritura se revierte toda la operación nueva.

## Kardex e historia

`crear_kardex_ingreso` se ejecuta al crear DetalleFactura, incluso en borrador. El
servicio reutiliza ese registro y NO crea otro al confirmar. Debe existir exactamente
un ingreso vinculado al detalle, activo, de su mismo artículo y cantidad, sin vínculos
incompatibles a despacho, asignación o movimiento revertido.

Política explícita para un ingreso ausente: rechazar y pedir diagnóstico. No se
reconstruye automáticamente. Duplicados, cantidades diferentes y vínculos incorrectos
también se rechazan sin borrar ni corregir los movimientos.

La confirmación no consulta el stock histórico como límite, pero conserva las
asignaciones acumuladas y todos los contadores anteriores. Si había 620 asignadas,
añadir 1,200 deja 1,820 históricas. Si había consumo acreditado de 620, conserva ese
consumo y solo las 1,200 nuevas quedan pendientes. No se reinician ni liberan fuentes
agotadas. Una inconsistencia anterior queda visible en el diagnóstico y en las
restricciones de las operaciones normales de stock; no se repara ni se presume
consumida durante esta confirmación.

La vista de asignación directa conserva su validación de saldo; se corrigió además
su validación estructural de artículo ausente para devolver error de formulario,
en lugar de fallar al acceder a una relación inexistente cuando el selector rechaza
un artículo sin disponibilidad.

Los cálculos existentes de Kardex/Libro Mayor excluyen ingresos de facturas borrador
sin borrar registros. Los reportes valorizados muestran movimientos registrados;
pueden diferir del saldo físico ante despachos parciales aún sin Kardex. Esta
corrección no fabrica movimientos ni modifica la lógica de despachos para ocultarlo.

## Diagnóstico de producción

La base local NO contiene el artículo 675 ni los Kardex 682, 692 y 693. No se ha
verificado que 693 corresponda a #13 ni que 692 consuma la división 3. Para obtener
los vínculos y contadores sin modificar datos, con los settings reales del sitio:

```powershell
python manage.py auditar_articulo_1h --articulo 675 > diagnostico-675.json
```

Ejecutarlo desde una sesión nueva de manage.py, fuera de otra transacción. El comando
usa REPEATABLE READ / READ ONLY e incluye detalles y estados del 1H, Kardex con
fuentes, reversiones, asignaciones directas, divisiones/ubicaciones incluso inactivas,
distribuciones y despachos/solicitudes con orígenes. No incluye credenciales.

Comprobar a qué documento pertenece 693, que exista solo un ingreso correcto por
detalle, y vincular 692 a su requerimiento/solicitud y ubicación de división mediante
FKs, no por coincidencia de cantidades. Ante un dato ambiguo, conservar evidencia:
este cambio no repara históricos. La falta de un consumo acreditado no se interpreta
como autorización para liberar el presupuesto histórico de una división.

## Validación

```text
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test almacen_app.test_confirmacion_existencias --noinput
python manage.py test almacen_app --noinput
```

Pruebas PostgreSQL: primer/segundo ingreso; historia consumida e inconsistente;
varias líneas del mismo artículo; varias divisiones; distribución incorrecta y POST
adulterado; cantidades no finitas y divisiones inactivas; doble confirmación; Kardex
preexistente, ausente, duplicado o con artículo/cantidad diferentes; rollback después
de escribir una distribución; conservación de reservas y consumos; asignaciones
normales directas y de división; ubicaciones históricas inactivas; reportes y auditoría.

Las pruebas concurrentes usan conexiones independientes y una barrera: mismo documento,
dos documentos del mismo artículo, sobreasignaciones normales y confirmación junto
con la vista real de asignación manual de stock. También se prueba que completar
un parcial por la vista real no descuente dos veces la salida.

Resultado local con PostgreSQL: 109 pruebas ejecutadas, 100 correctas; las 24 de
confirmación pasaron. check y makemigrations --check --dry-run completaron sin
cambios de esquema.

Se conservan los nueve casos problemáticos previos: tres de Kardex con facturas
borrador/movimientos duplicados en fixtures y seis que recrean el grupo Gestor ya
creado por migración. No se alteran esas pruebas para hacerlas pasar. check conserva
las advertencias previas de namespace almacen duplicado y ForeignKey único.

## Despliegue IIS

1. Guardar el respaldo y diagnóstico habituales. Desplegar JUNTOS models.py,
   views.py y el NUEVO confirmacion_1h.py, además de esta documentación y las pruebas.
   Si se parte de una versión anterior al cambio precedente, desplegar también
   disponibilidad.py, form.py y el comando de auditoría de esa versión. Conservar
   settings y conexiones productivas; no ejecutar scripts cloud en producción.
2. Con Python y venv reales del sitio ejecutar check y makemigrations --check --dry-run.
   No hay migración nueva, cambio de dependencias ni necesidad de collectstatic.
3. Ejecutar pruebas contra una base de PRUEBAS autorizada, no usar registros
   productivos como fixtures.
4. Reciclar solo el Application Pool de la aplicación para no mezclar versiones.
5. Verificar que el ingreso de cada detalle del #13 esté vinculado y sea único.
   Desde la pantalla distribuir exactamente las 1,200 del documento y confirmar.
   No insertar otro ingreso si 693 ya corresponde a ese detalle.
6. Verificar estado, auditoría, distribución 1,200, acumulado histórico incrementado
   exactamente en 1,200, un único ingreso Kardex y reservas/consumos intactos.
   Repetir confirmación no debe añadir nada. Comprobar también que las asignaciones
   manuales siguen permitiendo saldo existente y rechazando excesos/reservas.

No se ha desplegado en IIS ni confirmado documentos productivos desde este entorno.
