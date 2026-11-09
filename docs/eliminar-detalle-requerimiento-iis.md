# Eliminación de detalles de requerimiento — 9 de noviembre de 2026

## Diagnóstico y alcance

`eliminar_detalle_requerimiento` responde JSON a POST en
`/almacen/detalle-requerimiento/eliminar/<pk>/`. El template
`detalle_requerimiento.html` enviaba CSRF y la PK correcta, pero descartaba
el cuerpo de cualquier respuesta HTTP no exitosa y mostraba siempre
«Error al eliminar el detalle». También recargaba ante cualquier HTTP 200,
incluso si era una página HTML de autenticación o un JSON sin `success: true`.

El commit `f0df30d` incorporó el bloqueo intencional de detalles de requerimientos
con solicitudes de origen: conservan reservas y un desglose protegido mediante
`DetalleSolicitudRequerimiento.detalle_requerimiento` (`PROTECT`). En pruebas,
este caso devuelve HTTP 400 con la instrucción de anular el requerimiento.
No se elimina la restricción ni se alteran las fuentes para permitir borrar.
La captura del requerimiento real 869 no muestra su respuesta HTTP ni sus datos;
no se ha consultado ese registro de producción y no se atribuye su rechazo a
una causa particular sin esa evidencia. El modal reparado permite verla.

Se encontraron además validaciones ausentes: el endpoint permitía borrar filas
en cabeceras no pendientes y desvincular un Kardex (`SET_NULL`) cuando el
contador de despacho era cero. Las pruebas previas reprodujeron ambas pérdidas
de protección. Ahora se comprueban cabecera, detalle y vínculo Kardex bajo los
bloqueos existentes, antes de borrar. Los Departamentos deben pertenecer al
departamento del requerimiento, conforme a la comprobación de acceso de la
pantalla; no se cambian grupos ni asignaciones de permisos.

## Cambios

- `views.py`: `eliminar_detalle_requerimiento` conserva POST, CSRF, grupos,
  bloqueo de departamento y fuentes. Bloquea después cabecera y detalle;
  contrasta el requerimiento enviado por el modal, conserva fuentes protegidas,
  rechaza estados no permitidos y movimientos Kardex. Un savepoint revierte
  por completo una excepción de borrado antes de responder JSON 500 y registrar
  el traceback en el servidor. No se expone el traceback al cliente.
- `templates/almacen/detalle_requerimiento.html`: identifica la cabecera y
  contiene un mensaje accesible dentro del modal Riho.
- `static/almacen_app/js/eliminar_detalle_requerimiento.js`: muestra el error JSON
  mediante `textContent`, valida HTTP, tipo de contenido y `success: true`;
  mantiene el modal abierto ante rechazo y deshabilita el botón durante la
  petición. No elimina filas optimistamente ni interpreta redirecciones como éxito.
- `test_eliminar_detalle_requerimiento.py`: pruebas específicas de eliminación,
  reservas, fuentes, estados, Kardex, acceso, CSRF, repetición y rollback, junto
  con regresión de agregar y editar detalles.

## Inventario

Una fila directa pendiente sin solicitud aporta una reserva calculada por
`fuentes_departamento`. Al eliminarla, desaparece solo esa reserva implícita;
no se modifica la asignación ni se crea un ingreso de inventario.
Las reservas explícitas de solicitudes directas y de división se mantienen
intactas ante el rechazo. Para cambiar ese desglose se conserva el flujo existente
de anulación y nueva solicitud. No se invoca un servicio de liberación global
para borrar una sola fila.

No se cambian modelos, migraciones, fórmulas de stock, Kardex, correlativos,
precios, despachos o Formularios 1H. Todas las operaciones reproducidas utilizan
una base PostgreSQL de pruebas, nunca el requerimiento 869 real.

Las optimizaciones de búsqueda y carga diferida de Asignar Artículo que ya estaban
sin publicar al comenzar esta tarea son trabajo anterior; no forman parte de esta
reparación aunque sigan presentes en el directorio de trabajo.

## Verificación y despliegue

Pruebas específicas:

```console
python manage.py test almacen_app.test_eliminar_detalle_requerimiento --noinput
```

Resultado: 12 pruebas específicas correctas. La suite completa ejecutó 191:
181 correctas y los mismos 10 fallos anteriores (3 fallos de aserción y 7 errores);
no hubo fallos nuevos frente al registro previo. Los fallos previos pertenecen a
impresión, cálculos de Kardex y fixtures de reversiones. No se corrigieron fuera
del alcance de esta tarea. `check` conserva las dos advertencias previas sobre
namespace y ForeignKey única; `makemigrations --check --dry-run` no detecta cambios.
`collectstatic`, la sintaxis JavaScript y `git diff --check` también se verificaron.

Se probó además en Chromium el rechazo por fuente reservada, el modal abierto,
el botón habilitado para reintentar, el doble clic (una sola petición), una respuesta HTML, un JSON de rechazo con
HTTP 200 y el borrado válido seguido de recarga. Solo se validó en el entorno de
pruebas Linux; IIS requiere actualizar sus archivos para comprobarlo allí.

Al desplegar los archivos aprobados en Windows Server, desde la carpeta que
contiene `manage.py`, ejecutar con el mismo Python y configuración del sitio:

```powershell
C:\Python\python.exe manage.py collectstatic --noinput
```

Reciclar el application pool del sitio para cargar el cambio Python y recargar
el navegador con Ctrl+F5. Confirmar que la URL estática de
`almacen_app/js/eliminar_detalle_requerimiento.js?v=20261109.1` devuelve JavaScript.
No se requieren migraciones nuevas ni ajustes de inventario. Probar primero
con un requerimiento de prueba y verificar que un rechazo mantiene el detalle.

No se publicaron cambios en GitHub.
