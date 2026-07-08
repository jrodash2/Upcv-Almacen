# Generated manually for DivisionArticuloUbicacion reverse relation

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('almacen_app', '0054_divisiones_almacen'),
    ]

    operations = [
        migrations.AlterField(
            model_name='detallesolicitudrequerimiento',
            name='division_articulo_ubicacion',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='detalles_solicitud', to='almacen_app.divisionarticuloubicacion'),
        ),
    ]
