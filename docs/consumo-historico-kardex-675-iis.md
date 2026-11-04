# Consumo histórico del Kardex no reconocido en la división

## Corrección respecto de las indicaciones anteriores

El reporte completo de IIS demuestra que las 620 ya fueron despachadas. **Para este
caso no se deben desasignar ni liberar otra vez esas 620.** La indicación anterior
de que solo quedarían 580 disponibles se basaba en los totales y en el contador de
división en cero; no reconocía la relación histórica duplicada que ahora documenta
el reporte completo.

Las primeras pruebas reproducían 1,820/620/1,200 pero no la cronología ni el cruce
entre el ingreso original, la asignación directa y su copia en ubicación. La nueva
regresión reproduce esos enlaces y el segundo ingreso después de la salida.

## Evidencia entregada por el usuario

- Artículo código 675; PK 675 en IIS. El código no se usa como PK en la reparación.
- Ingreso 677 / Formulario 1H 6: 620 unidades.
- Distribución original 5: esas 620 ya estaban en división 3.
- Asignación directa 4: 620 al departamento 37.
- Ubicación 6 de asignación de división 393: otras 620 administrativas del mismo
  artículo y departamento, creadas antes de la salida.
- Solicitud/detalle 6: origen directo 4 y detalle de requerimiento 6.
- Requerimiento 867: detalle completamente despachado, cantidad 620.
- Kardex 692: SALIDA vigente de 620, enlazada al detalle 6, sin reversión.
- Ingreso posterior 687 / Formulario 1H 13: 1,200 nuevas unidades; distribución 23.

El Kardex contiene una única salida física de 620. La ubicación histórica conservaba
`cantidad_consumida=0`, mientras la fuente directa ya reconocía el despacho. Al
calcular la división únicamente con ese contador, las 620 seguían apareciendo como
compromiso futuro y la división mostraba 1,820 en vez de 1,200 vigentes.

## Reconocimiento conservador y trazable

`consumo_historico_division.py` reconoce una asignación espejo solo cuando prueba:

1. Mismo artículo y mismo departamento para ubicación, asignación directa y despacho.
2. Un único origen directo completo, enlazado al detalle despachado.
3. Una salida Kardex vigente, de la misma cantidad y artículo, con ese detalle como
   origen; no está revertida ni tiene un movimiento de reversión.
4. La asignación directa y la ubicación son anteriores a la salida. Una asignación
   nueva creada después del despacho no se consume con una salida antigua.
5. La división ya era propietaria del ingreso original: distribución confirmada
   exclusiva y completa, de la misma cantidad, anterior a la asignación directa.
6. No hay otro ingreso anterior que vuelva ambiguo el lote ni dos posibles ubicaciones
   o despachos entre los que hubiera que elegir arbitrariamente.
7. El contador de división y sus despachos posteriores permiten distinguir lo que
   ya estaba registrado de lo que faltaba, sin sumar un consumo dos veces.

No se emparejan artículos por tener saldo 620, no se descuentan todas las salidas de
todas las divisiones y no hay una excepción por código 675.

El cálculo distingue:

- **Consumo registrado:** valor original de la columna, que se conserva.
- **Consumo histórico reconocido:** salida real con enlaces verificables que faltaba
  reflejar en esa ubicación.
- **Consumo efectivo:** registrado más la parte reconocida que faltaba.
- **Consumo compartido:** la misma salida representada en dos asignaciones históricas;
  se cuenta una sola vez en el total global de consumos físicos.

Para los datos auditados, la ubicación conserva sus 620 asignadas y su contador
original cero, pero su consumo efectivo es 620 y su disponibilidad es cero. La
fuente directa histórica también permanece totalmente consumida; no se reactiva.
El resumen global muestra consumo 620, nunca 1,240.

El reconocimiento es de solo lectura. Al registrar la liberación se incluyen en
`LiberacionStockDivision.procedencias` los IDs del Kardex, detalle de requerimiento,
asignación directa, ubicación y distribución original utilizados. Ese enlace
verificado conserva su trazabilidad en las operaciones posteriores. Dos liberaciones
parciales no duplican el reconocimiento.

No se reinterpretan liberaciones antiguas sin esa evidencia guardada. Los casos
ambiguos conservan las validaciones y requieren su propio diagnóstico.

## Resultado esperado

| Concepto | Antes de liberar | Después de liberar 1,200 |
|---|---:|---:|
| Existencia física | 1,200 | 1,200 |
| Asignación histórica división | 1,820 | 1,820 |
| Consumo efectivo división | 620 | 620 |
| Consumo físico global | 620 | 620 |
| Liberado | 0 | 1,200 |
| Compromiso vigente división | 1,200 | 0 |
| Compromiso vigente directo histórico | 0 | 0 |
| Disponible general | 0 | **1,200** |

La corrección no libera automáticamente las 1,200 nuevas: estaban asignadas a la
división y sigue siendo necesaria la acción administrativa **Liberar stock** con
justificación. Después se pueden asignar directamente las 1,200 completas.

Las 620 ya despachadas no se pueden desasignar, reservar ni solicitar de nuevo.
Los ingresos posteriores y las cantidades nuevas de la ubicación se manejan aparte,
sin reactivar ni duplicar el consumo antiguo.

## Archivos y límites del cambio

- Nuevo `almacen_app/consumo_historico_division.py`: comprobación de enlaces y
  evidencias; reutiliza consultas solo durante una fase de lectura.
- `almacen_app/models.py`: propiedades de consumo efectivo y validación de capacidad;
  no se agregan ni alteran campos de base de datos.
- `almacen_app/disponibilidad.py`: fuentes, compromisos y total global con deduplicación
  del consumo histórico compartido.
- `almacen_app/liberacion_division.py`: consume el mismo reconocimiento y guarda su
  evidencia en la bitácora existente.
- `almacen_app/views.py`: desasignación respeta el consumo efectivo; lecturas de Stock
  y Divisiones son coherentes. Despachar adquiere primero los bloqueos de artículo,
  como liberar, para evitar una inversión de orden durante operaciones simultáneas.
- Resumen/API de departamento y su template: deduplican el total asignado y
  despachado compartido, conservando el desglose histórico por origen.
- Templates de detalle, control y modal de divisiones: muestran consumo efectivo y
  señalan el reconocimiento por Kardex.
- `auditar_articulo_1h.py`: añade `consumos_historicos_reconocidos` al informe de solo
  lectura y conserva los contadores originales en el detalle completo.
- Nuevas regresiones en `test_consumo_historico_division.py` y documentación actualizada.

No se escriben nuevos ingresos ni salidas, no se modifican precios, Formularios 1H,
Kardex, despachos, asignaciones históricas ni reservas para hacer que cuadren. Las
escrituras de la liberación siguen siendo únicamente su bitácora administrativa.
No hay migración nueva ni nuevas dependencias.

Las consultas reutilizadas no se conservan entre solicitudes o escrituras. Las
validaciones transaccionales posteriores a guardar vuelven a leer el estado nuevo.

## Validación

Los casos nuevos prueban el orden real 620 ingresadas → asignación directa y copia
en ubicación → salida 620 → nuevo ingreso 1,200, con PK de artículo 9876 y código
comercial 675. Se comprueban snapshots de todas las tablas históricas antes/después.

Además cubren: consumo ya registrado que no se duplica; dos liberaciones parciales;
ubicación nueva posterior a la salida; departamento incorrecto; salida ausente,
incompleta o revertida; ingreso original no exclusivo; procedencia ausente;
operaciones futuras; línea despachada de requerimiento parcialmente resuelto;
rollback; lectura sin caché obsoleta; y despacho/liberación concurrentes.

Chromium comprueba el modal con 620 ya despachadas reconocidas en Kardex, liberación
de 1,200, Stock con compromiso cero, búsqueda AJAX con disponibilidad 1,200, rechazo
de 1,201 y guardado directo de 1,200. El Kardex conserva su única salida histórica
y la ubicación sigue asignada con disponibilidad cero, sin cambiar su contador original.

Comandos desde `upcv_app`, en PostgreSQL temporal:

```powershell
python manage.py test almacen_app.test_consumo_historico_division --noinput
python manage.py test almacen_app --noinput
python manage.py check
python manage.py makemigrations --check --dry-run
```

## IIS

Desplegar juntos los archivos Python, incluido el módulo nuevo, y los templates.
Desde el venv real de IIS, después de actualizar el repositorio:

```powershell
python manage.py check
python manage.py collectstatic --noinput
```

Reciclar AppAlmacen y comprobar en una consola del mismo sitio:

```powershell
python manage.py auditar_articulo_1h --codigo 675 --resumen
```

Debe mostrar una evidencia que vincula ubicación 6, asignación directa 4, salida 692
y distribución 5; consumo global 620; consumo efectivo de división 620 y compromiso
1,200. El contador original de ubicación cero en el reporte completo se conserva
para auditoría y no se corrige por SQL.

Después ejecutar **Liberar stock 1,200**, comprobar su registro y verificar compromiso
vigente cero y disponible general 1,200. **No desasignar ni liberar las 620 antiguas**.
No se ejecutó ninguna reparación de datos sobre la base productiva desde esta tarea.


Resultado final: 15 pruebas nuevas y el flujo Chromium aprobados. Suite completa:
174 ejecutadas, 164 aprobadas y los mismos 3 fallos / 7 errores previos de PDF,
Kardex y fixtures de reversiones, comparados por nombre. No se omitieron pruebas.
`check` conserva dos advertencias anteriores; no hay migraciones pendientes.
