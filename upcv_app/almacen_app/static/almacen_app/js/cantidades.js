/* Formatting for visible physical quantities only. Never use for input values/money. */
(function (root) {
  'use strict';
  function formatoCantidad(value) {
    if (value === null || value === undefined || value === '') return '0';
    const text = String(value).trim();
    const match = text.match(/^([+-]?)(\d*)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/);
    if (!match || !(match[2] || match[3])) return String(value);
    const exponent = Number(match[4] || 0);
    if (!Number.isSafeInteger(exponent) || Math.abs(exponent) > 10000) return String(value);
    const digits = (match[2] || '') + (match[3] || '');
    const point = (match[2] || '').length + exponent;
    let integer, fraction;
    if (point <= 0) {
      integer = '0'; fraction = '0'.repeat(-point) + digits;
    } else if (point >= digits.length) {
      integer = digits + '0'.repeat(point - digits.length); fraction = '';
    } else {
      integer = digits.slice(0, point); fraction = digits.slice(point);
    }
    integer = integer.replace(/^0+(?=\d)/, '') || '0';
    fraction = fraction.replace(/0+$/, '');
    const sign = match[1] === '-' && (integer !== '0' || fraction) ? '-' : '';
    return sign + integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + (fraction ? '.' + fraction : '');
  }
  root.formatoCantidad = formatoCantidad;
  if (typeof module !== 'undefined' && module.exports) module.exports = formatoCantidad;
})(typeof window !== 'undefined' ? window : globalThis);
