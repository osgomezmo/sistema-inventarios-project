-- Esquema inicial de base de datos para ms-proveedores (MySQL 8.4)

CREATE TABLE IF NOT EXISTS proveedores (
    id_proveedor INT NOT NULL AUTO_INCREMENT,
    nit VARCHAR(30) NOT NULL,
    razon_social VARCHAR(150) NOT NULL,
    telefono VARCHAR(30) NOT NULL,
    email VARCHAR(150) NOT NULL,
    direccion VARCHAR(200) NOT NULL,
    estado ENUM('ACTIVO', 'INACTIVO') NOT NULL DEFAULT 'ACTIVO',
    creado_en DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    actualizado_en DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    PRIMARY KEY (id_proveedor),
    UNIQUE KEY uq_proveedores_nit (nit),
    KEY idx_proveedores_razon_social (razon_social),
    KEY idx_proveedores_estado (estado)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS contactos (
    id_contacto INT NOT NULL AUTO_INCREMENT,
    id_proveedor INT NOT NULL,
    nombre VARCHAR(120) NOT NULL,
    cargo VARCHAR(100) NOT NULL,
    telefono VARCHAR(30) NOT NULL,
    email VARCHAR(150) NOT NULL,
    creado_en DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    PRIMARY KEY (id_contacto),
    KEY idx_contactos_proveedor (id_proveedor),
    CONSTRAINT fk_contactos_proveedor
        FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedor)
        ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS productos_suministrados (
    id_proveedor INT NOT NULL,
    sku VARCHAR(50) NOT NULL,
    precio_compra DECIMAL(14, 2) NOT NULL,
    dias_entrega INT NOT NULL,
    estado ENUM('ACTIVO', 'INACTIVO') NOT NULL DEFAULT 'ACTIVO',
    actualizado_en DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
    PRIMARY KEY (id_proveedor, sku),
    KEY idx_productos_suministrados_sku (sku),
    CONSTRAINT fk_productos_suministrados_proveedor
        FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedor)
        ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
