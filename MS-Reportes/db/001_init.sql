-- Migración inicial de MS-Reportes (Figura 7 y Sección 3.1)
-- Todas las tablas usan InnoDB, utf8mb4 y marcas de tiempo UTC.

CREATE TABLE IF NOT EXISTS saldo_reporte (
    sku VARCHAR(64) NOT NULL,
    id_bodega INT NOT NULL,
    cantidad DECIMAL(14, 3) NOT NULL DEFAULT 0.000,
    costo_promedio DECIMAL(14, 4) NOT NULL DEFAULT 0.0000,
    valor_total DECIMAL(14, 2) NOT NULL DEFAULT 0.00,
    actualizado_en DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    PRIMARY KEY (sku, id_bodega),
    KEY idx_saldo_reporte_bodega (id_bodega),
    KEY idx_saldo_reporte_sku (sku)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS movimiento_diario (
    sku VARCHAR(64) NOT NULL,
    id_bodega INT NOT NULL,
    fecha DATE NOT NULL,
    entradas DECIMAL(14, 3) NOT NULL DEFAULT 0.000,
    salidas DECIMAL(14, 3) NOT NULL DEFAULT 0.000,
    PRIMARY KEY (sku, id_bodega, fecha),
    KEY idx_movimiento_diario_fecha (fecha),
    KEY idx_movimiento_diario_sku (sku)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS orden_pendiente (
    id_orden INT NOT NULL,
    numero VARCHAR(64) NULL,
    id_proveedor INT NOT NULL,
    estado VARCHAR(32) NOT NULL,
    total DECIMAL(14, 2) NOT NULL DEFAULT 0.00,
    actualizada_en DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    PRIMARY KEY (id_orden),
    KEY idx_orden_pendiente_estado (estado)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS alerta_stock (
    sku VARCHAR(64) NOT NULL,
    id_bodega INT NOT NULL,
    saldo DECIMAL(14, 3) NOT NULL DEFAULT 0.000,
    stock_minimo DECIMAL(14, 3) NOT NULL DEFAULT 0.000,
    activa TINYINT(1) NOT NULL DEFAULT 1,
    fecha DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    PRIMARY KEY (sku, id_bodega),
    KEY idx_alerta_stock_activa (activa)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS evento_procesado (
    id_evento VARCHAR(64) NOT NULL,
    tipo VARCHAR(64) NOT NULL,
    procesado_en DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    PRIMARY KEY (id_evento)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
