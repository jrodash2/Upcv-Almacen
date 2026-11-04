/* Asignación directa: el código es visible; el POST conserva la PK interna. */
(function () {
  'use strict';
  const form = document.getElementById('asignacion-form');
  if (!form) return;
  const search = document.getElementById('busqueda-articulo');
  const suggestions = document.getElementById('sugerencias-articulo');
  const articleId = document.getElementById('id_articulo');
  const quantity = document.getElementById('id_cantidad_asignada');
  const submit = document.getElementById('guardar-asignacion');
  const info = document.getElementById('informacion-articulo');
  const status = document.getElementById('estado-articulo');
  let available = 0;
  let version = 0;
  let timer;
  function reset() {
    articleId.value = '';
    info.hidden = true;
    available = 0;
    quantity.disabled = true;
    quantity.removeAttribute('max');
    submit.disabled = true;
    suggestions.replaceChildren();
    suggestions.style.display = 'none';
    ['stock-cantidad', 'disponible-cantidad'].forEach(id => {
      document.getElementById(id).textContent = '—';
    });
  }
  function validate() {
    const value = Number(quantity.value);
    const valid = !!articleId.value && available > 0 && Number.isInteger(value) && value > 0 && value <= available;
    quantity.setCustomValidity(quantity.value && !valid ? 'Ingrese una cantidad entera mayor a cero y no superior a la disponibilidad.' : '');
    submit.disabled = !valid;
    return valid;
  }
  function select(item) {
    version += 1; // Ignorar respuestas anteriores que aún estén en vuelo.
    clearTimeout(timer);
    articleId.value = item.id;
    search.value = item.codigo + ' — ' + item.nombre;
    ['codigo', 'descripcion', 'categoria', 'renglon'].forEach((field, i) => {
      document.getElementById('articulo-' + field).textContent =
        [item.codigo, item.nombre, item.categoria, item.renglon_presupuestario || 'S/R'][i];
    });
    const stock = item.existencias;
    available = Number(stock.disponible_para_division);
    document.getElementById('stock-cantidad').textContent = formatoCantidad(stock.existencia_fisica);
    document.getElementById('disponible-cantidad').textContent = formatoCantidad(stock.disponible_para_division);
    info.hidden = false;
    suggestions.style.display = 'none';
    quantity.disabled = !(available > 0);
    quantity.max = String(available);
    status.textContent = stock.requiere_revision ? 'Los compromisos históricos requieren revisión; no se modificaron saldos.' :
      available > 0 ? 'Disponibilidad consultada. Se comprobará de nuevo al guardar.' : 'Sin disponibilidad para nuevas asignaciones directas.';
    validate();
  }
  search.addEventListener('input', function () {
    const current = ++version;
    const query = search.value.trim();
    clearTimeout(timer);
    reset();
    status.textContent = query ? 'Buscando artículos…' : 'Seleccione un artículo.';
    if (!query) return;
    timer = setTimeout(async function () {
      try {
        const url = new URL(form.dataset.busquedaUrl, window.location.href);
        url.searchParams.set('q', query);
        url.searchParams.set('asignacion_directa', '1');
        const response = await fetch(url, {headers: {'Accept': 'application/json'}});
        if (!response.ok) throw new Error('No se pudo consultar el catálogo.');
        const data = await response.json();
        if (current !== version) return;
        suggestions.replaceChildren();
        data.forEach(item => {
          const option = document.createElement('button');
          option.type = 'button';
          option.textContent = item.text;
          option.className = 'dropdown-item text-wrap';
          option.addEventListener('click', function () { select(item); });
          suggestions.appendChild(option);
        });
        suggestions.style.display = data.length ? 'block' : 'none';
        status.textContent = data.length ? 'Seleccione un resultado.' : 'No se encontraron artículos.';
      } catch (error) {
        if (current !== version) return;
        status.textContent = 'No se pudo consultar el artículo. Intente buscar nuevamente.';
      }
    }, 200);
  });
  quantity.addEventListener('input', validate);
  form.addEventListener('submit', function (event) {
    if (!validate()) {
      event.preventDefault();
      status.textContent = 'Seleccione un artículo y una cantidad válida dentro de la disponibilidad.';
    }
  });
  reset();
  const initial = JSON.parse(document.getElementById('articulo-seleccionado').textContent);
  if (initial) select(initial);
})();
