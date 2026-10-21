# Disponibilidad por origen: solicitudes, asignaciones y reservas

## Causas verificadas en el código

1. `crear_solicitud_requerimiento` sumaba Directo y División para validar el artículo,
   pero después buscaba una división con saldo para toda la cantidad. Si existía
   una asignación de división agotada, rechazaba el detalle aunque Directo tuviera
   existencias. El origen mostrado en pantalla no determinaba el origen guardado.
2. Crear Solicitud calculaba Directo como asignado menos **todos** los despachos del
   departamento. El resumen del Gestor primero restaba el consumo registrado en
   divisiones del total despachado y solo atribuía el resto a Directo.
3. Las solicitudes directas pendientes no tenían asignación identificada ni una
   reserva reflejada en el resumen. Al convertir se podía comprobar contra otro
   saldo y no había vínculo entre el detalle de solicitud y el de requerimiento.
4. Al despachar se elegía el primer detalle de solicitud por artículo, ignorando
   que varias filas del mismo artículo podían tener fuentes distintas. Rechazo y
   anulación tampoco serializaban todos los cambios con nuevas reservas.

El caso 10 frente a 9 se reproduce con Directo=10 y un despacho de división=1:
la fórmula antigua mostraba 9 en Crear Solicitud y 10 en el detalle. Las pruebas
incluyen esa situación. **No se han consultado los registros de producción**;
no se afirma que las 9 unidades reales sean incorrectas sin su auditoría.

## Selección y trazabilidad

Cada fila de Crear Solicitud elige artículo y **Origen / asignación**. Se permiten
filas repetidas del mismo artículo con diferentes fuentes. Para pedir 8 con Directo=6
más División=4, el usuario declara 6 en Directo y 2 en División. No hay distribución
oculta ni cambio automático del origen elegido. Si solo existe una fuente, se
preselecciona; con varias fuentes se exige elegir. Las cantidades asignadas,
reservadas, consumidas y disponibles de la fila corresponden a la fuente elegida.

El identificador de origen es `D:<pk de AsignacionDetalleFactura>` o
`V:<pk de DivisionArticuloUbicacion>`. No es el ID del artículo. Se verifica que
pertenece al departamento autorizado, al artículo y, para divisiones, a una
membresía activa. La categoría y el artículo activo se validan en el formulario.

La migración aditiva `0059_fuentes_solicitud` añade al detalle de solicitud:

- `asignacion_directa`, nullable, protegida frente a borrado.
- `detalle_requerimiento`, vínculo uno a uno nullable para conservar la fuente al convertir.
- Una restricción que impide tener fuente directa y división simultáneamente.

La relación de división existente se conserva. La migración no contiene operaciones
de datos: no completa fuentes históricas, no cambia cantidades ni elimina reservas.
Estas referencias eran necesarias porque el modelo anterior no podía identificar
una asignación directa concreta ni el despacho de cada fila de un artículo repetido.

## Cálculo común y ciclo de vida

`almacen_app/disponibilidad.py` centraliza los cálculos:

- `fuentes_departamento`: asignado, reservado, consumido y disponible por asignación.
- `totales_departamento`: suma las disponibilidades de fuentes autorizadas.
- `resumen_global_articulo`: distingue ingreso, asignación directa, asignación a
  divisiones y presupuesto todavía sin asignar.
- `bloquear_departamento` y `validar_y_reservar`: revalidación y reserva serializadas.
- `liberar_reservas_division`: liberación de la reserva restante al pasar a estado terminal.

Disponible por fuente = asignado − reserva activa − consumido. Un saldo negativo o
un déficit histórico se marca para revisión y no habilita nuevas reservas.

**Directo:** la reserva se deriva de los detalles de solicitudes pendientes y de
los restantes de solicitudes convertidas con requerimiento activo. Un requerimiento
manual sin solicitud también reserva su cantidad pendiente, una sola vez. El consumo
nuevo se atribuye a su asignación mediante el vínculo al detalle despachado.

**División:** se mantienen sus contadores existentes `cantidad_reservada` y
`cantidad_consumida`. Crear reserva solamente esa ubicación; convertir conserva la
misma reserva; despachar mueve solo el incremento de `cantidad_despachada` de
reservado a consumido. Repetir una cantidad acumulada ya despachada no vuelve a mover
unidades. Rechazo o anulación liberan únicamente la parte pendiente y una sola vez.

Los consumos y reservas directos anteriores sin asignación identificada se presentan
con una imputación de lectura estable por PK de asignación. El consumo histórico
directo parte de despachado total menos consumo de división registrado, sin descontar
la misma operación dos veces. No se escribe esa imputación en los históricos. Si la
información no alcanza para cubrir obligaciones, el saldo queda para revisión.
Los requerimientos históricos con múltiples fuentes indistinguibles no se despachan
eligiendo arbitrariamente la primera: se solicita revisión administrativa.

Las operaciones que crean/liberan reservas, convierten, despachan, editan reservas
directas manuales, transfieren o desasignan usan transacciones. Para nuevas reservas
se bloquea primero departamento, después asignaciones directas por PK y ubicaciones
por PK, y después las cabeceras correspondientes. `FOR UPDATE` se aplica a tablas
base separadas, sin joins opcionales. También se valida el total de filas de una
misma fuente bajo bloqueo. Dos reservas concurrentes no pueden gastar el mismo saldo.

Los detalles ya convertidos conservan el desglose original: el editor genérico no
puede cambiar o eliminar silenciosamente su fuente reservada. Para cambiar ese
desglose, anular y crear una nueva solicitud conforme al flujo actual. No cambian los
roles o permisos. Las transferencias directas no pueden tomar unidades reservadas o
consumidas.

## Pantallas y alcance global

Crear Solicitud, la API de artículos, Mis Artículos Asignados y Detalle de Asignaciones
consultan el mismo servicio. Mis Artículos ahora incluye Directo y División. Los
detalles de solicitudes y requerimientos muestran la fuente y asignación conservadas.
Las vistas de divisiones siguen usando sus contadores existentes; se aclara que el
saldo del padre disponible para distribuir a ubicaciones es distinto del saldo
solicitable ya asignado a cada ubicación.

El stock administrativo incluye reservas y consumos de fuentes directas y divisiones.
Su **disponible sin asignar** es ingreso confirmado menos asignado directamente menos
asignado al padre de división. La distribución a ubicaciones se informa aparte:
**no se añade otra vez a lo ingresado ni a lo asignado global**. No se descuenta de
nuevo la reserva de un presupuesto que ya está asignado.

No se cambiaron costos, correlativos, Formulario 1H, señales de Kardex ni Reversiones.
Se conserva el comportamiento previo de Kardex que registra la salida al completar
el detalle; los despachos parciales se reflejan en `cantidad_despachada` y en los
saldos de asignaciones, sin inventar movimientos históricos. Por ello no se afirma
haber corregido el registro físico de parciales en Kardex, que requeriría un cambio
específico de ese módulo.

## Auditoría de producción sin modificar datos

Después de desplegar y migrar, con el Python/settings reales del sitio:

```powershell
python manage.py auditar_disponibilidad --departamento ID_REAL --codigo 1
```

Usar el PK real de SECCIÓN DE ALMACÉN E INVENTARIOS, no el ID del artículo. El comando
muestra fuentes, documentos, cantidades despachadas, estados, referencias y contadores
incluyendo divisiones inactivas. Para cada división compara el contador reservado
con lo documentado y enumera detalles convertidos sin vínculo inequívoco.

`diferencia_por_investigar` no demuestra por sí sola una reserva huérfana: puede haber
históricos sin vínculo. Revisar los documentos indicados, estado de requerimientos,
consumos y movimientos originales antes de proponer cualquier ajuste administrativo.
No borrar sesiones, cachés, detalles o reservas para forzar coincidencias. El comando
es de lectura y no hace reparaciones. Si las 9 unidades corresponden a una reserva
directa legítima de 1, esa reserva aparecerá también en las demás vistas.

## Validación

En desarrollo, con PostgreSQL:

```text
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test almacen_app.test_disponibilidad almacen_app.test_solicitud_filas --noinput
python manage.py test almacen_app --noinput
```

Las 41 pruebas específicas pasan. Incluyen los casos A–I, fuentes agotadas y mixtas,
permisos de fuente/ubicación, artículo ajeno, filas eliminadas, reservas sucesivas,
rollback, rechazo repetido, conversión repetida, anulación, despacho completo/parcial,
reportes coherentes, auditoría de lectura y competencia real entre dos transacciones
PostgreSQL, tanto en asignación directa como en división.

En Chromium con servidor Django y PostgreSQL reales de pruebas pasaron la selección
explícita de fuentes, el desglose 6 Directo + 2 División, la actualización de saldos,
el guardado, las validaciones visibles y la eliminación sin reservas residuales.
También se repitieron los casos de la corrección anterior: doce filas paginadas,
bloqueo del doble envío, reintentos, 403/500 simulados, falta de DataTables y recarga.

La suite completa conserva nueve problemas anteriores: tres fallos de los tests de
Kardex por movimientos duplicados en sus fixtures y seis errores de fixtures de
Reversiones al recrear el grupo Gestor que ya existe por migración. No se alteraron
esas pruebas ni los módulos ajenos para convertirlos en aprobados. `check` mantiene
las advertencias previas por namespace `almacen` duplicado y ForeignKey único.

## Archivos y despliegue IIS

Cambios principales: `disponibilidad.py`, `form.py`, `models.py`, las funciones de
solicitudes/asignaciones de `views.py`, la migración `0059`, el comando de auditoría,
`test_disponibilidad.py` y los templates de creación, detalle de solicitud,
detalle de requerimiento, Mis Artículos, Mis Divisiones y stock administrativo.

1. Desplegar todos los archivos de esta revisión juntos, con el procedimiento del
   sitio bajo `C:\Users\Administrador\Documents\AppAlmacen\upcv_app`.
   Evitar que los workers atiendan solicitudes mezclando código antiguo y nuevo.
2. Con el entorno virtual y settings del sitio, revisar y aplicar:

   ```powershell
   python manage.py migrate --plan
   python manage.py migrate --noinput
   python manage.py check
   ```

3. Reciclar solo el Application Pool de esta aplicación. **No hace falta
   `collectstatic` para este cambio**: el JavaScript modificado sigue dentro del
   template; no se cambiaron archivos estáticos. Si el despliegue incluye otros
   cambios de estáticos, ejecutar `collectstatic --noinput` según su procedimiento.
4. Recargar sin caché, comprobar el selector Origen / asignación y el POST con
   `detalles-N-origen`. El éxito JSON devuelve 201; una validación, 400 con artículo,
   fuente y saldo. Revisar logs IIS/Django si aparece 403 o 500.
5. Ejecutar la auditoría del artículo y departamento reales y probar fuentes directas,
   divisiones y combinación con datos autorizados. Comparar fuentes y reservas con
   las demás pantallas en el mismo momento de consulta.

No se ha accedido al servidor IIS ni se han modificado sus registros. La publicación,
la migración y la comprobación con los documentos reales permanecen pendientes allí.
