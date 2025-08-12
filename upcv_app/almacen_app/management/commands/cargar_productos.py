from django.db.models import Max
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import pandas as pd
from almacen_app.models import (
    form1h, Proveedor, Articulo, DetalleFactura, Categoria, UnidadDeMedida,
    Ubicacion, LineaLibre, ContadorDetalleFactura
)
from django.core.management.base import BaseCommand


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

        # Agrupar productos por número de factura
        facturas = df.groupby('numero_factura')

        for numero_factura, grupo in facturas:
            self.stdout.write(f'Procesando factura: {numero_factura}')

            # Crear o obtener proveedor
            proveedor_nombre = grupo['proveedor'].iloc[0]
            proveedor, _ = Proveedor.objects.get_or_create(nombre=proveedor_nombre)

            # Crear form1h (borrador)
            f1h = form1h.objects.create(
                proveedor=proveedor,
                numero_factura=numero_factura,
                estado='borrador',
                fecha_ingreso=grupo['fecha_ingreso'].iloc[0],
                orden_compra=grupo['orden_compra'].iloc[0],
                nit_proveedor=grupo['nit_proveedor'].iloc[0],
                proveedor_nombre=proveedor_nombre,
                telefono_proveedor=grupo['telefono_proveedor'].iloc[0] if 'telefono_proveedor' in grupo.columns else None,
                direccion_proveedor=grupo['direccion_proveedor'].iloc[0] if 'direccion_proveedor' in grupo.columns else None,
                patente=grupo['patente'].iloc[0] if 'patente' in grupo.columns else None,
                fecha_factura=grupo['fecha_factura'].iloc[0],
                serie_id=grupo['serie_id'].iloc[0] if 'serie_id' in grupo.columns else None,
                dependencia_id=grupo['dependencia_id'].iloc[0] if 'dependencia_id' in grupo.columns else None,
                programa_id=grupo['programa_id'].iloc[0] if 'programa_id' in grupo.columns else None,
            )

            for _, row in grupo.iterrows():
                # Obtener o crear entidades relacionadas
                categoria, _ = Categoria.objects.get_or_create(nombre=row['categoria'])
                unidad, _ = UnidadDeMedida.objects.get_or_create(
                    nombre=row['unidad_medida'],
                    defaults={'simbolo': row['unidad_medida'][:3]}
                )
                ubicacion, _ = Ubicacion.objects.get_or_create(nombre=row.get('ubicacion', 'Principal'))

                # Crear o obtener artículo
                articulo, _ = Articulo.objects.get_or_create(
                    nombre=row['articulo'],
                    defaults={'categoria': categoria, 'unidad_medida': unidad, 'ubicacion': ubicacion}
                )

                # Reservar línea libre con creación dinámica si no hay disponibles
                linea = LineaLibre.objects.order_by('id_linea').first()
                if not linea:
                    ultimo_id = LineaLibre.objects.aggregate(max_id=Max('id_linea'))['max_id'] or 0
                    nuevas_lineas = [LineaLibre(id_linea=ultimo_id + i) for i in range(1, 11)]
                    LineaLibre.objects.bulk_create(nuevas_lineas)
                    linea = LineaLibre.objects.order_by('id_linea').first()

                if not linea:
                    raise Exception('No hay líneas libres disponibles ni se pudieron crear nuevas.')

                id_linea = linea.id_linea
                linea.delete()

                # Manejar fecha de vencimiento nula
                fecha_vencimiento = row.get('fecha_vencimiento')
                if pd.isna(fecha_vencimiento):
                    fecha_vencimiento = None

                # Crear detalle de factura
                DetalleFactura.objects.create(
                    form1h=f1h,
                    articulo=articulo,
                    cantidad=int(row['cantidad']),
                    precio_unitario=Decimal(row['precio_unitario']),
                    precio_total=Decimal(row['cantidad']) * Decimal(row['precio_unitario']),
                    id_linea=id_linea,
                    renglon=id_linea,
                    fecha_vencimiento=fecha_vencimiento
                )

            # Confirmar formulario (esto debería generar el ingreso automático en Kardex)
            f1h.estado = 'confirmado'
            f1h.save()

            self.stdout.write(self.style.SUCCESS(f'Factura {numero_factura} cargada y confirmada con éxito.'))
