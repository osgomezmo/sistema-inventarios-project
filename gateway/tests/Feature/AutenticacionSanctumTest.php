<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Route;
use Tests\TestCase;

class AutenticacionSanctumTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        // Ruta protegida solo para estas pruebas; no se publica en routes/api.php
        Route::middleware('auth:sanctum')->get('/api/ping', fn () => ['estado' => 'ok']);
    }

    public function test_sin_token_responde_401_en_json(): void
    {
        $this->get('/api/ping')
            ->assertStatus(401)
            ->assertExactJson(['error' => [
                'codigo' => 'NO_AUTENTICADO',
                'mensaje' => 'Token ausente, inválido o vencido.',
                'detalles' => [],
            ]]);
    }

    public function test_token_invalido_responde_401(): void
    {
        $this->withToken('1|token-que-no-existe')->getJson('/api/ping')
            ->assertStatus(401)
            ->assertJsonPath('error.codigo', 'NO_AUTENTICADO');
    }

    public function test_con_token_valido_responde_200(): void
    {
        $token = User::factory()->create()->createToken('prueba')->plainTextToken;

        $this->withToken($token)->getJson('/api/ping')
            ->assertOk()
            ->assertExactJson(['estado' => 'ok']);
    }

    public function test_el_token_vence_a_las_ocho_horas(): void
    {
        $token = User::factory()->create()->createToken('prueba')->plainTextToken;

        $this->travel(479)->minutes();
        $this->withToken($token)->getJson('/api/ping')->assertOk();

        $this->travel(2)->minutes();
        $this->app['auth']->forgetGuards();
        $this->withToken($token)->getJson('/api/ping')->assertStatus(401);
    }
}
