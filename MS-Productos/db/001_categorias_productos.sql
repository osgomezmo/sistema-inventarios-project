-- Tablas de categorías y productos de ms-productos.
-- Las fechas se guardan en UTC.

CREATE TABLE IF NOT EXISTS categorias (
    id_categoria INT NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL,
    descripcion VARCHAR(255) NULL,
    id_categoria_padre INT NULL,
    estado ENUM('ACTIVO', 'INACTIVO') NOT NULL DEFAULT 'ACTIVO',
    creado_en DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    PRIMARY KEY (id_categoria),
    -- No hay UNIQUE (id_categoria_padre, nombre): MySQL admite varios NULL en un
    -- índice único, así que no cubriría las categorías raíz. El nombre repetido
    -- en el mismo nivel se valida en el endpoint (409 NOMBRE_REPETIDO).
    KEY idx_categorias_padre (id_categoria_padre),
    KEY idx_categorias_estado (estado),
    CONSTRAINT fk_categorias_padre
        FOREIGN KEY (id_categoria_padre) REFERENCES categorias (id_categoria)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS productos (
    id_producto INT NOT NULL AUTO_INCREMENT,
    sku VARCHAR(50) NOT NULL,
    nombre VARCHAR(150) NOT NULL,
    descripcion TEXT NULL,
    marca VARCHAR(100) NOT NULL,
    id_categoria INT NOT NULL,
    unidad_medida ENUM('UNIDAD', 'KILO', 'LITRO') NOT NULL,
    precio_venta DECIMAL(14, 2) NOT NULL,
    stock_minimo DECIMAL(14, 3) NOT NULL,
    estado ENUM('ACTIVO', 'INACTIVO') NOT NULL DEFAULT 'ACTIVO',
    creado_en DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    PRIMARY KEY (id_producto),
    UNIQUE KEY uq_productos_sku (sku),
    KEY idx_productos_nombre (nombre),
    KEY idx_productos_categoria (id_categoria),
    KEY idx_productos_estado (estado),
    KEY idx_productos_precio (precio_venta),
    CONSTRAINT fk_productos_categoria
        FOREIGN KEY (id_categoria) REFERENCES categorias (id_categoria)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
