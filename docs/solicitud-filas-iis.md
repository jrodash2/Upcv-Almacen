# Crear Solicitud: eliminación de filas e IIS

## Causa y alcance

La pantalla usa un ModelFormSet nuevo (`detalles`, `INITIAL_FORMS=0`). Antes, Quitar
marcaba DELETE y ocultaba la fila con CSS; Agregar insertaba directamente en tbody.
El inicializador compartido de Riho activa DataTables sobre `.datatables`, por lo que
su colección de filas y el DOM divergían. Al redibujar podía reinsertar filas ocultas
y la paginación podía dejar controles, incluido DELETE, fuera del formulario enviado.
No se encontró persistencia de borradores en sesión, caché, localStorage,
sessionStorage ni base de datos en este flujo. Una recarga de POST inválido vuelve
a renderizar sus datos; ahora se omiten también las filas marcadas DELETE.

La tabla ahora agrega y elimina mediante la API de DataTables, elimina los controles
de la fila y compacta nombres e IDs del formset. Las actualizaciones de opciones
recorren todas las páginas. Antes de validar/enviar se muestran todas las filas
activas para que sus controles participen en el POST y la validación nativa.
Quitar conserva texto e icono sin saltos de línea. No se cambia el diseño general.

El backend existente ya ignora DELETE, suma filas repetidas por artículo, valida
cantidades positivas y disponibilidad, y guarda atómicamente. Se conserva la lógica
de fuentes y reservas, sin cambios en modelos, migraciones, stock o permisos.
No se ha demostrado una causa exclusiva de IIS: comparar archivos desplegados y
respuestas del servidor es necesario para confirmar qué versión tiene producción.

## Validación reproducible

Desde `upcv_app`, con el entorno Python y PostgreSQL de desarrollo activados:

```text
python manage.py test almacen_app.test_solicitud_filas --noinput
```

Las pruebas cubren filas eliminadas/inválidas, volver a agregar sin duplicados,
5+3 contra 9 disponibles, rechazo de 5+5, exclusión de cantidades eliminadas,
peticiones vacías/incompletas, nueva carga y reservas/consumos por división.

Para la comprobación en navegador, usar un Gestor de pruebas con artículos asignados:

1. Agregar A y B, quitar B y guardar: Network debe mostrar solo A y TOTAL_FORMS=1.
2. Repetir quitando B y volviéndolo a agregar: exactamente dos detalles.
3. Agregar más de diez filas; buscar, quitar, paginar y ordenar: la fila no reaparece
   y el contador disminuye. Al enviar deben incluirse todas las filas restantes.
4. Recargar una creación nueva: no se restauran los artículos eliminados.
5. Probar 5+3 y 5+5 del mismo artículo con 9 disponibles; repetir con división,
   comprobando que una petición rechazada no altera reservas ni crea cabecera.

## Resultados en el entorno de desarrollo

- PostgreSQL: las nueve pruebas de regresión pasaron.
- Chromium, con servidor Django real y base de pruebas: pasaron los casos A–D,
  se inspeccionó el POST real y se comprobaron los detalles persistidos para A/B.
  También se comprobó que las doce filas activas de una tabla paginada se envían.
- En el template original y en el corregido aparecen los mismos errores generales
  de Riho: `simpleDatatables is not defined`, acceso a `top` sobre undefined y a
  `classList` sobre null. También hay recursos generales con 404 y recursos externos
  inaccesibles desde este entorno. No aparecieron excepciones JavaScript nuevas
  durante los casos probados. Estos problemas ajenos al flujo no se modificaron.
- La suite histórica completa tiene fallos ya diagnosticados de Kardex y fixtures
  del grupo Gestor; no se alteraron esos módulos ni pruebas para ocultarlos.
- IIS: pendiente de validación en el servidor real. No se ejecutó despliegue remoto.

## Despliegue Windows Server / IIS

1. Desplegar el template `upcv_app/almacen_app/templates/almacen/crear_solicitud_requerimiento.html`
   en el checkout real del sitio, bajo `C:\Users\Administrador\Documents\AppAlmacen`.
   Comparar su hash SHA-256 (`Get-FileHash`) con el archivo de esta revisión.
2. Este cambio mantiene el JavaScript dentro del template: **no requiere collectstatic**.
   No editar manualmente copias de `staticfiles`. Si también se actualizan archivos
   estáticos en el despliegue, ejecutar, con el Python del sitio y sus settings reales:

   ```powershell
   Set-Location 'C:\Users\Administrador\Documents\AppAlmacen\upcv_app'
   # Activar aquí el entorno virtual que ya utiliza el sitio.
   python manage.py findstatic almacen_app/js/almacen_datatables.js --verbosity 2
   python manage.py collectstatic --noinput
   ```

   El `STATIC_ROOT` del proyecto es `upcv_app/staticfiles`; verificar que IIS sirve
   ese directorio. `findstatic` permite detectar copias de origen duplicadas sin
   borrar archivos. No ejecutar `collectstatic --clear` ni limpiar sesiones.
3. Reciclar **solo el Application Pool de esta aplicación** para cargar el template
   actualizado y vaciar la caché de templates de los workers. Puede interrumpir
   solicitudes en curso: hacerlo conforme al procedimiento operativo del sitio.
4. Abrir una creación nueva con recarga forzada y caché deshabilitada en DevTools.
   En la respuesta HTML verificar `tabla.row(row).remove().draw(false)` y
   `sincronizarIndices`; verificar que jQuery/DataTables cargan una sola vez, sin 404
   ni errores de consola. El JS compartido sigue siendo `almacen_app/js/almacen_datatables.js`.
5. Repetir los casos anteriores en producción con datos de prueba autorizados y
   revisar el POST y los detalles guardados. No se ha accedido ni desplegado al IIS
   de producción desde este entorno; su verificación permanece pendiente.

No se requieren migraciones ni reinicio general del servidor IIS.
