-- Esquema inicial de ms-compras (base de datos: mscompras)
-- Motor InnoDB, UTF-8 estandar y marcas de tiempo en UTC.

CREATE TABLE IF NOT EXISTS ordenes_compra (
    id_orden INT NOT NULL AUTO_INCREMENT,
    numero VARCHAR(30) NULL,
    id_proveedor INT NOT NULL,
    id_bodega_destino INT NOT NULL,
    estado ENUM('BORRADOR', 'APROBADA', 'RECIBIDA_PARCIAL', 'RECIBIDA', 'ANULADA')
        NOT NULL DEFAULT 'BORRADOR',
    total DECIMAL(14, 2) NOT NULL DEFAULT 0.00,
    id_usuario_creador INT NOT NULL,
    id_usuario_aprobador INT NULL,
    motivo_anulacion VARCHAR(255) NULL,
    creada_en DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    aprobada_en DATETIME NULL,
    actualizada_en DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    PRIMARY KEY (id_orden),
    UNIQUE KEY uq_ordenes_numero (numero),
    KEY idx_ordenes_estado (estado),
    KEY idx_ordenes_proveedor (id_proveedor),
    KEY idx_ordenes_creada_en (creada_en)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS detalles_orden (
    id_detalle INT NOT NULL AUTO_INCREMENT,
    id_orden INT NOT NULL,
    sku VARCHAR(50) NOT NULL,
    cantidad_pedida DECIMAL(14, 3) NOT NULL,
    cantidad_recibida DECIMAL(14, 3) NOT NULL DEFAULT 0.000,
    cantidad_devuelta DECIMAL(14, 3) NOT NULL DEFAULT 0.000,
    precio_unitario DECIMAL(14, 2) NOT NULL,
    PRIMARY KEY (id_detalle),
    UNIQUE KEY uq_orden_sku (id_orden, sku),
    KEY idx_detalles_orden (id_orden),
    CONSTRAINT fk_detalles_orden
        FOREIGN KEY (id_orden) REFERENCES ordenes_compra (id_orden)
        ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS recepciones (
    id_recepcion INT NOT NULL AUTO_INCREMENT,
    id_orden INT NOT NULL,
    fecha DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    id_usuario INT NOT NULL,
    observaciones VARCHAR(300) NOT NULL DEFAULT '',
    PRIMARY KEY (id_recepcion),
    KEY idx_recepciones_orden (id_orden),
    KEY idx_recepciones_fecha (fecha),
    CONSTRAINT fk_recepciones_orden
        FOREIGN KEY (id_orden) REFERENCES ordenes_compra (id_orden)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS recepcion_detalle (
    id_recepcion INT NOT NULL,
    id_detalle INT NOT NULL,
    cantidad DECIMAL(14, 3) NOT NULL,
    PRIMARY KEY (id_recepcion, id_detalle),
    CONSTRAINT fk_rec_det_recepcion
        FOREIGN KEY (id_recepcion) REFERENCES recepciones (id_recepcion)
        ON DELETE CASCADE,
    CONSTRAINT fk_rec_det_detalle
        FOREIGN KEY (id_detalle) REFERENCES detalles_orden (id_detalle)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS devoluciones_proveedor (
    id_devolucion INT NOT NULL AUTO_INCREMENT,
    id_orden INT NOT NULL,
    fecha DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    motivo VARCHAR(255) NOT NULL,
    id_usuario INT NOT NULL,
    PRIMARY KEY (id_devolucion),
    KEY idx_devoluciones_orden (id_orden),
    KEY idx_devoluciones_fecha (fecha),
    CONSTRAINT fk_devoluciones_orden
        FOREIGN KEY (id_orden) REFERENCES ordenes_compra (id_orden)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS devolucion_detalle (
    id_devolucion INT NOT NULL,
    id_detalle INT NOT NULL,
    cantidad DECIMAL(14, 3) NOT NULL,
    PRIMARY KEY (id_devolucion, id_detalle),
    CONSTRAINT fk_dev_det_devolucion
        FOREIGN KEY (id_devolucion) REFERENCES devoluciones_proveedor (id_devolucion)
        ON DELETE CASCADE,
    CONSTRAINT fk_dev_det_detalle
        FOREIGN KEY (id_detalle) REFERENCES detalles_orden (id_detalle)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;
