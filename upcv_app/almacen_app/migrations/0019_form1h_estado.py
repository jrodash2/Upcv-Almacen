# Generated by Django 5.1.4 on 2025-05-15 20:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('almacen_app', '0018_alter_detallefactura_id_linea_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='form1h',
            name='estado',
            field=models.CharField(choices=[('borrador', 'Borrador'), ('confirmado', 'Confirmado')], default='borrador', max_length=20),
        ),
    ]
