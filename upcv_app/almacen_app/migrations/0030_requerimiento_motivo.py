# Generated by Django 5.1.4 on 2025-07-17 21:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('almacen_app', '0029_institucion'),
    ]

    operations = [
        migrations.AddField(
            model_name='requerimiento',
            name='motivo',
            field=models.TextField(blank=True, null=True),
        ),
    ]
