const { AppError } = require('./errors');

const REGEX_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const REGEX_NIT = /^[0-9A-Za-z.-]{5,30}$/;
const REGEX_TELEFONO = /^\+?[\d\s()-]{7,30}$/;
const REGEX_SKU = /^[A-Za-z0-9_-]{2,50}$/;

function esTextoNoVacio(valor) {
  return typeof valor === 'string' && valor.trim().length > 0;
}

function validarTexto(detalles, campo, valor, { min = 1, max = 255, requerido = true } = {}) {
  if (valor === undefined || valor === null || (typeof valor === 'string' && valor.trim() === '')) {
    if (requerido) {
      detalles[campo] = [`El campo ${campo} es obligatorio.`];
    }
    return null;
  }

  if (typeof valor !== 'string') {
    detalles[campo] = [`El campo ${campo} debe ser una cadena de texto.`];
    return null;
  }

  const limpio = valor.trim();
  if (limpio.length < min) {
    detalles[campo] = [`El campo ${campo} debe tener al menos ${min} caracteres.`];
    return null;
  }
  if (limpio.length > max) {
    detalles[campo] = [`El campo ${campo} no puede superar ${max} caracteres.`];
    return null;
  }

  return limpio;
}

function validarEmail(detalles, campo, valor) {
  const limpio = validarTexto(detalles, campo, valor, { min: 5, max: 150 });
  if (!limpio) return null;
  if (!REGEX_EMAIL.test(limpio)) {
    detalles[campo] = ['El correo electrónico no tiene un formato válido.'];
    return null;
  }
  return limpio.toLowerCase();
}

function validarTelefono(detalles, campo, valor) {
  const limpio = validarTexto(detalles, campo, valor, { min: 7, max: 30 });
  if (!limpio) return null;
  if (!REGEX_TELEFONO.test(limpio)) {
    detalles[campo] = ['El teléfono debe contener entre 7 y 30 caracteres válidos.'];
    return null;
  }
  return limpio;
}

function validarIdEntero(rawId, nombreCampo = 'id') {
  const texto = String(rawId || '').trim();
  if (!/^\d+$/.test(texto)) {
    throw new AppError(400, 'PETICION_INVALIDA', `El parámetro ${nombreCampo} debe ser un entero positivo.`);
  }
  const numero = Number(texto);
  if (!Number.isSafeInteger(numero) || numero < 1 || numero > 2147483647) {
    throw new AppError(400, 'PETICION_INVALIDA', `El parámetro ${nombreCampo} debe ser un entero positivo válido.`);
  }
  return numero;
}

function validarSkuParam(rawSku) {
  if (!esTextoNoVacio(rawSku) || !REGEX_SKU.test(rawSku.trim())) {
    throw new AppError(400, 'PETICION_INVALIDA', 'El parámetro sku tiene un formato inválido.');
  }
  return rawSku.trim().toUpperCase();
}

function validarProveedorCrear(body) {
  const data = body && typeof body === 'object' && !Array.isArray(body) ? body : null;
  if (!data) {
    throw new AppError(400, 'PETICION_INVALIDA', 'El cuerpo de la petición debe ser un objeto JSON.');
  }

  const detalles = {};
  const nit = validarTexto(detalles, 'nit', data.nit, { min: 5, max: 30 });
  if (nit && !REGEX_NIT.test(nit)) {
    detalles.nit = ['El NIT solo puede contener dígitos, letras, puntos y guiones.'];
  }

  const razonSocial = validarTexto(detalles, 'razon_social', data.razon_social, { min: 2, max: 150 });
  const telefono = validarTelefono(detalles, 'telefono', data.telefono);
  const email = validarEmail(detalles, 'email', data.email);
  const direccion = validarTexto(detalles, 'direccion', data.direccion, { min: 3, max: 200 });

  let contactos = [];
  if (data.contactos !== undefined) {
    if (!Array.isArray(data.contactos)) {
      detalles.contactos = ['El campo contactos debe ser una lista.'];
    } else {
      contactos = data.contactos.map((c, idx) => {
        try {
          return validarContacto(c);
        } catch (err) {
          detalles[`contactos[${idx}]`] = [err.message || 'Contacto inválido.'];
          return null;
        }
      }).filter(Boolean);
    }
  }

  let productos = [];
  if (data.productos !== undefined) {
    if (!Array.isArray(data.productos)) {
      detalles.productos = ['El campo productos debe ser una lista.'];
    } else {
      productos = data.productos.map((p, idx) => {
        try {
          if (!p || typeof p !== 'object' || Array.isArray(p)) {
            throw new Error('Cada producto suministrado debe ser un objeto.');
          }
          const sku = validarSkuParam(p.sku);
          const validado = validarProductoSuministrado(p);
          return { sku, ...validado };
        } catch (err) {
          detalles[`productos[${idx}]`] = [err.message || 'Producto suministrado inválido.'];
          return null;
        }
      }).filter(Boolean);
    }
  }

  if (Object.keys(detalles).length > 0) {
    throw new AppError(422, 'VALIDACION', 'Datos inválidos para el proveedor.', detalles);
  }

  const resultado = {
    nit,
    razon_social: razonSocial,
    telefono,
    email,
    direccion,
  };
  if (contactos.length > 0) resultado.contactos = contactos;
  if (productos.length > 0) resultado.productos = productos;
  return resultado;
}

function validarProveedorActualizar(body) {
  const data = body && typeof body === 'object' && !Array.isArray(body) ? body : null;
  if (!data) {
    throw new AppError(400, 'PETICION_INVALIDA', 'El cuerpo de la petición debe ser un objeto JSON.');
  }

  const detalles = {};
  const razonSocial = validarTexto(detalles, 'razon_social', data.razon_social, { min: 2, max: 150 });
  const telefono = validarTelefono(detalles, 'telefono', data.telefono);
  const email = validarEmail(detalles, 'email', data.email);
  const direccion = validarTexto(detalles, 'direccion', data.direccion, { min: 3, max: 200 });

  if (Object.keys(detalles).length > 0) {
    throw new AppError(422, 'VALIDACION', 'Datos inválidos para actualizar el proveedor.', detalles);
  }

  return {
    razon_social: razonSocial,
    telefono,
    email,
    direccion,
  };
}

function validarContacto(body) {
  const data = body && typeof body === 'object' && !Array.isArray(body) ? body : null;
  if (!data) {
    throw new AppError(400, 'PETICION_INVALIDA', 'El cuerpo de la petición debe ser un objeto JSON.');
  }

  const detalles = {};
  const nombre = validarTexto(detalles, 'nombre', data.nombre, { min: 2, max: 120 });
  const cargo = validarTexto(detalles, 'cargo', data.cargo, { min: 2, max: 100 });
  const telefono = validarTelefono(detalles, 'telefono', data.telefono);
  const email = validarEmail(detalles, 'email', data.email);

  if (Object.keys(detalles).length > 0) {
    throw new AppError(422, 'VALIDACION', 'Datos inválidos para el contacto.', detalles);
  }

  return {
    nombre,
    cargo,
    telefono,
    email,
  };
}

function validarProductoSuministrado(body) {
  const data = body && typeof body === 'object' && !Array.isArray(body) ? body : null;
  if (!data) {
    throw new AppError(400, 'PETICION_INVALIDA', 'El cuerpo de la petición debe ser un objeto JSON.');
  }

  const detalles = {};
  let precioCompra = null;
  let diasEntrega = null;
  let estado = 'ACTIVO';

  if (
    data.precio_compra === undefined ||
    data.precio_compra === null ||
    typeof data.precio_compra === 'boolean' ||
    String(data.precio_compra).trim() === ''
  ) {
    detalles.precio_compra = ['El campo precio_compra es obligatorio.'];
  } else {
    const str = String(data.precio_compra).trim();
    const num = Number(str);
    if (!Number.isFinite(num) || num <= 0 || num > 999999999999.99 || !/^\d+(\.\d{1,2})?$/.test(str)) {
      detalles.precio_compra = ['El campo precio_compra debe ser un número mayor que 0 con máximo 2 decimales.'];
    } else {
      precioCompra = num.toFixed(2);
    }
  }

  if (
    data.dias_entrega === undefined ||
    data.dias_entrega === null ||
    typeof data.dias_entrega === 'boolean' ||
    String(data.dias_entrega).trim() === ''
  ) {
    detalles.dias_entrega = ['El campo dias_entrega es obligatorio.'];
  } else {
    const strDias = String(data.dias_entrega).trim();
    const num = Number(strDias);
    if (!/^\d+$/.test(strDias) || !Number.isSafeInteger(num) || num < 0 || num > 2147483647) {
      detalles.dias_entrega = ['El campo dias_entrega debe ser un número entero mayor o igual a 0.'];
    } else {
      diasEntrega = num;
    }
  }

  if (data.estado !== undefined) {
    const est = String(data.estado).trim().toUpperCase();
    if (est !== 'ACTIVO' && est !== 'INACTIVO') {
      detalles.estado = ['El campo estado debe ser ACTIVO o INACTIVO.'];
    } else {
      estado = est;
    }
  }

  if (Object.keys(detalles).length > 0) {
    throw new AppError(422, 'VALIDACION', 'Datos inválidos para el producto suministrado.', detalles);
  }

  return {
    precio_compra: precioCompra,
    dias_entrega: diasEntrega,
    estado,
  };
}

module.exports = {
  validarIdEntero,
  validarSkuParam,
  validarProveedorCrear,
  validarProveedorActualizar,
  validarContacto,
  validarProductoSuministrado,
};
