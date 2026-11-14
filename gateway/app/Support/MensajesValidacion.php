<?php

namespace App\Support;

/** Mensajes en español para las reglas de validación que usa el gateway. */
class MensajesValidacion
{
    public static function todos(): array
    {
        return [
            'required' => 'Es obligatorio.',
            'string' => 'Debe ser texto.',
            'email' => 'Debe ser un correo válido.',
            'integer' => 'Debe ser un número entero.',
            'min.string' => 'Debe tener al menos :min caracteres.',
            'min.numeric' => 'Debe ser mayor o igual a :min.',
            'max.string' => 'Máximo :max caracteres.',
            'max.numeric' => 'Debe ser menor o igual a :max.',
            'different' => 'Debe ser distinta de la actual.',
            'in' => 'Debe ser uno de: :values.',
            'exists' => 'No existe.',
        ];
    }
}
