from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('almacen_app', '0047_requerimiento_fechas_resolucion'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitudrequerimiento',
            name='tipo_solicitud',
            field=models.CharField(
                choices=[
                    ('bienes', 'Bienes'),
                    ('suministros', 'Suministros'),
                    ('insumos', 'Insumos'),
                ],
                default='suministros',
                max_length=20,
            ),
        ),
    ]
