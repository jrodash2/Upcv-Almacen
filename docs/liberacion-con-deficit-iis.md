# Liberación bloqueada por un exceso global previo: caso IIS 675

## Datos comprobados

El usuario ejecutó la auditoría de solo lectura en IIS. Para el artículo de código
675 (PK 675 en ese servidor), asignación 393 / división 3, informó:

| Dato | Cantidad |
|---|---:|
| Ingresado | 1,820 |
| Existencia física | 1,200 |
| Asignado directo histórico | 620 |
| Consumido directo | 620 |
| Compromiso directo vigente | 0 |
| Asignado a división | 1,820 |
| Distribuido a ubicaciones | 620 |
| Consumido en ubicaciones de división | 0 |
| Reservado | 0 |
| Liberado de división | 0 |
| Compromiso de división | 1,820 |
| Saldo matemático general | −620 |

`liberaciones_division` estaba vacío. Por tanto, esa base no contenía una liberación
confirmada. Las 620 consumidas corresponden al origen directo; no se trasladan
artificialmente al contador de consumo de la división. Las otras 620 distribuidas
siguen siendo un compromiso de ubicación según los registros auditados.

Se reprodujeron exactamente esos saldos en PostgreSQL temporal. También se comprobó
que **Desasignar de ubicación** devuelve la cobertura a la división y no crea una
liberación general, aunque la operación termine correctamente. El mensaje de éxito
referido por el usuario no demostraba un registro en la bitácora.

## Causa y reparación

Había dos controles incompatibles con este escenario:

1. `estado_liberacion` rechazaba toda revisión global, incluido un exceso numérico
   conocido de compromisos. Eso impedía reducir un compromiso no distribuido.
2. La comprobación posterior exigía que el saldo asignable publicado aumentase en
   toda la cantidad liberada. Si se parte de −620, liberar 500 lleva a −120 y el
   saldo asignable continúa en cero: la operación redujo el déficit correctamente,
   pero esa comprobación la revertía.

Ahora se distingue la revisión de **orígenes/reservas/consumos sin cobertura** del
**exceso global numérico**. La primera sigue bloqueando. El segundo genera una
advertencia y permite liberar expresamente la parte no distribuida, limitada a la
existencia física positiva de la operación.

Bajo los mismos bloqueos se exige:

- Existencia física posterior = existencia física anterior.
- Compromisos posteriores = compromisos anteriores − cantidad liberada.
- Saldo matemático posterior = saldo matemático anterior + cantidad liberada.
- Ninguna inconsistencia de orígenes después de guardar.

La asignación directa sigue usando el saldo autorizado por los controles normales;
no se permite asignar un saldo negativo ni se ignoran reservas. No cambió la fórmula
de stock ni se agregó una excepción por código 675. No hay actualización automática
de asignaciones históricas, ubicaciones, Kardex o documentos 1H.

El modal muestra el exceso previo y una estimación del disponible general para la
cantidad escrita. La estimación es informativa; el servidor revalida al confirmar.
El mensaje de éxito muestra el saldo general realmente disponible y el compromiso
que permanece en divisiones.

## Resultado correcto para los datos auditados

Al registrar **Liberar stock = 1,200** contra la asignación 393:

| Dato | Después |
|---|---:|
| Existencia física | 1,200, sin cambios |
| Liberaciones registradas | 1,200 |
| Compromiso de división | 620 |
| Compromiso directo vigente | 0 |
| Disponible para nueva asignación directa | **580** |

No pueden ofrecerse las 1,200 completas mientras las 620 de ubicación sigan
comprometidas. El saldo inicial era −620; al sumar la reducción de 1,200 queda 580.

Una liberación parcial de 500 reduce el déficit a −120 y registra el evento, pero
no habilita asignación. Liberar luego las otras 700 deja los mismos 580 disponibles.
No se generan unidades adicionales.

Si el Administrador desea retirar **también** las 620 de la ubicación y confirma
que ya no deben permanecer asignadas, debe ejecutar operaciones explícitas:

1. Desasignar esas 620 de la ubicación mediante la acción existente. El sistema
   vuelve a comprobar reservas/consumos; si ya tienen compromisos, debe rechazarlas.
2. Liberar el remanente de 620 de la división mediante **Liberar stock**.

En ese caso el compromiso de división queda en cero y, si no se hicieron otras
asignaciones, el disponible general llega a 1,200. No se marcan las 620 como
consumidas ni se borran movimientos. La asignación acumulada de división sigue
en 1,820 y los dos eventos de liberación documentan la reducción de sus derechos
administrativos, incluido el exceso previo; no son ingresos físicos. Este flujo
se probó, pero no se ejecutó sobre la base productiva del usuario.

## Archivos

- `almacen_app/disponibilidad.py`: expone si hay revisión de orígenes, sin cambiar
  el saldo ni sus condiciones para nuevas asignaciones.
- `almacen_app/liberacion_division.py`: elegibilidad local, advertencia, límite
  físico e invariantes correctos para liberar cuando existe déficit previo.
- `almacen_app/views.py`: éxito con saldo real y advertencia si aún hay déficit.
- `almacen_app/templates/almacen/divisiones/_liberar_stock.html`: advertencia y
  vista previa del efecto sobre la disponibilidad general.
- `almacen_app/templates/almacen/divisiones/detail.html`: advertencia y versión
  del script; elimina el prefijo fijo “Ubicación duplicada” de alertas ajenas a eso.
- `almacen_app/static/almacen_app/js/liberacion_division.js`: estimación informativa.
- `almacen_app/test_liberacion_deficit.py`: regresiones con los datos de IIS.
- `almacen_app/test_liberacion_division.py`: cambia el caso de exceso global para
  comprobar la reducción explícita conservando los otros compromisos. Las pruebas
  de consumos duplicados/orígenes inciertos siguen exigiendo bloqueo.
- `docs/liberacion-stock-divisiones-iis.md` y este documento: reglas actualizadas.

## Validación y despliegue

Desde `upcv_app`, con PostgreSQL de pruebas:

```powershell
python manage.py test almacen_app.test_liberacion_deficit almacen_app.test_liberacion_division --noinput
python manage.py test almacen_app --noinput
python manage.py check
python manage.py makemigrations --check --dry-run
```

Las pruebas reproducen el defecto anterior y comprueban: liberación de 1,200 con
580 disponibles; rechazo de una asignación directa de 581 y guardado de 580;
liberaciones parciales que aún no cubren el déficit; límite físico; protección de
las 620 de ubicación; solicitudes sin origen que siguen bloqueando; mensaje con
saldo real; concurrencia y el flujo explícito para retirar el remanente de ubicación.
Se conservan snapshots de Kardex, ingresos y asignaciones originales.

Chromium verificó el botón habilitado con advertencia, el modal y su estimación,
el POST de 1,200, Stock, el JSON y el desglose de Asignación Directa, el rechazo de
581 y el guardado de 580. Kardex y las 620 de ubicación permanecieron intactos.

No hay modelos ni migraciones nuevos. En IIS, después de desplegar esta versión:

```powershell
python manage.py check
python manage.py collectstatic --noinput
```

Reciclar AppAlmacen, recargar el navegador y volver a consultar:

```powershell
python manage.py auditar_articulo_1h --codigo 675 --resumen
```

Si sigue indicando cero liberaciones, la operación aún no está registrada. Usar
**Divisiones → Detalle de División → Liberar stock**, con justificación, y comprobar
su fila en Historial de Liberaciones y los saldos indicados arriba. No usar ajustes
SQL ni inventar ingresos para habilitar el botón. El JavaScript del modal se sirve
como `liberacion_division.js?v=20261104.2`.


Resultado final: las nueve pruebas nuevas y el flujo Chromium aprobaron. La suite
completa ejecutó 159 pruebas: 149 aprobadas y los mismos 3 fallos / 7 errores previos
de PDF, Kardex y fixtures de reversiones, comparados por nombre de prueba. No hubo
omisiones ni se cambiaron esas pruebas previas para ocultar sus resultados.
`check` conserva las dos advertencias existentes; no hay migraciones pendientes y
el JavaScript recolectado coincide con la fuente. Los cambios se verificaron en
la nube con datos aislados; requieren desplegarse en IIS y ejecutar allí la
liberación administrativa explícita para modificar ese inventario.
