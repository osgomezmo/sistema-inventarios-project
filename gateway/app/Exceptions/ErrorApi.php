<?php

namespace App\Exceptions;

use RuntimeException;

/**
 * Error de negocio que se responde tal cual en /api/* con el formato
 * {"error": {"codigo", "mensaje", "detalles"}} (G7).
 */
class ErrorApi extends RuntimeException
{
    public function __construct(
        public readonly string $codigo,
        string $mensaje,
        public readonly int $status,
        public readonly array $detalles = [],
    ) {
        parent::__construct($mensaje);
    }
}
