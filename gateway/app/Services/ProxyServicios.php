<?php

namespace App\Services;

use App\Exceptions\ErrorApi;
use App\Models\User;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\Response as RespuestaServicio;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

/**
 * Llama a un microservicio con la identidad ya verificada por el gateway (G10).
 * Nunca reenvía las credenciales del cliente: el servicio recibe el token de
 * servicio, X-User-Id, X-User-Role (código del rol) y X-Correlation-Id.
 */
class ProxyServicios
{
    private const TOKENS_DE_EJEMPLO = ['', 'cambia-este-token'];

    /**
     * @param  string  $ruta  ruta interna sin barra inicial, tal como la envió el cliente
     * @param  string|null  $consulta  cadena de consulta cruda, sin "?"
     */
    public function enviar(
        string $servicio,
        string $metodo,
        string $ruta,
        ?string $consulta,
        User $usuario,
        string $idCorrelacion,
        string $cuerpo = '',
        ?string $tipoContenido = null,
    ): RespuestaServicio {
        $token = (string) config('gateway.service_token');
        if (in_array(trim($token), self::TOKENS_DE_EJEMPLO, true)) {
            Log::error('Proxy sin token de servicio configurado', ['servicio' => $servicio, 'correlacion' => $idCorrelacion]);
            throw $this->noDisponible();
        }

        $url = rtrim((string) config("gateway.servicios.$servicio"), '/').'/'.$ruta;
        if ($consulta !== null && $consulta !== '') {
            $url .= '?'.$consulta;
        }

        $peticion = Http::withHeaders([
            'Authorization' => 'Bearer '.$token,
            'X-User-Id' => (string) $usuario->id,
            'X-User-Role' => (string) $usuario->rol?->codigo,
            'X-Correlation-Id' => $idCorrelacion,
            'Accept' => 'application/json',
        ])->timeout(config('gateway.timeout'))->connectTimeout(config('gateway.timeout'));

        if ($cuerpo !== '') {
            $peticion = $peticion->withBody($cuerpo, $tipoContenido ?: 'application/json');
        }

        try {
            return $peticion->send($metodo, $url);
        } catch (ConnectionException $e) {
            // Sin token, cabeceras ni cuerpo en el log
            Log::warning('Servicio no disponible', [
                'servicio' => $servicio,
                'metodo' => $metodo,
                'error' => class_basename($e),
                'correlacion' => $idCorrelacion,
            ]);
            throw $this->noDisponible();
        }
    }

    private function noDisponible(): ErrorApi
    {
        return new ErrorApi('SERVICIO_NO_DISPONIBLE', 'El servicio no responde.', 503);
    }
}
