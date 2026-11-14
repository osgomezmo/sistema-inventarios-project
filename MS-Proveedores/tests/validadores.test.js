const {
  validarIdEntero,
  validarSkuParam,
  validarProveedorCrear,
  validarProveedorActualizar,
  validarContacto,
  validarProductoSuministrado,
} = require('../src/utils/validadores');
const { leerPaginacion, respuestaPaginada } = require('../src/utils/paginacion');
const { normalizarRol, requerirRoles } = require('../src/utils/roles');
const { AppError } = require('../src/utils/errors');

describe('MS-Proveedores | Validadores, paginacion y roles', () => {
  describe('Casos reales', () => {
    test('valida creacion de proveedor normalizando espacios y correo a minusculas', () => {
      const resultado = validarProveedorCrear({
        nit: '  900.123.456-7 ',
        razon_social: '  Distribuidora Andina S.A.S.  ',
        telefono: ' +57 310 555 0199 ',
        email: '  VENTAS@Andina.COM.CO  ',
        direccion: ' Calle 45 # 12-30, Bogota ',
      });

      expect(resultado).toEqual({
        nit: '900.123.456-7',
        razon_social: 'Distribuidora Andina S.A.S.',
        telefono: '+57 310 555 0199',
        email: 'ventas@andina.com.co',
        direccion: 'Calle 45 # 12-30, Bogota',
      });
    });

    test('valida actualizacion de proveedor sin exigir NIT', () => {
      const resultado = validarProveedorActualizar({
        razon_social: 'Logistica Central Ltda.',
        telefono: '(601) 444-8899',
        email: 'contacto@logisticacentral.co',
        direccion: 'Av. Dorado # 80-20',
      });

      expect(resultado).toEqual({
        razon_social: 'Logistica Central Ltda.',
        telefono: '(601) 444-8899',
        email: 'contacto@logisticacentral.co',
        direccion: 'Av. Dorado # 80-20',
      });
    });

    test('valida contacto y producto suministrado con 0 dias de entrega', () => {
      const contacto = validarContacto({
        nombre: 'Laura Gomez',
        cargo: 'Ejecutiva Comercial',
        telefono: '3001234567',
        email: 'laura@proveedor.com',
      });
      expect(contacto.email).toBe('laura@proveedor.com');

      const prod = validarProductoSuministrado({
        precio_compra: '12500.5',
        dias_entrega: 0,
      });
      expect(prod).toEqual({
        precio_compra: '12500.50',
        dias_entrega: 0,
        estado: 'ACTIVO',
      });
    });

    test('normaliza SKU, IDs enteros, roles de gateway y paginacion valida', () => {
      expect(validarIdEntero('42')).toBe(42);
      expect(validarSkuParam('  arr-001_col ')).toBe('ARR-001_COL');
      expect(normalizarRol('Administrador')).toBe('admin');
      expect(normalizarRol('Jefe de bodega')).toBe('jefe_bodega');
      expect(normalizarRol('JEFE')).toBe('jefe_bodega');
      expect(normalizarRol('Compras')).toBe('compras');
      expect(normalizarRol('GERENTE')).toBe('gerente');

      const pag = leerPaginacion({ page: '2', per_page: '50' });
      expect(pag).toEqual({ page: 2, perPage: 50, offset: 50 });
      expect(respuestaPaginada([{ id: 1 }], 2, 50, 51)).toEqual({
        data: [{ id: 1 }],
        meta: { page: 2, per_page: 50, total: 51 },
      });
    });
  });

  describe('Casos ilogicos', () => {
    test('rechaza cuerpo que no es objeto JSON (array, null, texto)', () => {
      for (const cuerpo of [null, [], 'texto', 123]) {
        expect(() => validarProveedorCrear(cuerpo)).toThrow(AppError);
        try {
          validarProveedorCrear(cuerpo);
        } catch (err) {
          expect(err.statusCode).toBe(400);
          expect(err.codigo).toBe('PETICION_INVALIDA');
        }
      }
    });

    test('rechaza NIT con simbolos prohibidos, correo sin TLD y telefono con letras', () => {
      expect(() =>
        validarProveedorCrear({
          nit: '900 123@!*',
          razon_social: '   ',
          telefono: 'no-es-telefono',
          email: 'usuario@localhost',
          direccion: 'Calle 10',
        })
      ).toThrow(AppError);

      try {
        validarProveedorCrear({
          nit: '900 123@!*',
          razon_social: '   ',
          telefono: 'no-es-telefono',
          email: 'usuario@localhost',
          direccion: 'Calle 10',
        });
      } catch (err) {
        expect(err.statusCode).toBe(422);
        expect(err.codigo).toBe('VALIDACION');
        expect(Object.keys(err.detalles)).toEqual(
          expect.arrayContaining(['nit', 'razon_social', 'telefono', 'email'])
        );
      }
    });

    test('rechaza booleanos o cadenas en blanco en precio_compra y dias_entrega', () => {
      for (const payload of [
        { precio_compra: true, dias_entrega: 3 },
        { precio_compra: 1000, dias_entrega: false },
        { precio_compra: '1000', dias_entrega: '   ' },
        { precio_compra: 'abc', dias_entrega: 'dos' },
        { precio_compra: 1500, dias_entrega: 5, estado: 'ELIMINADO' },
      ]) {
        try {
          validarProductoSuministrado(payload);
          throw new Error('Debio lanzar AppError');
        } catch (err) {
          expect(err).toBeInstanceOf(AppError);
          expect(err.statusCode).toBe(422);
          expect(err.codigo).toBe('VALIDACION');
        }
      }
    });

    test('rechaza SKU con espacios o caracteres especiales y rol no reconocido', () => {
      expect(() => validarSkuParam('SKU CON ESPACIOS!')).toThrow(AppError);
      expect(() => validarSkuParam('A')).toThrow(AppError);

      const middleware = requerirRoles(['admin']);
      const req = { usuario: { id: '1', rol: 'visitante_externo' } };
      let capturado = null;
      middleware(req, {}, (err) => {
        capturado = err;
      });
      expect(capturado).toBeInstanceOf(AppError);
      expect(capturado.statusCode).toBe(403);
      expect(capturado.codigo).toBe('SIN_PERMISO');
    });
  });

  describe('Casos fuera de rango', () => {
    test('rechaza IDs en cero, negativos, decimales y desbordamiento INT32', () => {
      for (const rawId of ['0', '-1', '1.5', 'abc', '2147483648', '999999999999999999999']) {
        try {
          validarIdEntero(rawId, 'id');
          throw new Error(`Debio fallar para ${rawId}`);
        } catch (err) {
          expect(err).toBeInstanceOf(AppError);
          expect(err.statusCode).toBe(400);
          expect(err.codigo).toBe('PETICION_INVALIDA');
        }
      }
    });

    test('rechaza longitudes debajo del minimo o por encima del maximo permitido', () => {
      try {
        validarProveedorCrear({
          nit: '1234',
          razon_social: 'X',
          telefono: '123456',
          email: 'a@b',
          direccion: 'ab',
        });
        throw new Error('Debio fallar por longitudes minimas');
      } catch (err) {
        expect(err.statusCode).toBe(422);
        expect(Object.keys(err.detalles).sort()).toEqual([
          'direccion',
          'email',
          'nit',
          'razon_social',
          'telefono',
        ]);
      }

      try {
        validarContacto({
          nombre: 'A'.repeat(121),
          cargo: 'B'.repeat(101),
          telefono: '3'.repeat(31),
          email: `${'u'.repeat(145)}@test.com`,
        });
        throw new Error('Debio fallar por longitudes maximas');
      } catch (err) {
        expect(err.statusCode).toBe(422);
        expect(Object.keys(err.detalles).sort()).toEqual([
          'cargo',
          'email',
          'nombre',
          'telefono',
        ]);
      }
    });

    test('rechaza precio_compra <= 0, con 3 decimales, infinito o superior a DECIMAL(14,2) y dias negativos/desbordados', () => {
      const casosInvalidos = [
        { precio_compra: 0, dias_entrega: 1 },
        { precio_compra: -25.5, dias_entrega: 1 },
        { precio_compra: 10.123, dias_entrega: 1 },
        { precio_compra: '1000000000000.00', dias_entrega: 1 },
        { precio_compra: Infinity, dias_entrega: 1 },
        { precio_compra: 100, dias_entrega: -1 },
        { precio_compra: 100, dias_entrega: 2.5 },
        { precio_compra: 100, dias_entrega: 2147483648 },
      ];

      for (const caso of casosInvalidos) {
        try {
          validarProductoSuministrado(caso);
          throw new Error(`Debio fallar para ${JSON.stringify(caso)}`);
        } catch (err) {
          expect(err.statusCode).toBe(422);
          expect(err.codigo).toBe('VALIDACION');
        }
      }
    });

    test('rechaza parametros de paginacion negativos, en cero o superiores a 100', () => {
      for (const query of [
        { page: '0' },
        { page: '-2' },
        { per_page: '0' },
        { per_page: '101' },
        { page: 'uno', per_page: 'diez' },
      ]) {
        try {
          leerPaginacion(query);
          throw new Error(`Debio fallar paginacion ${JSON.stringify(query)}`);
        } catch (err) {
          expect(err.statusCode).toBe(422);
          expect(err.codigo).toBe('VALIDACION');
        }
      }
    });
  });
});
