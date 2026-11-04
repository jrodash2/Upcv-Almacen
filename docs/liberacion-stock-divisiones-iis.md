# Liberar stock de una división

## Diagnóstico y significado de las cantidades

`DivisionArticulo.cantidad_asignada` es una cantidad acumulada: puede incluir
asignaciones manuales y distribuciones de varios Formularios 1H, incluso unidades
ya consumidas. `DetalleFacturaDivision` conserva la distribución original de cada
detalle 1H. `DivisionArticuloUbicacion.cantidad_asignada` también conserva cobertura
para las cantidades consumidas y reservadas de esa ubicación.

Sumar asignaciones directas históricas y asignaciones acumuladas a divisiones no
indica por sí solo cuántas unidades siguen comprometidas. Por eso Stock podía
mostrar 2,440 asignadas históricamente aunque la existencia física fuera 1,200.
La disponibilidad general ya utilizaba compromisos netos; faltaba una operación
administrativa auditable para devolver a disponibilidad el remanente de división.
Las pantallas ahora distinguen histórico, liberado y compromiso vigente.

El número histórico 620 directo no se elimina ni se presume consumido. Hay que
verificar qué despachos lo consumieron y desde qué origen. Si el mismo despacho
aparece consumido tanto en directo como en división, o si subsiste un compromiso
directo que hace exceder la existencia física, la liberación se bloquea y explica
el motivo. Tampoco se liberan cantidades cuando hay solicitudes/requerimientos
vigentes sin origen verificable, reservas sin contadores suficientes o consumos
sin despachos que los respalden. No se reparan automáticamente esas situaciones.

## Fórmula e invariantes

Para una asignación de división:

- **A:** asignación acumulada original, que no se sobrescribe.
- **L:** suma de las liberaciones auditadas contra esa asignación.
- **U:** suma de las asignaciones a ubicaciones, incluidas las inactivas.
- **C:** consumo de esas ubicaciones, ya incluido en U.
- **R:** reservas de esas ubicaciones, incluidas en U − C.

Presupuesto después de liberaciones = **A − L**.

Compromiso vigente de división = **A − L − C**.

Compromiso que sigue cubriendo ubicaciones = **U − C**.

Máximo liberable = **(A − L − C) − (U − C) = A − L − U**.

Si el resultado es negativo o los registros presentan inconsistencias, el máximo
operable es cero y se muestra la razón. C y R no se restan otra vez: ya están
protegidos por U. Una reserva o consumo en una ubicación no impide liberar el
remanente independiente de la división, pero su cobertura queda íntegra.

La existencia física sigue proviniendo de `existencia_general_articulo` sin cambios
de fórmula. La disponibilidad general sigue siendo existencia física menos los
compromisos vigentes directos y de todas las divisiones, ahora descontando L.
Se mantienen los campos históricos del resumen y se agregan campos explícitos de
liberación y compromiso neto para conservar compatibilidad.

Con A=100, U=30, C=0 y L=0 se pueden liberar 70, nunca 71.
Si las 30 unidades ya fueron consumidas, C=30: el compromiso de división es 70,
el compromiso restante de ubicaciones es cero y se pueden liberar esas 70.
El consumo no genera de nuevo 30 unidades físicas.

En el escenario 675, sin otros compromisos y con despachos verificados:

| Operación | Histórico A | Consumido C | Liberado L | Compromiso división | Físico | General disponible |
|---|---:|---:|---:|---:|---:|---:|
| Inicial | 1,820 | 620 | 0 | 1,200 | 1,200 | 0 |
| Liberar 500 | 1,820 | 620 | 500 | 700 | 1,200 | 500 |
| Liberar otros 700 | 1,820 | 620 | 1,200 | 0 | 1,200 | 1,200 |

Si tras liberar 500 se asignan 300 a otra división, A mantiene compromiso 700,
B tiene compromiso 300 y quedan 200 generales; la existencia física sigue en
1,200. Asignar las unidades liberadas directamente utiliza el formulario existente,
sin nuevo ingreso ni nuevo Formulario 1H.

## Operación, trazabilidad y concurrencia

Ruta: **Divisiones → Detalle de División → Artículos asignados → Liberar stock**.
El botón/modal solo está disponible para Administrador (y superusuario conforme al
decorador existente). Los demás permisos no se amplían. La petición es POST con
CSRF y exige cantidad positiva de hasta dos decimales, justificación no vacía y UUID
de operación. El modal solicita confirmación y bloquea el doble envío en navegador.
Un reintento idéntico con el mismo UUID devuelve el registro existente; cambiar
su cantidad, asignación, usuario o justificación no reutiliza ese identificador.

No había una bitácora equivalente: `HistorialTransferencia` representa movimientos
entre departamentos y Kardex representa movimientos físicos. Se añadió
`LiberacionStockDivision`, con relaciones PROTECT, usuario, fecha, tipo parcial/total,
saldos liberables antes/después y procedencias originales de `DetalleFacturaDivision`.
Las procedencias son un snapshot de las distribuciones que componen la asignación;
no se inventa una atribución física por lote cuando la asignación acumulaba varias
fuentes o incluía asignaciones manuales. La cobertura y el límite se controlan por
asignación original, mediante el acumulado L y el bloqueo transaccional.
“Total” significa todo el máximo liberable, no eliminar la asignación histórica.

La bitácora no tiene acciones de edición ni borrado en la vista y el modelo rechaza
el guardado de registros existentes y su eliminación individual. La liberación no
actualiza A, U, reservas, consumos, documentos 1H, asignaciones directas ni Kardex.
No genera INGRESO ni SALIDA, ni modifica costos.

La operación usa `transaction.atomic` y bloqueos de tablas base en orden:
artículo → departamentos por PK → asignación de división → ubicaciones por PK.
El cálculo se repite bajo bloqueo. Autoasignar toma primero el artículo para
serializarse con la liberación; solicitudes/reservas conservan su orden de bloqueo
departamento → ubicaciones. No hay FOR UPDATE sobre LEFT OUTER JOIN.
Antes de confirmar se verifica que la existencia física no cambió y que la
disponibilidad general aumentó exactamente en la cantidad liberada; un fallo
revierte también la bitácora.

## Archivos modificados

- `upcv_app/almacen_app/models.py`: bitácora y propiedades de saldo; capacidad de
  ubicaciones y validación de divisiones consideran liberaciones anteriores.
- `upcv_app/almacen_app/migrations/0060_liberacion_stock_division.py`: creación
  aditiva de tabla, claves protegidas, UUID único y constraints de saldos.
- `upcv_app/almacen_app/liberacion_division.py`: diagnóstico y servicio transaccional.
- `upcv_app/almacen_app/disponibilidad.py`: integración de L y desglose de compromisos.
- `upcv_app/almacen_app/form.py`: validación de cantidad, justificación e identificador.
- `upcv_app/almacen_app/views.py`: POST protegido, contexto de detalle, Stock/AJAX,
  totales del control general y bloqueo de autoasignación compatible con liberación.
- `upcv_app/almacen_app/urls.py`: ruta de liberación.
- `upcv_app/almacen_app/templates/almacen/divisiones/detail.html`: acción y bitácora.
- `upcv_app/almacen_app/templates/almacen/divisiones/_liberar_stock.html`: modal Riho.
- `upcv_app/almacen_app/templates/almacen/divisiones/control.html`: totales por
  división y compromisos por artículo, sin ocultar historial de asignaciones inactivas.
- `upcv_app/almacen_app/templates/almacen/divisiones/mis_divisiones.html`: identificación
  del histórico y liberado junto a la disponibilidad ya ajustada.
- `upcv_app/almacen_app/templates/almacen/stock_formulario_1h.html`: físico, histórico,
  liberado y compromisos vigentes diferenciados sin cambiar el número de columnas.
- `upcv_app/almacen_app/static/almacen_app/js/liberacion_division.js`: confirmación
  y protección del envío del modal.
- `upcv_app/almacen_app/management/commands/auditar_articulo_1h.py`: añade liberaciones
  y diagnóstico por división a su transacción existente de solo lectura.
- `upcv_app/almacen_app/test_liberacion_division.py`: 26 pruebas específicas.
- `docs/liberacion-stock-divisiones-iis.md`: este documento.

## Validación realizada

Django 5.1.4 y PostgreSQL 17, con señales reales y bases temporales:

```powershell
python manage.py test almacen_app.test_liberacion_division --noinput
python manage.py test almacen_app --noinput
python manage.py check
python manage.py makemigrations --check --dry-run
```

Las 26 pruebas específicas aprobaron. Cubren liberación total/parcial/sucesiva;
620 consumidas y 1,200 liberables; una o varias ubicaciones incluidas inactivas;
reservas y despachos parciales; cero disponibilidad; cantidades inválidas/excesivas;
compromisos directos vigentes y consumos duplicados; reintentos con UUID; dos
administradores liberando a la vez; dos envíos simultáneos con el mismo UUID;
liberación contra autoasignación; asignación directa y a otra división posterior;
nuevo ingreso 1H después de liberar; capacidad de ubicación ajustada; solicitudes
que rechazan unidades liberadas; consistencia entre vistas/AJAX; permisos, CSRF,
solo lectura, protección de relaciones y rollback completo.

Los snapshots comparan todos los campos de Kardex, ingresos/distribuciones 1H,
asignaciones originales, ubicaciones, solicitudes, reservas, requerimientos y
asignaciones directas antes/después de liberar. No se alteró ningún registro de
esas tablas durante la operación de liberación. Las asignaciones posteriores
constituyen operaciones separadas explícitas de las pruebas.

Suite completa: **146 ejecutadas, 136 aprobadas, 3 fallos y 7 errores**, sin omisiones.
Los diez resultados no aprobados coinciden exactamente con la base anterior:
seis errores de fixtures de reversiones que duplican el grupo Gestor; tres pruebas
de Kardex con saldos/filas incompatibles con los movimientos de sus fixtures; y
una prueba PDF que espera firmas comentadas en la plantilla. No se afirma que
esa suite previa esté totalmente aprobada ni se modificaron sus pruebas.
Las suites existentes de 1H, confirmación, disponibilidad, asignación directa,
divisiones, solicitudes, reservas y despachos conservan sus resultados.

Chromium completó el modal real, validación de exceso/justificación, liberación
parcial de 500, historial DataTables, Stock, Control General y asignación directa
posterior de las 500 unidades. Verificó físico 1,200, compromiso de división 700,
Kardex intacto y ausencia de IDs duplicados. No hubo errores de los scripts nuevos.
Persisten errores globales previos de Riho (`sidebar-pin.js` y
`custom-list-product.js`), ya documentados en la reparación anterior; no se
silenciaron ni se cambió el diseño general.

La migración 0060 se aplicó correctamente en desarrollo. `makemigrations --check
--dry-run` no detectó cambios pendientes. `check` conserva las dos advertencias
previas (namespace duplicado y ForeignKey único). `collectstatic` se verificó en
un directorio externo al checkout; el JavaScript recolectado coincide con la fuente.
La base de desarrollo continúa con **cero liberaciones**: las escrituras de pruebas
ocurrieron únicamente en bases temporales eliminadas por el runner.

## Auditoría pendiente del artículo 675 de producción

La base PostgreSQL disponible en esta tarea no contiene `Articulo.codigo='675'`.
El SQLite versionado es un snapshot anterior sin columna `codigo`; no se interpreta
su PK como código comercial. No hay acceso a la base de IIS. Por tanto, los números
reales informados por el usuario no se consideran reconciliados ni se libera stock
productivo en este trabajo. Los escenarios numéricos se validaron con fixtures
separados, PK 9876 / código 675, descripción indicada, categoría Suministro y renglón 294.

En el entorno real, localizar primero la PK por código y ejecutar el diagnóstico
existente, que ahora también informa el máximo liberable y sus motivos:

```powershell
python manage.py shell -c "from almacen_app.models import Articulo; print(list(Articulo.objects.filter(codigo='675').values('pk','codigo','nombre')))"
python manage.py auditar_articulo_1h --articulo PK_REAL > diagnostico-675.json
```

La auditoría usa una transacción REPEATABLE READ, READ ONLY. Comparar la existencia
física, los compromisos directos, los consumos por origen y
`liberacion_por_division`. Si `maximo_liberable` es cero por revisión, resolver el
diagnóstico en un trabajo separado, sin resetear asignaciones, fabricar ingresos,
borrar Kardex ni alterar Formularios 1H confirmados.

## Despliegue en Windows Server / IIS

1. Respaldar la base y el despliegue. Publicar juntos el Python, templates,
   JavaScript y migración listados; conservar la configuración y el venv del sitio.
2. Desde la carpeta real `upcv_app`, con el Python del venv de IIS:

   ```powershell
   python manage.py migrate --plan
   python manage.py migrate --noinput
   python manage.py check
   python manage.py collectstatic --noinput
   ```

   La migración crea la bitácora vacía; no contiene RunPython ni modifica inventarios.
3. Reciclar **AppAlmacen** (o el Application Pool real) y recargar completamente el
   navegador. Confirmar HTTP 200 del archivo
   `static/almacen_app/js/liberacion_division.js?v=20261104.1`.
4. Ejecutar la auditoría de solo lectura de 675 antes de utilizar la acción sobre
   ese inventario. La prueba de escritura del despliegue debe hacerse en una base
   de pruebas, no creando asignaciones o liberaciones ficticias en producción.
5. Comprobar con Administrador el modal, el historial y la coherencia de Stock,
   Control General y Asignación Directa; con Almacen, comprobar que no puede liberar.

No se añaden dependencias Python/JavaScript externas. No copiar la configuración
local de nube a IIS. Una vez registradas liberaciones, no desplegar una versión
antigua que ignore la bitácora ni eliminar la migración: calcularía compromisos sin
L. Cualquier reversión del despliegue debe conservar y considerar esas operaciones.
La comprobación en IIS queda pendiente de ejecutarse en ese servidor.
