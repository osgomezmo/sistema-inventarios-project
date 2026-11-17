<?php

namespace App\Support;

/** Listados {data, meta: {page, per_page, total}} con per_page entre 1 y 100 (G7). */
class Paginacion
{
    public const REGLAS = [
        'page' => ['sometimes', 'integer', 'min:1'],
        'per_page' => ['sometimes', 'integer', 'min:1', 'max:100'],
    ];

    /** @return array{0: int, 1: int} página y tamaño ya validados */
    public static function leer(array $datos): array
    {
        return [(int) ($datos['page'] ?? 1), (int) ($datos['per_page'] ?? 20)];
    }

    public static function respuesta(array $filas, int $page, int $perPage, int $total): array
    {
        return ['data' => $filas, 'meta' => ['page' => $page, 'per_page' => $perPage, 'total' => $total]];
    }
}
