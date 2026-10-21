# Solicitud: filtro de categorías y justificación obligatoria

## Causa

La selección vacía se interpretaba como ausencia de filtro en el formulario y en la
API, por lo que podía ofrecer todo el catálogo asignado. Las consultas AJAX no
cancelaban respuestas anteriores: una respuesta de una selección anterior podía
reemplazar las opciones actuales. Al cambiar tipos se reconstruían selectores, pero
no se eliminaban las filas cuyos artículos ya no correspondían.

El filtrado estaba duplicado en formulario/API mediante coincidencias parciales de
texto (`icontains`). La justificación, por su parte, seguía siendo opcional en el
ModelForm porque el campo del modelo permite valores vacíos para históricos.

## Corrección y alcance

`categorias_solicitud.py` define un mapeo común entre los valores internos de los
checkboxes y los nombres del catálogo `Categoria.nombre`:

| Valor interno | Etiquetas admitidas |
|---|---|
| bienes | Bien, Bienes |
| suministros | Suministro, Suministros |
| insumos | Insumo, Insumos |

Se normalizan mayúsculas y espacios exteriores sin modificar categorías almacenadas.
No se trata cualquier nombre que contenga «bien» como categoría Bienes. El modelo
usa una FK a Categoria y su nombre, no códigos internos adicionales de categoría.
El catálogo PostgreSQL preparado para desarrollo estaba vacío; las variantes se
validaron con fixtures, incluidos `Suministro` y el artículo Masking del caso indicado.
No se ha inspeccionado el catálogo real de producción.

La selección múltiple se mantiene: se ofrece la unión de los tipos marcados. Ningún
tipo significa selector vacío y Agregar ítem deshabilitado. Se aplica tanto a filas
existentes del formulario nuevo como a las agregadas después.

El endpoint compartido recibe `contexto=solicitud` en este flujo; así, una selección
vacía devuelve cero artículos y solo se ofrecen artículos con disponibilidad. Su uso
anterior sin ese contexto por la pantalla de transferencias conserva el contrato
sin filtro. Esto evita afectar otra funcionalidad que comparte el endpoint.

Al desmarcar una categoría se eliminan las filas incompatibles mediante el mismo
helper que usa Quitar: API de DataTables, borrado de controles y sincronización de
índices. Se recorren todas las páginas de la tabla. La notificación informa cuántos
artículos se retiraron. No se borran artículos del catálogo ni detalles persistidos.
Se cancelan peticiones obsoletas y se ignoran respuestas de generaciones anteriores.
Mientras se carga el filtro se impide enviar una selección incompleta.

El widget Django muestra solamente opciones permitidas; el campo conserva el queryset
**autorizado** para identificar un artículo enviado mediante POST manipulado. Después
`clean_articulo` comprueba su categoría real y rechaza la discrepancia con código,
nombre y categoría en el mensaje. No basta con agregar una opción desde DevTools.

Justificación tiene `required` en el formulario y un asterisco visible. Cliente y
servidor recortan espacios y usan el mensaje:

> Debe ingresar una justificación para crear la solicitud.

No se exige una longitud mínima adicional: una justificación de un carácter es válida.
Sin tipos se muestra:

> Debe seleccionar al menos un tipo de solicitud: Bienes, Suministros o Insumos.

No se encontró pantalla de edición que reutilice este formulario: se usa al crear.
Se comprobó que consultar una solicitud histórica vacía no modifica justificación
ni elimina detalles. El modelo sigue admitiendo esos datos históricos.

## Archivos modificados

- `upcv_app/almacen_app/categorias_solicitud.py`: mapeo, mensajes y filtro común.
- `upcv_app/almacen_app/form.py`: opciones por categoría, comprobación del artículo
  enviado y justificación obligatoria con recorte de espacios.
- `upcv_app/almacen_app/views.py`: filtro común en API y metadatos iniciales del formulario.
- `upcv_app/almacen_app/templates/almacen/crear_solicitud_requerimiento.html`:
  selección dinámica, retiro de filas, control de respuestas AJAX y validación visible.
- `upcv_app/almacen_app/test_categorias_solicitud.py`: trece pruebas nuevas.
- `upcv_app/almacen_app/test_solicitud_filas.py` y `test_disponibilidad.py`: las peticiones
  válidas de los fixtures ahora incluyen justificación; se conservan sus aserciones.
- Esta guía.

No se modifican modelos, migraciones, cálculos de disponibilidad, servicio de fuentes,
reservas, consumos, despachos, stock, Formulario 1H, Kardex, Reversiones, PDFs, permisos
ni el diseño general. Las fuentes Directo/División y sus cantidades se conservan.

## Pruebas

Desde `upcv_app`, con la configuración de desarrollo y PostgreSQL:

```text
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test almacen_app.test_categorias_solicitud almacen_app.test_solicitud_filas almacen_app.test_disponibilidad --noinput
```

Pasaron las 54 pruebas específicas: las 13 nuevas y las 41 de regresión anteriores.
Cubren las ocho combinaciones de tipos, singular/plural/mayúsculas, POST manipulado,
justificación vacía/espacios, recorte y ausencia de longitud mínima, selección múltiple,
Directo con División agotada, reserva por División, API de transferencias e históricos.
Las regresiones conservan cobertura de Quitar, Guardar, reservas, conversión,
despachos y concurrencia PostgreSQL.

En Chromium con servidor Django y PostgreSQL de pruebas también pasaron:

- Las ocho combinaciones muestran exactamente la unión esperada.
- Cambiar Suministros + Bienes a solo Bienes elimina Masking, conserva la otra fila
  y su cantidad, y envía únicamente esa fila en el POST.
- Justificación vacía o con espacios no produce POST y muestra el mensaje.
- De trece filas paginadas se retiran siete incompatibles, se conservan seis y se
  guardan realmente esas seis en PostgreSQL, sin campos residuales.
- Directo sigue disponible cuando División está agotada.
- Una respuesta AJAX de Bienes deliberadamente atrasada no restaura opciones cuando
  la selección actual es Suministros.

`check` no encontró errores; mantiene las advertencias anteriores de namespace
`almacen` duplicado y ForeignKey único. No hay migraciones nuevas que generar.
Los errores generales de Riho previamente documentados no se modificaron.

## Despliegue IIS

Desplegar juntos helper, formulario, vista y template de esta revisión en el proyecto
bajo `C:\Users\Administrador\Documents\AppAlmacen\upcv_app`.

Esta corrección **no agrega migraciones**. Presupone la revisión anterior de fuentes
y su migración `0059`, documentada en [Disponibilidad por origen](disponibilidad-origenes-iis.md).

Ejecutar `python manage.py check` con el Python/settings reales del sitio y reciclar
solo el Application Pool de la aplicación. No hace falta `collectstatic`: el JavaScript
modificado está dentro del template y no se cambiaron archivos estáticos.

Tras una recarga forzada, verificar el asterisco de Justificación, el parámetro
`contexto=solicitud`, los varios `tipos_solicitud` del GET y las ocho combinaciones.
Probar el caso Masking/Suministro, cambiar categorías con filas ya agregadas y revisar
el POST. Con justificación válida el éxito devuelve 201; una validación del servidor
responde 400 con los mensajes visibles. No compartir cookies ni tokens al diagnosticar.

No se accedió ni desplegó al IIS real desde este entorno; esa verificación queda
pendiente con el catálogo y los usuarios de producción.
