from django import forms
from django.contrib.auth.models import User, Group
from django.forms import CheckboxInput, DateInput
from django.core.exceptions import ValidationError
from .models import DetalleFactura, Ubicacion, UnidadDeMedida, Proveedor, Departamento, Categoria, Articulo, Departamento, Kardex, AsignacionDetalleFactura, Movimiento, FraseMotivacional, Serie, form1h, Dependencia, Programa

from django.db.models import Sum, F, Value
from django.db.models.functions import Coalesce

class AsignacionDetalleFacturaForm(forms.ModelForm):
    articulo = forms.ModelChoiceField(
        queryset=Articulo.objects.none(),  # Inicialmente vacío, se llenará en __init__
        label='Artículo'
    )
    destino = forms.ModelChoiceField(
        queryset=Departamento.objects.all(),
        label='Departamento'
    )

    class Meta:
        model = AsignacionDetalleFactura
        fields = ['articulo', 'cantidad_asignada', 'destino', 'descripcion']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Obtener artículos con stock total > 0 (considerando lo asignado)
        # 1. Sumar cantidades en DetalleFactura
        stock_por_articulo = DetalleFactura.objects.values('articulo').annotate(
            total_stock=Coalesce(Sum('cantidad'), 0)
        )

        # 2. Sumar cantidades asignadas
        asignado_por_articulo = AsignacionDetalleFactura.objects.values('articulo').annotate(
            total_asignado=Coalesce(Sum('cantidad_asignada'), 0)
        )

        # 3. Construir diccionario de stock disponible por artículo
        stock_disponible = {}
        for item in stock_por_articulo:
            articulo_id = item['articulo']
            total_stock = item['total_stock']
            total_asignado = next((a['total_asignado'] for a in asignado_por_articulo if a['articulo'] == articulo_id), 0)
            disponible = total_stock - total_asignado
            if disponible > 0:
                stock_disponible[articulo_id] = disponible

        # 4. Filtrar artículos cuyo id está en stock_disponible (es decir, con stock > 0)
        queryset_filtrado = Articulo.objects.filter(id__in=stock_disponible.keys())

        self.fields['articulo'].queryset = queryset_filtrado


class DetalleFacturaForm(forms.ModelForm):
    class Meta:
        model = DetalleFactura
        fields = ['articulo', 'cantidad', 'precio_unitario', 'renglon', 'id_linea']
        widgets = {
            'articulo': forms.Select(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control'}),
            'renglon': forms.NumberInput(attrs={'class': 'form-control'}),
            'id_linea': forms.HiddenInput(),  # Esto para no mostrarlo en el formulario
        }

    def __init__(self, *args, **kwargs):
        form1h_instance = kwargs.pop('form1h_instance', None)  # Obtener el form1h de la vista
        super(DetalleFacturaForm, self).__init__(*args, **kwargs)
        if form1h_instance:
            self.instance.form1h = form1h_instance  # Asignar el form1h automáticamente

class SerieForm(forms.ModelForm):
    class Meta:
        model = Serie
        fields = ['serie', 'numero_inicial', 'numero_final', 'activo']
        widgets = {
            'serie': forms.TextInput(attrs={
                'placeholder': 'Código de la serie',
                'class': 'form-control'
            }),
            'numero_inicial': forms.NumberInput(attrs={
                'placeholder': 'Número inicial',
                'class': 'form-control'
            }),
            'numero_final': forms.NumberInput(attrs={
                'placeholder': 'Número final',
                'class': 'form-control'
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        super(SerieForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'

class Form1hForm(forms.ModelForm):
    cantidad_detalles = forms.IntegerField(
        min_value=1,
        required=True,
        label="Cantidad de Detalles",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej. 5'
        })
    )

    class Meta:
        model = form1h
        fields = [
            'proveedor', 'nit_proveedor', 'proveedor_nombre', 'telefono_proveedor',
            'direccion_proveedor', 'numero_factura', 'dependencia', 'programa',
            'orden_compra', 'patente', 'fecha_factura', 'cantidad_detalles'  # ✅ AÑADIDO AQUÍ
        ]
        widgets = {
            'proveedor': forms.Select(attrs={'class': 'form-control'}),
            'nit_proveedor': forms.TextInput(attrs={'placeholder': 'NIT del proveedor', 'class': 'form-control'}),
            'proveedor_nombre': forms.TextInput(attrs={'placeholder': 'Nombre del proveedor', 'class': 'form-control'}),
            'telefono_proveedor': forms.TextInput(attrs={'placeholder': 'Teléfono del proveedor', 'class': 'form-control'}),
            'direccion_proveedor': forms.TextInput(attrs={'placeholder': 'Dirección del proveedor', 'class': 'form-control'}),
            'numero_factura': forms.TextInput(attrs={'placeholder': 'Número de factura', 'class': 'form-control'}),
            'dependencia': forms.Select(attrs={'class': 'form-control'}),
            'programa': forms.Select(attrs={'class': 'form-control'}),
            'orden_compra': forms.TextInput(attrs={'placeholder': 'Orden de compra', 'class': 'form-control'}),
            'patente': forms.TextInput(attrs={'placeholder': 'Patente', 'class': 'form-control'}),
            'fecha_factura': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }


    def __init__(self, *args, **kwargs):
        super(Form1hForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'

class DepartamentoForm(forms.ModelForm):
    class Meta:
        model = Departamento
        fields = ['id_departamento', 'nombre', 'descripcion']
        widgets = {
            'id_departamento': forms.TextInput(attrs={'placeholder': 'ID del departamento', 'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre del departamento', 'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'placeholder': 'Descripción del departamento', 'rows': 4, 'cols': 40, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super(DepartamentoForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'


class ArticuloForm(forms.ModelForm):
    class Meta:
        model = Articulo
        fields = ['nombre', 'categoria', 'unidad_medida', 'ubicacion']
        widgets = {
            
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre del artículo', 'class': 'form-control'}),
            'categoria': forms.Select(attrs={'class': 'form-control'}),
            'unidad_medida': forms.Select(attrs={'class': 'form-control'}),
            'ubicacion': forms.Select(attrs={'class': 'form-control'}),
           
        }

    def __init__(self, *args, **kwargs):
        super(ArticuloForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'


class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ['nombre', 'direccion', 'telefono', 'email', 'nit']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre del proveedor', 'class': 'form-control'}),
            'direccion': forms.TextInput(attrs={'placeholder': 'Dirección del proveedor', 'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'placeholder': 'Teléfono del proveedor', 'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email del proveedor', 'class': 'form-control'}),
            'nit': forms.TextInput(attrs={'placeholder': 'NIT del proveedor', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super(ProveedorForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre de la categoría', 'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'placeholder': 'Descripción de la categoría', 'rows': 4, 'cols': 40, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super(CategoriaForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'


class UnidadDeMedidaForm(forms.ModelForm):
    class Meta:
        model = UnidadDeMedida
        fields = ['nombre', 'simbolo']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre de la unidad', 'class': 'form-control'}),
            'simbolo': forms.TextInput(attrs={'placeholder': 'Símbolo de la unidad', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super(UnidadDeMedidaForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'


class UbicacionForm(forms.ModelForm):
    class Meta:
        model = Ubicacion
        fields = ['nombre', 'descripcion', 'activo']  # Ensure 'activo' is included
        widgets = {
            'descripcion': forms.Textarea(attrs={'placeholder': 'Descripcion de la ubicacion','rows': 4, 'cols': 40}),
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre de la ubicacion', 'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super(UbicacionForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'


class UserForm(forms.ModelForm):
    new_password = forms.CharField(
        required=True, 
        widget=forms.PasswordInput, 
        label="Contraseña"
    )
    confirm_password = forms.CharField(
        required=True, 
        widget=forms.PasswordInput, 
        label="Confirmar Contraseña"
    )
    group = forms.ModelChoiceField(queryset=Group.objects.all(), required=True, label="Grupo")

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']  # No incluimos 'password' aquí

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        # Verificar si las contraseñas coinciden
        if password and confirm_password:
            if password != confirm_password:
                raise ValidationError("Las contraseñas no coinciden.")
        
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        
        # Si se proporciona una nueva contraseña, la seteamos
        if self.cleaned_data.get("new_password"):
            user.set_password(self.cleaned_data["new_password"])

        if commit:
            user.save()
            user.groups.add(self.cleaned_data['group'])

        return user
 
    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        
        
        # Agregar la clase 'form-control' a todos los campos del formulario
        for field in self.fields.values():
            field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'