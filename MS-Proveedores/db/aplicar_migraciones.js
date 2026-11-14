require('dotenv').config();

const fs = require('fs');
const path = require('path');
const mysql = require('mysql2/promise');
const { config } = require('../src/config/env');

async function aplicarMigraciones() {
  const conexion = await mysql.createConnection({
    host: config.db.host,
    port: config.db.port,
    user: config.db.user,
    password: config.db.password,
    database: config.db.database,
    timezone: 'Z',
    charset: 'utf8mb4',
    multipleStatements: true,
    connectTimeout: 5000,
  });

  try {
    await conexion.query(`
      CREATE TABLE IF NOT EXISTS migraciones_aplicadas (
        nombre VARCHAR(255) NOT NULL,
        aplicada_en DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
        PRIMARY KEY (nombre)
      ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
    `);

    const [aplicadasRows] = await conexion.query('SELECT nombre FROM migraciones_aplicadas');
    const aplicadas = new Set(aplicadasRows.map((row) => row.nombre));

    const dirMigraciones = __dirname;
    const archivos = fs
      .readdirSync(dirMigraciones)
      .filter((archivo) => archivo.endsWith('.sql'))
      .sort();

    for (const archivo of archivos) {
      if (aplicadas.has(archivo)) {
        continue;
      }

      const sql = fs.readFileSync(path.join(dirMigraciones, archivo), 'utf-8');
      await conexion.beginTransaction();
      try {
        await conexion.query(sql);
        await conexion.query('INSERT INTO migraciones_aplicadas (nombre) VALUES (?)', [archivo]);
        await conexion.commit();
        console.log(`[MS-Proveedores] Migración aplicada: ${archivo}`);
      } catch (err) {
        await conexion.rollback();
        throw err;
      }
    }

    console.log('[MS-Proveedores] Migraciones verificadas correctamente.');
  } finally {
    await conexion.end();
  }
}

if (require.main === module) {
  aplicarMigraciones().catch((err) => {
    console.error('[MS-Proveedores] Error aplicando migraciones:', err.message);
    process.exit(1);
  });
}

module.exports = { aplicarMigraciones };
