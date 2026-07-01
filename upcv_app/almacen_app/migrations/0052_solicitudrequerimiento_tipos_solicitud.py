from django.db import migrations, models


def copiar_tipo_a_tipos(apps, schema_editor):
    SolicitudRequerimiento = apps.get_model('almacen_app', 'SolicitudRequerimiento')
    for solicitud in SolicitudRequerimiento.objects.all().only('id', 'tipo_solicitud', 'tipos_solicitud'):
        if not solicitud.tipos_solicitud and solicitud.tipo_solicitud:
            solicitud.tipos_solicitud = solicitud.tipo_solicitud
            solicitud.save(update_fields=['tipos_solicitud'])


class Migration(migrations.Migration):

    dependencies = [
        ('almacen_app', '0051_articulo_codigo'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitudrequerimiento',
            name='tipos_solicitud',
            field=models.CharField(blank=True, help_text='Tipos seleccionados: bienes, suministros, insumos.', max_length=100, verbose_name='Tipos de solicitud'),
        ),
        migrations.RunPython(copiar_tipo_a_tipos, migrations.RunPython.noop),
    ]
