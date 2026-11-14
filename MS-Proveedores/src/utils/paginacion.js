const { AppError } = require('./errors');

function leerPaginacion(query) {
  const detalles = {};
  let page = 1;
  let perPage = 20;

  if (query.page !== undefined) {
    const rawPage = String(query.page).trim();
    if (!/^\d+$/.test(rawPage) || parseInt(rawPage, 10) < 1) {
      detalles.page = ['El parámetro page debe ser un entero mayor o igual a 1.'];
    } else {
      page = parseInt(rawPage, 10);
    }
  }

  if (query.per_page !== undefined) {
    const rawPerPage = String(query.per_page).trim();
    const valor = parseInt(rawPerPage, 10);
    if (!/^\d+$/.test(rawPerPage) || valor < 1 || valor > 100) {
      detalles.per_page = ['El parámetro per_page debe ser un entero entre 1 y 100.'];
    } else {
      perPage = valor;
    }
  }

  if (Object.keys(detalles).length > 0) {
    throw new AppError(422, 'VALIDACION', 'Parámetros de paginación inválidos.', detalles);
  }

  return {
    page,
    perPage,
    offset: (page - 1) * perPage,
  };
}

function respuestaPaginada(data, page, perPage, total) {
  return {
    data,
    meta: {
      page,
      per_page: perPage,
      total,
    },
  };
}

module.exports = {
  leerPaginacion,
  respuestaPaginada,
};
