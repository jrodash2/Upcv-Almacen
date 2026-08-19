from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('almacen_app', '0055_detallesolicitud_division_related_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='CargaInicialInventario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('archivo', models.FileField(upload_to='cargas_iniciales/')),
                ('nombre_archivo', models.CharField(max_length=255)),
                ('hash_archivo', models.CharField(max_length=64, unique=True)),
                ('fecha_carga', models.DateTimeField(auto_now_add=True)),
                ('estado', models.CharField(choices=[('procesada', 'Procesada'), ('error', 'Error')], default='procesada', max_length=20)),
                ('total_filas', models.PositiveIntegerField(default=0)),
                ('filas_validas', models.PositiveIntegerField(default=0)),
                ('filas_error', models.PositiveIntegerField(default=0)),
                ('observacion', models.TextField(blank=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-fecha_carga']},
        ),
        migrations.CreateModel(
            name='CargaInicialInventarioDetalle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=50)),
                ('nombre', models.CharField(max_length=1085)),
                ('renglon', models.CharField(blank=True, max_length=20)),
                ('categoria', models.CharField(blank=True, max_length=255)),
                ('unidad', models.CharField(blank=True, max_length=50)),
                ('cantidad', models.PositiveIntegerField()),
                ('costo_unitario', models.DecimalField(decimal_places=2, max_digits=25)),
                ('total', models.DecimalField(decimal_places=2, max_digits=25)),
                ('estado', models.CharField(max_length=20)),
                ('mensaje', models.TextField(blank=True)),
                ('articulo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='almacen_app.articulo')),
                ('carga', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detalles', to='almacen_app.cargainicialinventario')),
            ],
        ),
    ]
