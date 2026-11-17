-- Tablas de bodegas, saldos, traslados, movimientos y eventos procesados.
-- Las fechas se guardan en UTC. Cantidades DECIMAL(14,3), costos DECIMAL(14,4)
-- y valores DECIMAL(18,2): cantidad por costo puede superar DECIMAL(14,2).
-- Los CHECK son defensa en profundidad: el código valida las mismas reglas.

CREATE TABLE IF NOT EXISTS bodegas (
    id_bodega INT NOT NULL AUTO_INCREMENT,
    codigo VARCHAR(30) NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    direccion VARCHAR(255) NOT NULL,
    estado ENUM('ACTIVO', 'INACTIVO') NOT NULL DEFAULT 'ACTIVO',
    creado_en DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    PRIMARY KEY (id_bodega),
    UNIQUE KEY uq_bodegas_codigo (codigo),
    KEY idx_bodegas_estado (estado)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

-- Saldo de un producto en una bodega. stock_minimo es la copia del mínimo del
-- producto (se refresca en cada movimiento). actualizado_en lo fija el código en
-- cada UPDATE: MySQL solo admite CURRENT_TIMESTAMP en ON UPDATE.
CREATE TABLE IF NOT EXISTS saldos (
    id_saldo INT NOT NULL AUTO_INCREMENT,
    sku VARCHAR(50) NOT NULL,
    id_bodega INT NOT NULL,
    cantidad DECIMAL(14, 3) NOT NULL DEFAULT 0,
    costo_promedio DECIMAL(14, 4) NOT NULL DEFAULT 0,
    stock_minimo DECIMAL(14, 3) NOT NULL DEFAULT 0,
    actualizado_en DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    PRIMARY KEY (id_saldo),
    UNIQUE KEY uq_saldos_sku_bodega (sku, id_bodega),
    KEY idx_saldos_bodega (id_bodega),
    -- No hay saldo negativo (RF04)
    CONSTRAINT ck_saldos_cantidad CHECK (cantidad >= 0),
    -- El costo promedio nunca es negativo
    CONSTRAINT ck_saldos_costo CHECK (costo_promedio >= 0),
    CONSTRAINT fk_saldos_bodega FOREIGN KEY (id_bodega) REFERENCES bodegas (id_bodega)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS traslados (
    id_traslado INT NOT NULL AUTO_INCREMENT,
    sku VARCHAR(50) NOT NULL,
    id_bodega_origen INT NOT NULL,
    id_bodega_destino INT NOT NULL,
    cantidad DECIMAL(14, 3) NOT NULL,
    motivo VARCHAR(255) NULL,
    id_usuario INT NOT NULL,
    fecha DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    PRIMARY KEY (id_traslado),
    KEY idx_traslados_sku (sku),
    KEY idx_traslados_fecha (fecha),
    -- Un traslado siempre mueve una cantidad positiva
    CONSTRAINT ck_traslados_cantidad CHECK (cantidad > 0),
    -- El origen y el destino deben ser bodegas distintas
    CONSTRAINT ck_traslados_bodegas CHECK (id_bodega_origen <> id_bodega_destino),
    CONSTRAINT fk_traslados_origen FOREIGN KEY (id_bodega_origen) REFERENCES bodegas (id_bodega),
    CONSTRAINT fk_traslados_destino FOREIGN KEY (id_bodega_destino) REFERENCES bodegas (id_bodega)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

-- Kardex. Es inmutable: el código solo inserta y nunca hace UPDATE ni DELETE,
-- porque cada fila es la historia auditable de un cambio de saldo (RF10).
-- Un error se corrige con un nuevo movimiento de ajuste, no editando el anterior.
CREATE TABLE IF NOT EXISTS movimientos (
    id_movimiento BIGINT NOT NULL AUTO_INCREMENT,
    sku VARCHAR(50) NOT NULL,
    id_bodega INT NOT NULL,
    tipo ENUM(
        'ENTRADA_COMPRA', 'AJUSTE_POSITIVO', 'TRASLADO_ENTRADA', 'DEVOLUCION_CLIENTE',
        'SALIDA', 'AJUSTE_NEGATIVO', 'TRASLADO_SALIDA', 'DEVOLUCION_PROVEEDOR'
    ) NOT NULL,
    cantidad DECIMAL(14, 3) NOT NULL,
    costo_unitario DECIMAL(14, 4) NOT NULL,
    saldo_resultante DECIMAL(14, 3) NOT NULL,
    costo_promedio DECIMAL(14, 4) NOT NULL,
    valor_resultante DECIMAL(18, 2) NOT NULL,
    motivo VARCHAR(255) NULL,
    documento_referencia VARCHAR(100) NULL,
    id_usuario INT NOT NULL,
    id_traslado INT NULL,
    fecha DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    PRIMARY KEY (id_movimiento),
    KEY idx_movimientos_kardex (sku, id_bodega, fecha, id_movimiento),
    KEY idx_movimientos_fecha (fecha),
    KEY idx_movimientos_tipo (tipo),
    KEY idx_movimientos_traslado (id_traslado),
    -- La cantidad es siempre positiva: el tipo indica si entra o sale
    CONSTRAINT ck_movimientos_cantidad CHECK (cantidad > 0),
    CONSTRAINT fk_movimientos_bodega FOREIGN KEY (id_bodega) REFERENCES bodegas (id_bodega),
    CONSTRAINT fk_movimientos_traslado FOREIGN KEY (id_traslado) REFERENCES traslados (id_traslado)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

-- Eventos de RabbitMQ ya aplicados, para que los consumidores sean idempotentes
CREATE TABLE IF NOT EXISTS eventos_procesados (
    id_evento CHAR(36) NOT NULL,
    tipo VARCHAR(60) NOT NULL,
    procesado_en DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    PRIMARY KEY (id_evento)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
