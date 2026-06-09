from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('almacen_app', '0049_solicitudrequerimiento_justificacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='articulo',
            name='renglon_presupuestario',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='Renglón presupuestario'),
        ),
    ]
