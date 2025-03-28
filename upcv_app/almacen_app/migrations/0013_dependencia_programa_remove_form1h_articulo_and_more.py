# Generated by Django 5.1.4 on 2025-03-27 18:01

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('almacen_app', '0012_form1h_cantidad_form1h_precio_total_ingreso_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Dependencia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=255)),
                ('descripcion', models.TextField(blank=True, null=True)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_actualizacion', models.DateTimeField(auto_now=True)),
                ('activo', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='Programa',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=255)),
                ('descripcion', models.TextField(blank=True, null=True)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_actualizacion', models.DateTimeField(auto_now=True)),
                ('activo', models.BooleanField(default=True)),
            ],
        ),
        migrations.RemoveField(
            model_name='form1h',
            name='articulo',
        ),
        migrations.RemoveField(
            model_name='form1h',
            name='cantidad',
        ),
        migrations.RemoveField(
            model_name='form1h',
            name='precio_total_ingreso',
        ),
        migrations.RemoveField(
            model_name='form1h',
            name='precio_unitario',
        ),
        migrations.RemoveField(
            model_name='form1h',
            name='renglon',
        ),
        migrations.AddField(
            model_name='detallefactura',
            name='renglon',
            field=models.PositiveIntegerField(default=2),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='form1h',
            name='dependencia',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='almacen_app.dependencia'),
        ),
        migrations.AddField(
            model_name='form1h',
            name='programa',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='almacen_app.programa'),
        ),
    ]
