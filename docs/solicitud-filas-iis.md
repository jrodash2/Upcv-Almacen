# Crear Solicitud: filas, guardado e IIS

## Diagnóstico y alcance

La pantalla usa un ModelFormSet nuevo (`detalles`, `INITIAL_FORMS=0`), con campos
`articulo`, `cantidad` y `DELETE`. La fuente Directo/División se resuelve en el
backend; no hay ID de asignación enviado por el navegador. No se encontraron
borradores en sesión, caché, localStorage, sessionStorage ni base de datos en este
flujo. No hay cambios en permisos, modelos, migraciones ni cálculos de existencias.

La corrección anterior de Quitar se conserva: altas y bajas usan la API de
DataTables, las filas eliminadas pierden sus controles y los índices se compactan.
Las filas DELETE de un POST inválido tampoco se renderizan de nuevo.

Se identificaron estos problemas concretos en Guardar:

- El POST tradicional dependía de `draw()` de DataTables y `reportValidity()` antes
  de enviar. Un error en ese paso podía interrumpir el envío; las validaciones
  nativas no tenían un resumen visible en la pantalla.
- Los errores transaccionales de disponibilidad se enviaban mediante `messages`,
  pero ni el template ni su base los renderizaban. Ahora aparecen en un resumen.
- Guardar quedaba deshabilitado por el stock inicial, y los botones no se
  actualizaban al cargar artículos de otro departamento mediante AJAX. Esto
  dependía de los datos y departamentos del usuario.

Estos problemas se verificaron en el código y las pruebas de desarrollo. **No se
ha accedido al IIS real ni se ha confirmado cuál de ellos explica el incidente
reportado en producción.** Es necesario observar su petición y respuesta HTTP.

## Comportamiento corregido

El formulario sigue enviando los mismos campos, CSRF y nombres de formset al mismo
endpoint. Cuando JavaScript está activo utiliza `fetch`, `FormData` y
`Accept: application/json`. Recupera todas las filas activas de DataTables, incluidas
las páginas separadas del DOM; descarta del payload la selección parcial del DOM
y agrega una sola vez los controles de todas las filas. No depende de redibujar
la tabla para guardar. Si DataTables no está disponible, usa las filas del DOM.

La vista sigue admitiendo POST tradicional. Para las peticiones JSON responde:

- `201`, `ok: true`, `redirect_url`: transacción completada; navegar al listado.
- `400`, `ok: false`, `errors`: validación fallida; mostrar los mensajes y conservar
  los datos, con el botón habilitado para corregirlos.

El backend conserva las validaciones y las reservas existentes: cantidades mayores
que cero, suma de filas repetidas, disponibilidad y guardado atómico. Evalúa tanto
la cabecera como los detalles y resume los errores de ambos.

Guardar muestra “Guardando…” y bloquea envíos simultáneos desde la misma página.
Ante HTTP 403/500, respuesta inesperada o error de red muestra un mensaje y restaura
el botón. Si no se recibió confirmación, pide revisar el listado antes de reintentar:
un fallo de red puede ocurrir después del commit. No se añade idempotencia persistente
ni se garantiza deduplicación entre pestañas o reintentos tras perder la respuesta.
No se registran cookies, CSRF ni detalles sensibles en la consola.

## Validación reproducible

Desde `upcv_app`, con Python y PostgreSQL de desarrollo configurados:

```text
python manage.py test almacen_app.test_solicitud_filas --noinput
```

Pasaron las 19 pruebas de regresión. Cubren eliminación y volver a agregar, POST
tradicional y JSON, una/tres/doce filas, cantidades vacías/cero/negativas,
5+3 contra 9 disponibles, rechazo de 5+5, exclusión de cantidades eliminadas,
management_form inválido, errores de cabecera y detalles, rollback y fuente/reservas
por división. También comprueban que un stock vacío no deje Guardar sin respuesta.

En Chromium con servidor Django real y PostgreSQL de pruebas se verificó:

1. Guardar una fila; guardar tres; eliminar una de tres y guardar las dos restantes.
2. Guardar realmente doce filas paginadas/filtradas y comprobarlas en PostgreSQL.
3. Mostrar errores por cero artículos/cantidad cero y guardar tras corregir.
4. Bloquear envíos simultáneos: solo un POST y una solicitud creada.
5. Mostrar HTTP 403/500 y fallos de red simulados, conservar datos y permitir reintento.
6. Mostrar una validación agregada real del backend (filas repetidas sin stock suficiente).
7. Agregar/quitar/guardar con el recurso DataTables bloqueado.
8. Recargar sin restaurar filas eliminadas; cambiar de un departamento sin stock
   inicial a otro con asignaciones disponibles.

En el template anterior y el corregido se observan los mismos errores generales
preexistentes de Riho: `simpleDatatables is not defined`, acceso a `top` sobre
undefined y a `classList` sobre null. También existen recursos generales con 404
y recursos externos inaccesibles desde este entorno. No se alteraron esos scripts;
no aparecieron excepciones JavaScript nuevas en los casos probados.

La suite histórica completa tiene fallos previamente diagnosticados en Kardex y
fixtures del grupo Gestor. No se alteraron esos módulos ni pruebas para ocultarlos.

## Despliegue Windows Server / IIS

1. Desplegar juntos estos archivos de la misma revisión:

   - `upcv_app/almacen_app/views.py`
   - `upcv_app/almacen_app/templates/almacen/crear_solicitud_requerimiento.html`

   El proyecto del sitio está bajo
   `C:\Users\Administrador\Documents\AppAlmacen\upcv_app`.
   Comparar SHA-256 (`Get-FileHash`) de ambos archivos con los de esta revisión.
   No mezclar el template nuevo con una vista antigua: el navegador espera el
   contrato JSON del backend de la misma versión.

2. **Este cambio no requiere `collectstatic`: el JavaScript está dentro del
   template.** No editar manualmente `staticfiles`. Si el despliegue incluye
   cambios adicionales en estáticos, ejecutar con el Python y settings del sitio:

   ```powershell
   Set-Location 'C:\Users\Administrador\Documents\AppAlmacen\upcv_app'
   # Activar el entorno virtual que ya utiliza el sitio.
   python manage.py check
   python manage.py findstatic almacen_app/js/almacen_datatables.js --verbosity 2
   python manage.py collectstatic --noinput
   ```

   El `STATIC_ROOT` del proyecto es `upcv_app/staticfiles`; verificar que IIS sirve
   ese directorio. `findstatic` identifica orígenes duplicados. No ejecutar
   `collectstatic --clear`, limpiar sesiones ni borrar cachés de otros usuarios.

3. Reciclar **solo el Application Pool de esta aplicación** para cargar la vista
   y el template nuevos. Hacerlo conforme al procedimiento operativo del sitio,
   pues puede interrumpir solicitudes en curso. No se requiere reinicio general
   de IIS ni ejecutar migraciones.

4. Abrir una creación nueva con recarga forzada y caché deshabilitada en DevTools.
   Verificar en la respuesta HTML `guardar-solicitud`, `FormData` y
   `Accept: "application/json"`. jQuery y DataTables deben cargar una sola vez;
   comparar la respuesta del JS servido con el origen desplegado si hay dudas.

5. Repetir los casos de navegador con un Gestor y datos de prueba autorizados.
   En Network, comprobar el POST a la misma URL, `csrfmiddlewaretoken`, el
   departamento/tipos y `detalles-TOTAL_FORMS`, con exactamente las filas activas:

   - `201` JSON y navegación al listado: comprobar los detalles en la aplicación.
   - `400` JSON: corregir los mensajes visibles; no debe crearse cabecera parcial.
   - `403`: revisar sesión, CSRF, esquema HTTPS y configuración del proxy/origen
     del sitio. No deshabilitar CSRF ni agregar orígenes sin verificar el host real.
   - `500`: revisar traceback de Django/wfastcgi y logs de IIS de esa petición.
   - Sin POST: revisar el resumen de validación y la consola, y verificar que el
     HTML corresponde a la revisión nueva.

No se ha desplegado ni validado el servidor IIS desde este entorno. Su validación
permanece pendiente y requiere la respuesta HTTP real; no compartir cookies ni tokens.
