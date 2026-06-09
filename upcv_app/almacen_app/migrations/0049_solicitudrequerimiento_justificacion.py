from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('almacen_app', '0048_solicitudrequerimiento_tipo_solicitud'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitudrequerimiento',
            name='justificacion',
            field=models.TextField(blank=True, null=True),
        ),
    ]
