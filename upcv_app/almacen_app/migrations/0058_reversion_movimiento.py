import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('almacen_app', '0057_detallefacturadivision'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='kardex',
            name='estado',
            field=models.CharField(
                choices=[
                    ('activo', 'Activo'),
                    ('revertido', 'Revertido'),
                    ('reversion', 'Reversión'),
                ],
                default='activo',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='kardex',
            name='motivo_reversion',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='kardex',
            name='movimiento_revertido',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='movimientos_reversion',
                to='almacen_app.kardex',
            ),
        ),
        migrations.CreateModel(
            name='ReversionMovimiento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo_reversion', models.CharField(choices=[('INGRESO', 'Reversión de ingreso'), ('SALIDA', 'Reversión de salida')], max_length=20)),
                ('cantidad', models.DecimalField(decimal_places=2, max_digits=12)),
                ('justificacion', models.TextField()),
                ('fecha_reversion', models.DateTimeField(auto_now_add=True)),
                ('documento_referencia', models.CharField(blank=True, max_length=150, null=True)),
                ('observacion_sistema', models.TextField(blank=True, null=True)),
                ('articulo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reversiones', to='almacen_app.articulo')),
                ('movimiento_original', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='reversion_realizada', to='almacen_app.kardex')),
                ('movimiento_reversion', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='reversion_generada', to='almacen_app.kardex')),
                ('realizado_por', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reversiones_realizadas', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-fecha_reversion']},
        ),
    ]
