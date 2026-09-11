from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('almacen_app', '0056_cargainicialinventario_and_detalle'),
    ]

    operations = [
        migrations.CreateModel(
            name='DetalleFacturaDivision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cantidad_asignada', models.DecimalField(decimal_places=2, max_digits=12)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('creado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('detalle_factura', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='asignaciones_division', to='almacen_app.detallefactura')),
                ('division', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='detalles_factura', to='almacen_app.divisionalmacen')),
            ],
        ),
        migrations.AddConstraint(
            model_name='detallefacturadivision',
            constraint=models.UniqueConstraint(fields=('detalle_factura', 'division'), name='unique_detalle_factura_division'),
        ),
    ]
