<?php

namespace App\Http\Controllers;

use App\Exceptions\ErrorApi;
use App\Models\Rol;
use App\Models\User;
use App\Support\MensajesValidacion;
use App\Support\Paginacion;
use App\Support\Serializador;
use Illuminate\Database\QueryException;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\Rule;

/** Administración de usuarios (G9). Todas las rutas exigen usuarios.gestionar. */
class UsuarioController extends Controller
{
    public function listar(Request $request): JsonResponse
    {
        $datos = $request->validate([
            'rol' => ['sometimes', 'string', Rule::in(Rol::pluck('codigo')->all())],
            'estado' => ['sometimes', 'string', Rule::in(['ACTIVO', 'INACTIVO'])],
            ...Paginacion::REGLAS,
        ], MensajesValidacion::todos());
        [$page, $perPage] = Paginacion::leer($datos);

        $consulta = User::query()->with('rol')
            ->when($datos['rol'] ?? null, fn ($q, $rol) => $q->whereHas('rol', fn ($r) => $r->where('codigo', $rol)))
            ->when($datos['estado'] ?? null, fn ($q, $estado) => $q->where('estado', $estado));

        $total = (clone $consulta)->count();
        $usuarios = $consulta->orderBy('name')->orderBy('id')
            ->offset(($page - 1) * $perPage)->limit($perPage)->get();

        return response()->json(Paginacion::respuesta(
            $usuarios->map(fn (User $u) => Serializador::usuario($u))->all(), $page, $perPage, $total,
        ));
    }

    public function crear(Request $request): JsonResponse
    {
        $datos = $this->validar($request, conPassword: true);
        $this->exigirCorreoLibre($datos['email']);

        try {
            $usuario = User::create([
                'name' => $datos['nombre'],
                'email' => $datos['email'],
                'password' => $datos['password'],  // el modelo la guarda hasheada
                'id_rol' => $datos['id_rol'],
            ]);
        } catch (QueryException $e) {
            // Otro alta con el mismo correo pudo ganar la carrera
            throw $this->esDuplicado($e) ? $this->correoDuplicado() : $e;
        }

        return response()->json(Serializador::usuario($usuario->fresh('rol')), 201);
    }

    public function ver(int $id): JsonResponse
    {
        return response()->json(Serializador::usuario($this->buscar($id)));
    }

    /** Reemplaza nombre, email y rol; nunca la contraseña ni el estado. */
    public function editar(Request $request, int $id): JsonResponse
    {
        $datos = $this->validar($request, conPassword: false);

        $usuario = DB::transaction(function () use ($request, $id, $datos) {
            $usuario = $this->buscar($id, bloquear: true);
            $this->exigirCorreoLibre($datos['email'], $usuario->id);

            $nuevoRol = Rol::find($datos['id_rol']);
            if ($this->esAdmin($usuario) && $nuevoRol->codigo !== 'admin') {
                if ($usuario->id === $request->user()->id) {
                    throw new ErrorApi('CONFLICTO', 'No puedes quitarte el rol de administrador.', 409);
                }
                $this->exigirOtroAdminActivo($usuario);
            }

            $usuario->update(['name' => $datos['nombre'], 'email' => $datos['email'], 'id_rol' => $nuevoRol->id_rol]);

            return $usuario;
        });

        return response()->json(Serializador::usuario($usuario->fresh('rol')));
    }

    /** Pasa a INACTIVO y revoca todos sus tokens. Idempotente. */
    public function inactivar(Request $request, int $id): JsonResponse
    {
        $usuario = DB::transaction(function () use ($request, $id) {
            $usuario = $this->buscar($id, bloquear: true);
            if ($usuario->id === $request->user()->id) {
                throw new ErrorApi('CONFLICTO', 'No puedes inactivarte a ti mismo.', 409);
            }
            if ($usuario->estado === 'ACTIVO' && $this->esAdmin($usuario)) {
                $this->exigirOtroAdminActivo($usuario);
            }
            $usuario->update(['estado' => 'INACTIVO']);
            $usuario->tokens()->delete();

            return $usuario;
        });

        return response()->json(Serializador::usuario($usuario->fresh('rol')));
    }

    /** Pasa a ACTIVO. Idempotente. */
    public function activar(int $id): JsonResponse
    {
        $usuario = $this->buscar($id);
        $usuario->update(['estado' => 'ACTIVO']);

        return response()->json(Serializador::usuario($usuario->fresh('rol')));
    }

    private function validar(Request $request, bool $conPassword): array
    {
        // Correo en minúsculas y sin espacios antes de validar
        if (is_string($request->input('email'))) {
            $request->merge(['email' => strtolower(trim($request->input('email')))]);
        }

        return $request->validate(array_filter([
            'nombre' => ['required', 'string', 'max:100'],
            'email' => ['required', 'string', 'email', 'max:255'],
            'password' => $conPassword ? ['required', 'string', 'min:8'] : null,
            'id_rol' => ['required', 'integer', Rule::exists('roles', 'id_rol')],
        ]), MensajesValidacion::todos());
    }

    private function buscar(int $id, bool $bloquear = false): User
    {
        $usuario = User::query()->when($bloquear, fn ($q) => $q->lockForUpdate())->find($id);

        return $usuario ?? throw new ErrorApi('NO_EXISTE', 'El usuario no existe.', 404);
    }

    private function exigirCorreoLibre(string $email, ?int $excepto = null): void
    {
        $existe = User::where('email', $email)->when($excepto, fn ($q) => $q->where('id', '!=', $excepto))->exists();
        if ($existe) {
            throw $this->correoDuplicado();
        }
    }

    private function correoDuplicado(): ErrorApi
    {
        return new ErrorApi('EMAIL_DUPLICADO', 'Ya existe un usuario con ese correo.', 409,
            ['email' => ['Ya existe un usuario con ese correo.']]);
    }

    private function esDuplicado(QueryException $e): bool
    {
        return ($e->errorInfo[1] ?? null) === 1062 || str_contains($e->getMessage(), 'UNIQUE constraint failed');
    }

    private function esAdmin(User $usuario): bool
    {
        return $usuario->rol?->codigo === 'admin';
    }

    /** El sistema nunca queda sin un administrador ACTIVO (G9). */
    private function exigirOtroAdminActivo(User $usuario): void
    {
        $otros = User::query()->lockForUpdate()
            ->where('id', '!=', $usuario->id)->where('estado', 'ACTIVO')
            ->whereHas('rol', fn ($q) => $q->where('codigo', 'admin'))
            ->count();
        if ($otros === 0) {
            throw new ErrorApi('CONFLICTO', 'Debe quedar al menos un administrador activo.', 409);
        }
    }
}
