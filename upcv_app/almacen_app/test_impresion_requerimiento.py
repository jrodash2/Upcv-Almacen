"""El PDF identifica la solicitud de origen y conserva las firmas existentes."""
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from pypdf import PdfReader
from reportlab.pdfbase.pdfmetrics import stringWidth

from .models import Departamento, Requerimiento, SolicitudRequerimiento


class ImpresionRequerimientoTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username='impresion_requerimiento')
        self.usuario.groups.add(Group.objects.get_or_create(name='Administrador')[0])
        self.client.force_login(self.usuario)
        self.departamento = Departamento.objects.create(id_departamento='IMP', nombre='Impresión')
        self.requerimiento = Requerimiento.objects.create(
            id=902, departamento=self.departamento, creado_por=self.usuario)
        self.url = reverse('almacen:exportar_requerimiento_pdf', args=[self.requerimiento.pk])

    def pdf(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        return PdfReader(BytesIO(response.content))

    def test_correlativo_es_el_de_la_solicitud_y_recibido_esta_centrado(self):
        SolicitudRequerimiento.objects.create(id=17, usuario_solicitante=self.usuario,
            departamento=self.departamento, estado='convertida', requerimiento=self.requerimiento)
        pdf = self.pdf()
        texto = '\n'.join(page.extract_text() for page in pdf.pages)
        self.assertIn('0017', texto)
        self.assertNotIn('REQ-000902', texto)
        for firma in ['ENTREGADO POR', 'AUTORIZADO POR', 'RECIBIDO POR',
                      'Departamento Financiero', 'Vo. Bo. Coordinación', 'Entrega Sección de Almacén']:
            self.assertIn(firma, texto)
        posiciones = {}
        def visitor(text, cm, tm, font, size):
            for firma in ['ENTREGADO POR', 'RECIBIDO POR', 'Departamento Financiero']:
                if firma in text:
                    posiciones[firma] = (
                        cm[0] * tm[4] + cm[2] * tm[5] + cm[4],
                        cm[1] * tm[4] + cm[3] * tm[5] + cm[5],
                        size * abs(cm[0]),
                    )
        pdf.pages[0].extract_text(visitor_text=visitor)
        x, y, size = posiciones['RECIBIDO POR']
        ancho = stringWidth('RECIBIDO POR', 'Helvetica-Bold', size)
        self.assertAlmostEqual(x + ancho / 2, float(pdf.pages[0].mediabox.width) / 2, delta=3)
        self.assertGreater(posiciones['ENTREGADO POR'][1], y)
        self.assertGreater(y, posiciones['Departamento Financiero'][1])

    def test_sin_solicitud_no_presenta_correlativo_del_requerimiento(self):
        texto = '\n'.join(page.extract_text() for page in self.pdf().pages)
        self.assertIn('Sin solicitud vinculada', texto)
        self.assertNotIn('REQ-000902', texto)
