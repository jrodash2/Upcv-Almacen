from django import forms
from django.contrib.auth.models import User, Group
from django.forms import CheckboxInput, DateInput
from django.core.exceptions import ValidationError
from .models import Ubicacion, UnidadDeMedida, Proveedor, Departamento, Categoria, Articulo, Departamento


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
        fields = ['codigo', 'nombre', 'descripcion', 'stock', 'precio', 'proveedor', 'categoria', 'unidad_medida', 'ubicacion', 'estado']
        widgets = {
            'codigo': forms.TextInput(attrs={'placeholder': 'Código del artículo', 'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre del artículo', 'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'placeholder': 'Descripción del artículo', 'rows': 4, 'cols': 40, 'class': 'form-control'}),
            'stock': forms.NumberInput(attrs={'placeholder': 'Stock del artículo', 'class': 'form-control'}),
            'precio': forms.NumberInput(attrs={'placeholder': 'Precio del artículo', 'class': 'form-control'}),
            'proveedor': forms.Select(attrs={'class': 'form-control'}),
            'categoria': forms.Select(attrs={'class': 'form-control'}),
            'unidad_medida': forms.Select(attrs={'class': 'form-control'}),
            'ubicacion': forms.Select(attrs={'class': 'form-control'}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
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