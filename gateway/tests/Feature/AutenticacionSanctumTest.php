<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class AutenticacionSanctumTest extends TestCase
{
    use RefreshDatabase;

    // GET /api/auth/me es la ruta protegida más simple del gateway
    private const RUTA = '/api/auth/me';

    public function test_sin_token_responde_401_en_json(): void
    {
        $this->get(self::RUTA)
            ->assertStatus(401)
            ->assertExactJson(['error' => [
                'codigo' => 'NO_AUTENTICADO',
                'mensaje' => 'Token ausente, inválido o vencido.',
                'detalles' => [],
            ]]);
    }

    public function test_token_invalido_responde_401(): void
    {
        $this->withToken('1|token-que-no-existe')->getJson(self::RUTA)
            ->assertStatus(401)
            ->assertJsonPath('error.codigo', 'NO_AUTENTICADO');
    }

    public function test_con_token_valido_responde_200(): void
    {
        $token = User::factory()->create()->createToken('prueba')->plainTextToken;

        $this->withToken($token)->getJson(self::RUTA)
            ->assertOk()
            ->assertJsonStructure(['id', 'nombre', 'email', 'estado', 'rol', 'permisos']);
    }

    public function test_el_token_vence_a_las_ocho_horas(): void
    {
        $token = User::factory()->create()->createToken('prueba')->plainTextToken;

        $this->travel(479)->minutes();
        $this->withToken($token)->getJson(self::RUTA)->assertOk();

        $this->travel(2)->minutes();
        $this->app['auth']->forgetGuards();
        $this->withToken($token)->getJson(self::RUTA)->assertStatus(401);
    }
}
