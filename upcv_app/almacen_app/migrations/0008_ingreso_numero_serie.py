# Generated by Django 5.1.4 on 2025-03-13 17:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('almacen_app', '0007_serie_numero_actual'),
    ]

    operations = [
        migrations.AddField(
            model_name='ingreso',
            name='numero_serie',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
