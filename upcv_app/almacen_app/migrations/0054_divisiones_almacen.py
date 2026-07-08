# Generated manually for divisiones de almacén

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('almacen_app', '0053_merge_20260701_1420'),
    ]

    operations = [
        migrations.CreateModel(
            name='DivisionAlmacen',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=150, unique=True)),
                ('descripcion', models.TextField(blank=True, null=True)),
                ('activa', models.BooleanField(default=True)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('creado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='divisiones_creadas', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='DivisionArticulo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cantidad_asignada', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('observacion', models.TextField(blank=True, null=True)),
                ('activo', models.BooleanField(default=True)),
                ('fecha_asignacion', models.DateTimeField(auto_now_add=True)),
                ('articulo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='divisiones_asignadas', to='almacen_app.articulo')),
                ('asignado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('division', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='articulos', to='almacen_app.divisionalmacen')),
            ],
            options={'unique_together': {('division', 'articulo')}},
        ),
        migrations.CreateModel(
            name='DivisionUbicacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activa', models.BooleanField(default=True)),
                ('fecha_asignacion', models.DateTimeField(auto_now_add=True)),
                ('division', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ubicaciones', to='almacen_app.divisionalmacen')),
                ('ubicacion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='divisiones_almacen', to='almacen_app.departamento')),
            ],
            options={'unique_together': {('division', 'ubicacion')}},
        ),
        migrations.CreateModel(
            name='DivisionArticuloUbicacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cantidad_asignada', models.DecimalField(decimal_places=2, max_digits=12)),
                ('cantidad_reservada', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('cantidad_consumida', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('activo', models.BooleanField(default=True)),
                ('fecha_asignacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_actualizacion', models.DateTimeField(auto_now=True)),
                ('asignado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('division_articulo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='asignaciones_ubicacion', to='almacen_app.divisionarticulo')),
                ('ubicacion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='articulos_division_asignados', to='almacen_app.departamento')),
            ],
            options={'unique_together': {('division_articulo', 'ubicacion')}},
        ),
        migrations.AddField(
            model_name='detallesolicitudrequerimiento',
            name='division_articulo_ubicacion',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='almacen_app.divisionarticuloubicacion'),
        ),
    ]
