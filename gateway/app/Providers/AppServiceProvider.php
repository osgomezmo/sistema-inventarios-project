<?php

namespace App\Providers;

use Illuminate\Cache\RateLimiting\Limit;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\RateLimiter;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    /**
     * Register any application services.
     */
    public function register(): void
    {
        //
    }

    /**
     * Bootstrap any application services.
     */
    public function boot(): void
    {
        // Login: 5 intentos por minuto por correo e IP (G8)
        RateLimiter::for('login', function (Request $request) {
            $correo = strtolower(trim((string) $request->input('email')));

            return Limit::perMinute(5)->by($correo.'|'.$request->ip());
        });
    }
}
