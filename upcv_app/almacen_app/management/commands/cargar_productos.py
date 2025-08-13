from django.db.models import Max
from django.db import transaction
from decimal import Decimal
import pandas as pd
from almacen_app.models import (
    form1h, Proveedor, Articulo, DetalleFactura, Categoria, UnidadDeMedida,
    Ubicacion, LineaLibre
)
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date


class Command(BaseCommand):
    help = 'Carga masiva de productos desde un archivo Excel'

    def add_arguments(self, parser):
        parser.add_argument('archivo_excel', type=str, help='Ruta al archivo Excel')

    @transaction.atomic
    def handle(self, *args, **kwargs):
        archivo = kwargs['archivo_excel']
        df = pd.read_excel(archivo)

        if df.empty:
            self.stdout.write(self.style.ERROR('El archivo está vacío.'))
            return

        # Agrupar por numero_factura
        facturas = df.groupby('numero_factura')

        for numero_factura, grupo in facturas:
            self.stdout.write(f'Procesando factura: {numero_factura}')

            # Verificar si ya existe un form1h con el numero_factura
            f1h = form1h.objects.filter(numero_factura=numero_factura).first()

            if not f1h:
                # Si no existe, se crea uno nuevo
                first_row = grupo.iloc[0]
                proveedor_nombre = first_row.get('proveedor', '') or ''
                proveedor, _ = Proveedor.objects.get_or_create(nombre=proveedor_nombre)

                # Crear un nuevo form1h
                f1h = form1h.objects.create(
                    proveedor=proveedor,
                    numero_factura=numero_factura,
                    estado=first_row.get('estado', 'borrador'),
                    fecha_ingreso=first_row.get('fecha_ingreso'),
                    orden_compra=first_row.get('orden_compra'),
                    nit_proveedor=first_row.get('nit_proveedor'),
                    proveedor_nombre=proveedor_nombre,
                    telefono_proveedor=first_row.get('telefono_proveedor'),
                    direccion_proveedor=first_row.get('direccion_proveedor'),
                    patente=first_row.get('patente'),
                    fecha_factura=first_row.get('fecha_factura'),
                    serie_id=first_row.get('serie_id'),
                    dependencia_id=first_row.get('dependencia_id'),
                    programa_id=first_row.get('programa_id'),
                )

            # Obtener el número de serie de la factura
            numero_serie = f1h.numero_serie  # Ahora obtenemos el numero_serie de form1h directamente

            # Procesar los detalles de la factura
            for _, row in grupo.iterrows():
                categoria, _ = Categoria.objects.get_or_create(nombre=row.get('categoria', 'Sin Categoría'))
                unidad_nombre = row.get('unidad_medida', 'UND')
                unidad, _ = UnidadDeMedida.objects.get_or_create(
                    nombre=unidad_nombre,
                    defaults={'simbolo': unidad_nombre[:3]}
                )
                ubicacion_nombre = row.get('ubicacion', 'Principal')
                ubicacion, _ = Ubicacion.objects.get_or_create(nombre=ubicacion_nombre)

                articulo_nombre = row.get('articulo', 'Sin Nombre')
                articulo, _ = Articulo.objects.get_or_create(
                    nombre=articulo_nombre,
                    defaults={'categoria': categoria, 'unidad_medida': unidad, 'ubicacion': ubicacion}
                )

                # Revisar si hay fecha de vencimiento
                fecha_vencimiento = row.get('fecha_vencimiento')
                if pd.isna(fecha_vencimiento):
                    fecha_vencimiento = None  # Si no hay fecha, se asigna None
                else:
                    try:
                        # Si hay fecha de vencimiento, actualizamos el artículo para que requiera vencimiento
                        fecha_vencimiento = pd.to_datetime(fecha_vencimiento, format='%d/%m/%Y').strftime('%Y-%m-%d')

                        # Actualizar el campo `requiere_vencimiento` a True para este artículo
                        articulo.requiere_vencimiento = True
                        articulo.save()

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error al procesar la fecha de vencimiento: {fecha_vencimiento}, error: {e}"))
                        fecha_vencimiento = None  # En caso de error, asignamos None

                cantidad = int(row.get('cantidad', 0))
                precio_unitario = Decimal(row.get('precio_unitario', 0))

                # Crear detalle factura con el numero_serie adecuado
                DetalleFactura.objects.create(
                    form1h=f1h,
                    articulo=articulo,
                    cantidad=cantidad,
                    precio_unitario=precio_unitario,
                    precio_total=cantidad * precio_unitario,
                    id_linea=articulo.id,
                    renglon=articulo.id,
                    fecha_vencimiento=fecha_vencimiento,  # Si es None, se pasa como None
                )

            # Guardar estado final en form1h
            if f1h.estado not in ['borrador', 'confirmado', 'anulado']:
                f1h.estado = 'borrador'
            f1h.save()

            self.stdout.write(self.style.SUCCESS(f'Factura {numero_factura} cargada con estado "{f1h.estado}".'))

# comando para cargar datos desde excel:  python manage.py cargar_productos "C:\\Users\\Julio Rodas\\Documents\\carga_masiva.xlsx"