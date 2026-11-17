# Etapa 1: dependencias de PHP sin las de desarrollo
FROM composer:2 AS vendor
WORKDIR /app
COPY composer.json composer.lock ./
RUN composer install --no-dev --no-scripts --no-autoloader --prefer-dist --no-interaction \
    --ignore-platform-req=ext-*
COPY . .
RUN composer dump-autoload --no-dev --optimize --classmap-authoritative --no-scripts

# Etapa 2: Apache con PHP 8.3
FROM php:8.3-apache

# Extensión de MySQL y reescritura de URLs
RUN docker-php-ext-install pdo_mysql && a2enmod rewrite

# Apache sirve public/ y respeta el .htaccess de Laravel
ENV APACHE_DOCUMENT_ROOT=/var/www/html/public
RUN sed -ri 's!/var/www/html!${APACHE_DOCUMENT_ROOT}!g' /etc/apache2/sites-available/*.conf \
    && printf '<Directory ${APACHE_DOCUMENT_ROOT}>\n    AllowOverride All\n</Directory>\n' \
       > /etc/apache2/conf-available/laravel.conf \
    && a2enconf laravel

WORKDIR /var/www/html

# Código y dependencias; la configuración llega por variables de entorno
COPY --from=vendor /app /var/www/html

# Registro de paquetes sin los de desarrollo; Apache corre como www-data y
# necesita escribir en storage y bootstrap/cache
RUN php artisan package:discover --ansi \
    && chown -R www-data:www-data storage bootstrap/cache

COPY --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh

EXPOSE 80

# Espera a la base, migra, siembra si no hay roles y arranca Apache
ENTRYPOINT ["entrypoint.sh"]
