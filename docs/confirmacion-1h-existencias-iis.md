# Confirmación de 1H después de consumos históricos

## Evidencia y alcance del diagnóstico

La base de desarrollo no contiene el artículo 675 ni los Kardex 682, 692 y 693.
No se consultó producción y no se modificaron sus datos. La secuencia comunicada
(620 ingreso, 620 salida, 1,200 ingreso) por sí sola NO demuestra qué origen
consumió las 620 ni qué documento originó el movimiento 693.

Antes de confirmar el #13 en producción, con sus settings reales:

```powershell
python manage.py auditar_articulo_1h --articulo 675 > diagnostico-675.json
```

El comando es de solo lectura, exige una transacción nueva y usa un snapshot
REPEATABLE READ / READ ONLY de PostgreSQL. Incluye facturas y estados, Kardex con
vínculos a factura/despacho, reversiones, asignaciones directas, divisiones y
ubicaciones incluso inactivas, distribución de factura, despachos y solicitudes
con sus orígenes. No incluye credenciales. Ejecutarlo desde manage.py, fuera de
una transacción ya abierta.

Revisar explícitamente:

* Que 693.fuente_factura apunte a un detalle de #13, con cantidad 1,200.
* Que 682 apunte al detalle de #6 confirmado, con cantidad 620.
* Que 692.fuente_despacho apunte al requerimiento efectivamente despachado y que
  la solicitud de origen enlace ese detalle con DivisionArticuloUbicacion de
  división 3. Comparar cantidad_despachada, cantidad_consumida y reversiones.
* Que no existan reservas o consumos sin documento, ni ingresos duplicados,
  reversiones sin vínculo o compromisos superiores al físico.

Si no hay vínculo inequívoco, no atribuir una salida a una división por coincidir
el artículo o la cantidad. Se conserva el compromiso y se informa la inconsistencia;
este cambio no reconcilia ni repara históricos. Para auditar reservas por departamento
se conserva también `auditar_disponibilidad --departamento ID --codigo CODIGO`.

## Causa y reglas de saldo

La señal crear_kardex_ingreso registra un movimiento cuando se crea DetalleFactura,
incluso en borrador. La existencia cuenta el detalle solo cuando se confirma. Por
eso puede existir un ingreso Kardex de 1,200 antes de confirmar: no debe crearse otro.
La confirmación verifica que exista exactamente un ingreso activo coincidente por
detalle; un faltante, duplicado o cantidad diferente exige revisión.

DivisionArticulo.cantidad_asignada es acumulada. Compararla directamente con la
existencia actual descontaba las salidas físicas, pero seguía considerando las
mismas unidades consumidas como comprometidas.

Ahora `compromisos_articulo` calcula por división:

    compromiso vigente = asignación histórica - consumo registrado en ubicaciones

Las reservas son parte de ese compromiso, no otra resta del físico. Las ubicaciones
son un desglose de la asignación de división y no una segunda asignación global.
Las directas usan el cálculo existente `fuentes_departamento` para separar consumo,
reservas y legado; un origen ambiguo no libera presupuesto. Los orígenes inactivos
conservan sus compromisos e historia. Un contador inconsistente bloquea disponibilidad.

    libre para una nueva asignación = existencia física - compromisos vigentes

`DivisionArticulo.clean()` y `resumen_global_articulo()` comparten esta regla.
`full_clean()` sigue ejecutándose. No hay cambios de campos ni migraciones.
`disponible_division` resta la asignación histórica a ubicaciones (incluido consumo);
`disponible_para_solicitud` resta consumo y reservas. El saldo de cada ubicación
sigue siendo asignado - reservado - consumido. No se devuelve automáticamente lo
consumido a ninguna de estas fuentes.

La existencia física cuenta detalles confirmados + ingresos de reversión - salidas
Kardex - despachos aún no reflejados en Kardex. Esta última diferencia es necesaria
porque la señal solo registra una salida al completar el despacho: un parcial ya
consumido no debe financiar nuevas asignaciones. Se descuenta únicamente la parte
no contabilizada; al completarse, el Kardex reemplaza ese descuento sin duplicarlo.
No se cambian señales, cantidades despachadas ni movimientos históricos.

Stock administrador y pantallas/formulario de asignación directa usan el resumen
común; Mis Artículos, solicitudes y despachos conservan los cálculos por origen.
Kardex y Libro Mayor excluyen los ingresos de facturas en borrador/anuladas de sus
cálculos, conservando los registros en la base. No se cambian precios. Los reportes
valorizados siguen representando movimientos registrados: un despacho parcial aún
sin Kardex puede diferir de la existencia física. No se fabrican movimientos ni
costos para ocultar esa diferencia; una conciliación histórica de parciales es una
tarea separada. Las reversiones tampoco restauran contadores de origen automáticamente.

## Transacciones y trazabilidad

Confirmación mantiene bloqueo de cabecera y bloquea artículos en orden de PK antes
de leer/modificar asignaciones. Dos formularios del mismo artículo se serializan.
El alta/actualización validada de DivisionArticulo también bloquea el artículo.
La asignación manual a división y el formulario de asignación directa usan el mismo
bloqueo. Se conservan distribución exacta obligatoria, DetalleFacturaDivision,
asignado_por/creado_por, atomic y prevención de doble confirmación.

Un savepoint abarca estado confirmado, distribución y acumulación. Un ValidationError
revierte todo ese bloque y se informa en pantalla; no deja confirmaciones parciales.
Se rechazan filas incompletas, detalles ajenos y números no finitos. No se reinicia
cantidad_asignada, no se borran asignaciones ni se ejecutan reparaciones masivas.

## Pruebas

```text
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test almacen_app.test_confirmacion_existencias --noinput
python manage.py test almacen_app --noinput
```

17 pruebas nuevas con PostgreSQL: primer y segundo ingreso; doble confirmación;
620 consumidas y nuevo ingreso 1,200 con señal real; parcial y reservas protegidas, completado por la vista real sin doble descuento;
varias divisiones y distribución incorrecta; mezcla directa/división; consumo sin
origen acreditado; rollback en la segunda distribución; ingreso duplicado; reversión;
stock y selector directo; borrador excluido en Kardex/Libro Mayor; auditoría de solo
lectura; dos confirmaciones del mismo documento, dos documentos del mismo artículo
y dos sobreasignaciones simultáneas mediante conexiones independientes.

La suite conserva los nueve casos problemáticos conocidos: tres de Kardex usan
facturas borrador y movimientos duplicados en fixtures, seis recrean el grupo Gestor
ya creado por migración. La exclusión de borradores cambia los valores/forma del fallo
de esos tres casos; no se modificaron sus fixtures para ocultarlo. Se conservan las
advertencias por namespace almacen duplicado y ForeignKey único.

## Despliegue IIS

1. Seguir el respaldo y ventana de despliegue habituales. Guardar el diagnóstico
   previo del artículo 675 y revisar los vínculos anteriores antes de operar #13.
2. Desplegar juntos models.py (solo métodos), disponibilidad.py, views.py, form.py
   y management/commands/auditar_articulo_1h.py; conservar settings de producción.
   No hay migración nueva, cambios de dependencias ni de Riho/staticfiles.
3. Con el Python/venv real del sitio ejecutar check y makemigrations --check --dry-run.
   Ejecutar las pruebas contra una base de pruebas autorizada, nunca usar datos
   productivos como fixtures ni ejecutar scripts de desarrollo/cloud allí.
4. Reciclar únicamente el Application Pool de la aplicación para evitar workers
   mezclados. No se necesita collectstatic para este cambio.
5. Repetir diagnóstico. Solo si se acreditan las 620 consumidas de división 3 y
   los compromisos están conciliados, confirmar #13 desde su pantalla habitual.
   No insertar otro ingreso para compensar el 693 existente.
6. Verificar estado confirmado, distribución exacta 1,200, auditoría de usuario,
   un solo ingreso de 1,200 para el detalle y consumo histórico intacto. Si las
   premisas se cumplen, el acumulado asignado será 1,820, consumido 620 y compromiso
   vigente/físico 1,200 (menos reservas para disponibilidad solicitante).
   Revisar también stock, división, Mis Artículos, solicitud, Kardex y Libro Mayor.
   Ante discrepancias, conservar evidencia y detener la operación; no ajustar datos.

No se ha desplegado en IIS ni confirmado ningún documento de producción.
