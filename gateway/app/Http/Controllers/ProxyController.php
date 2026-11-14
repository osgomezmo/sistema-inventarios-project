<?php

namespace App\Http\Controllers;

use App\Exceptions\ErrorApi;
use App\Http\Middleware\IdCorrelacion;
use App\Services\ProxyServicios;
use Illuminate\Http\Client\Response as RespuestaServicio;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Symfony\Component\HttpKernel\Exception\MethodNotAllowedHttpException;
use Symfony\Component\HttpKernel\Exception\NotFoundHttpException;

/**
 * Reenvía /api/{ruta} al microservicio que corresponde, después de validar la
 * ruta y el permiso del rol (G10).
 */
class ProxyController extends Controller
{
    /** Cabeceras de la respuesta del servicio que llegan al cliente. */
    private const CABECERAS_DE_VUELTA = ['Content-Type', 'Content-Disposition', 'Allow', 'Retry-After'];

    public function __construct(private readonly ProxyServicios $proxy) {}

    public function __invoke(Request $request): Response
    {
        $ruta = $this->rutaCruda($request);
        $decodificada = $this->validarRuta($ruta);
        $servicio = config('gateway.prefijos.'.explode('/', $decodificada)[0])
            ?? throw new NotFoundHttpException;

        $permiso = $this->permisoRequerido($request->method(), $decodificada);
        if ($permiso !== null && ! $request->user()->tienePermiso($permiso)) {
            throw new ErrorApi('SIN_PERMISO', 'No tienes permiso para esta operación.', 403);
        }

        $consulta = $request->server('QUERY_STRING');

        $respuesta = $this->proxy->enviar(
            $servicio,
            $request->method(),
            $ruta,
            $consulta,
            $request->user(),
            $request->attributes->get(IdCorrelacion::ATRIBUTO),
            $request->getContent(),
            $request->headers->get('Content-Type'),
        );

        return self::devolver($respuesta);
    }

    /** Copia el código, el cuerpo y solo las cabeceras permitidas. */
    public static function devolver(RespuestaServicio $respuesta): Response
    {
        $cabeceras = [];
        foreach (self::CABECERAS_DE_VUELTA as $nombre) {
            if ($respuesta->header($nombre) !== '') {
                $cabeceras[$nombre] = $respuesta->header($nombre);
            }
        }

        return response($respuesta->body(), $respuesta->status(), $cabeceras);
    }

    /** Ruta sin "/api/", tal como la escribió el cliente (sin decodificar). */
    private function rutaCruda(Request $request): string
    {
        $camino = (string) parse_url((string) $request->server('REQUEST_URI'), PHP_URL_PATH);

        return (string) preg_replace('#^/api/#', '', $camino);
    }

    /**
     * Rechaza con 404 las rutas con "..", "\", "//" o caracteres de control,
     * también si vienen codificados (una o dos veces).
     */
    private function validarRuta(string $ruta): string
    {
        $una = rawurldecode($ruta);
        foreach ([$ruta, $una, rawurldecode($una)] as $forma) {
            if ($forma === ''
                || str_contains($forma, '..')
                || str_contains($forma, '\\')
                || str_contains($forma, '//')
                || preg_match('/[\x00-\x1F\x7F]/', $forma)) {
                throw new NotFoundHttpException;
            }
        }

        return $una;
    }

    /**
     * Permiso de la primera regla que coincide (null = cualquier autenticado).
     * Si la ruta existe solo con otros métodos responde 405; si no existe, 404.
     */
    private function permisoRequerido(string $metodo, string $ruta): ?string
    {
        $permitidos = [];
        foreach (config('gateway.permisos') as [$metodos, $patron, $permiso]) {
            if (! preg_match($patron, $ruta)) {
                continue;
            }
            if (in_array($metodo, $metodos, true)) {
                return $permiso;
            }
            array_push($permitidos, ...$metodos);
        }

        if ($permitidos) {
            throw new MethodNotAllowedHttpException(array_values(array_unique($permitidos)));
        }
        throw new NotFoundHttpException;
    }
}
