from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('almacen_app', '0046_solicitudrequerimiento'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='requerimiento',
            name='fecha_despachado',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='requerimiento',
            name='fecha_rechazado',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='requerimiento',
            name='despachado_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='requerimientos_despachados', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='requerimiento',
            name='rechazado_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='requerimientos_rechazados', to=settings.AUTH_USER_MODEL),
        ),
    ]
