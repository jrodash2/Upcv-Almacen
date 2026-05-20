from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


def crear_grupo_gestor(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name='Gestor')


class Migration(migrations.Migration):

    dependencies = [
        ('almacen_app', '0045_kardex_numero_kardex'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SolicitudRequerimiento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('estado', models.CharField(choices=[('pendiente', 'Pendiente'), ('convertida', 'Convertida'), ('rechazada', 'Rechazada')], default='pendiente', max_length=20)),
                ('observaciones', models.TextField(blank=True, null=True)),
                ('motivo_rechazo', models.TextField(blank=True, null=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('convertido_en', models.DateTimeField(blank=True, null=True)),
                ('rechazado_en', models.DateTimeField(blank=True, null=True)),
                ('convertido_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='solicitudes_convertidas', to=settings.AUTH_USER_MODEL)),
                ('departamento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='almacen_app.departamento')),
                ('rechazado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='solicitudes_rechazadas', to=settings.AUTH_USER_MODEL)),
                ('requerimiento', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='solicitudes_origen', to='almacen_app.requerimiento')),
                ('usuario_solicitante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='solicitudes_requerimiento', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='DetalleSolicitudRequerimiento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cantidad', models.PositiveIntegerField()),
                ('observacion', models.TextField(blank=True, null=True)),
                ('articulo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='almacen_app.articulo')),
                ('solicitud', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detalles', to='almacen_app.solicitudrequerimiento')),
            ],
        ),
        migrations.RunPython(crear_grupo_gestor, migrations.RunPython.noop),
    ]
