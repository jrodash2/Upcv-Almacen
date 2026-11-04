# Liberación confirmada, pero disponibilidad cero

La captura de Asignación Directa muestra existencia física 1,200 y un bloqueo de
revisión histórica. Ese bloqueo no prueba que una liberación haya desaparecido:
la disponibilidad depende también de los compromisos directos, de otras divisiones
y de reservas/consumos sin cobertura verificable. No se debe quitar la validación
ni sustituir la disponibilidad por la existencia física.

## Corrección visual comprobada

La columna Departamento(s)/División(es) de Stock aún enumeraba las cantidades
acumuladas de `DivisionArticulo.cantidad_asignada`. Después de liberar, podía seguir
mostrando `División A (1,820)` como si fuera compromiso actual.

Ahora las asociaciones vigentes usan asignado − liberado − consumido, y el
histórico se muestra por separado. Una división totalmente liberada y consumida
ya no figura como compromiso vigente; sus registros históricos permanecen visibles.
Lo mismo distingue compromisos directos vigentes de asignaciones ya consumidas.

Asignación Directa muestra además:

- Liberado de divisiones.
- Compromiso vigente en divisiones.
- Compromiso vigente directo.
- Motivo concreto de un bloqueo de revisión, cuando el servidor lo proporciona.

El resumen conserva el saldo matemático sin asignar (`saldo_sin_asignar`) y el saldo
realmente autorizado (`disponible_para_division`). No son intercambiables: el segundo
permanece en cero si la cobertura de reservas o consumos requiere revisión.
No se cambiaron las fórmulas ni las condiciones que autorizan asignar.
La consulta AJAX de existencias incluye `Cache-Control: no-store` y el navegador
solicita datos sin reutilizar respuestas almacenadas. Esto evita saldos obsoletos;
no establece que la caché haya sido la causa del incidente productivo.

## Comprobación en el servidor real

El servicio de liberación verifica antes de confirmar que el disponible general
aumentó exactamente por la cantidad liberada. El mensaje de éxito por sí solo no
explica un resultado posterior distinto: hay que contrastar la bitácora con el
resumen realmente servido por IIS. No repetir la liberación para intentar corregirlo.

Con la misma sesión autorizada del sitio, consultar:

```text
/almacen/buscar-articulos/?q=675&asignacion_directa=1
```

Dentro del objeto de código **675** —sin confundir su PK interna— revisar:
`existencias.liberado_divisiones`, `comprometido_divisiones`, `comprometido_directo`,
`existencia_fisica`, `requiere_revision`, `motivos_revision` y
`disponible_para_division`.

Tras desplegar esta corrección, desde `upcv_app` y el venv real de IIS se puede
consultar directamente por código comercial:

```powershell
python manage.py auditar_articulo_1h --codigo 675 --resumen
```

El comando mantiene su transacción PostgreSQL REPEATABLE READ, READ ONLY.
También conserva el argumento anterior `--articulo PK_INTERNA` y el informe completo
cuando se omite `--resumen`. No imprime credenciales ni modifica registros.

- Si el resumen reconoce 1,200 liberadas y aún existen compromisos/revisión,
  identificar las asignaciones y reservas concretas; no suprimirlas automáticamente.
- Si la consulta del proceso de consola reconoce liberaciones distintas de la
  respuesta del sitio, comprobar versión desplegada, reciclado del Application Pool,
  configuración de conexión y caché del servidor. No concluir una causa sin comparar.
- Si no hay liberaciones registradas, contrastar el historial de la operación y la
  base utilizada. Desasignar de ubicación devuelve cobertura a su división, mientras
  que Liberar stock de división devuelve disponibilidad al almacén general.

La base disponible en la nube no contiene el artículo 675 de producción. El incidente
productivo queda pendiente de su respuesta JSON o auditoría; no se declara resuelto
el disponible cero de IIS solamente con estas correcciones de visualización.

## Archivos y validación

Cambios en `disponibilidad.py`, `views.py`, `auditar_articulo_1h.py`, los templates
`stock_formulario_1h.html` y `crear_asignacion_detalle.html`, y `asignacion_directa.js`.
Nuevas pruebas en `test_saldo_liberado.py` para liberación total/parcial, asociaciones
históricas/vigentes, motivo de bloqueo y auditoría por código de solo lectura.
No hay modelos ni migraciones nuevas, ni cambios de cantidades o movimientos.

Ejecutar desde `upcv_app` con PostgreSQL de pruebas:

```powershell
python manage.py test almacen_app.test_saldo_liberado almacen_app.test_liberacion_division --noinput
python manage.py test almacen_app --noinput
```

Se reproducen los saldos con fixtures aislados y se conserva el bloqueo ante
inconsistencias. Chromium comprueba el flujo liberación → Stock → Asignación,
incluido el desglose de 500 liberadas, 700 comprometidas en división y cero de
compromiso directo antes de la nueva asignación.

Para IIS: desplegar juntos Python, templates y JS; ejecutar `check` y
`collectstatic --noinput`; reciclar el Application Pool y recargar el navegador.
El script se referencia como `asignacion_directa.js?v=20261104.2`. No requiere una
nueva migración sobre el despliegue que ya tiene aplicada 0060.

Resultado de la validación: 150 pruebas ejecutadas, 140 aprobadas y los mismos
3 fallos / 7 errores anteriores de PDF, Kardex y fixtures de reversiones; las cuatro
pruebas nuevas aprobaron. El flujo Chromium con el nuevo desglose aprobó.
`check` conserva las dos advertencias previas, no hay migraciones pendientes y el
JavaScript recolectado coincide con la fuente. Esto valida la corrección local de
visualización y diagnóstico; la disponibilidad real de IIS sigue pendiente de
contrastar con los datos de ese servidor.
