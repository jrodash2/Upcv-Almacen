from django.db import migrations, models


def asignar_codigos_articulos(apps, schema_editor):
    Articulo = apps.get_model('almacen_app', 'Articulo')
    for articulo in Articulo.objects.filter(codigo__isnull=True).order_by('id'):
        articulo.codigo = f"ART-{articulo.id:05d}"
        articulo.save(update_fields=['codigo'])


class Migration(migrations.Migration):

    dependencies = [
        ('almacen_app', '0050_articulo_renglon_presupuestario'),
    ]

    operations = [
        migrations.AddField(
            model_name='articulo',
            name='codigo',
            field=models.CharField(blank=True, help_text='Código único de referencia del artículo.', max_length=50, null=True, verbose_name='Código'),
        ),
        migrations.RunPython(asignar_codigos_articulos, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='articulo',
            name='codigo',
            field=models.CharField(help_text='Código único de referencia del artículo.', max_length=50, unique=True, verbose_name='Código'),
        ),
    ]
