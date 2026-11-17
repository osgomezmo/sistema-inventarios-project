<?php

namespace App\Http\Controllers;

use App\Exceptions\ErrorApi;
use App\Models\User;
use App\Support\MensajesValidacion;
use App\Support\Serializador;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Illuminate\Support\Facades\Hash;
use Illuminate\Validation\ValidationException;

/** Autenticación con tokens de Sanctum (G8). */
class AuthController extends Controller
{
    /** Hash de relleno para que un correo inexistente tarde lo mismo que uno real. */
    private const HASH_RELLENO = '$2y$12$Oa9F4PWMTVXKBiTMSnbFWOPrM4YNELWRSXKbT2E/LKkAIyWBcEh8m';

    public function login(Request $request): JsonResponse
    {
        $datos = $request->validate([
            'email' => ['required', 'string', 'email'],
            'password' => ['required', 'string'],
        ], MensajesValidacion::todos());

        $usuario = User::where('email', strtolower(trim($datos['email'])))->first();
        $valida = Hash::check($datos['password'], $usuario?->password ?? self::HASH_RELLENO);

        // El mismo mensaje para correo inexistente y contraseña errada
        if ($usuario === null || ! $valida) {
            throw new ErrorApi('CREDENCIALES_INVALIDAS', 'Correo o contraseña incorrectos.', 401);
        }
        if ($usuario->estado !== 'ACTIVO') {
            throw new ErrorApi('USUARIO_INACTIVO', 'El usuario está inactivo.', 403);
        }

        return response()->json([
            'token' => $usuario->createToken('api')->plainTextToken,
            'usuario' => Serializador::usuario($usuario),
        ]);
    }

    /** Revoca solo el token con el que se hizo la petición. */
    public function logout(Request $request): Response
    {
        $request->user()->currentAccessToken()->delete();

        return response()->noContent();
    }

    public function me(Request $request): JsonResponse
    {
        $usuario = $request->user();

        return response()->json([
            ...Serializador::usuario($usuario),
            'permisos' => $usuario->codigosDePermisos(),
        ]);
    }

    /** Cambia la contraseña y revoca los demás tokens; el actual sigue sirviendo. */
    public function cambiarPassword(Request $request): Response
    {
        $datos = $request->validate([
            'password_actual' => ['required', 'string'],
            'password_nueva' => ['required', 'string', 'min:8', 'different:password_actual'],
        ], MensajesValidacion::todos());

        $usuario = $request->user();
        if (! Hash::check($datos['password_actual'], $usuario->password)) {
            throw ValidationException::withMessages(['password_actual' => ['La contraseña actual no es correcta.']]);
        }

        $usuario->update(['password' => $datos['password_nueva']]);
        $actual = $usuario->currentAccessToken();
        $usuario->tokens()->where('id', '!=', $actual->id)->delete();

        return response()->noContent();
    }
}
