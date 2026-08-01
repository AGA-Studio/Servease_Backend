# Servease Backend

API REST para **Servease**, una plataforma que conecta **clientes** que necesitan un servicio (plomería, electricidad, limpieza, etc.) con **proveedores** que lo ofrecen. Proyecto escolar.

## Qué hace

Un cliente publica una solicitud de servicio, los proveedores se postulan con una propuesta de precio, el cliente acepta a uno, se abre un chat entre ambos, el proveedor hace el trabajo, cobra (efectivo o tarjeta vía Stripe) y ambas partes se califican mutuamente al terminar.

Flujo a grandes rasgos:

1. **Cliente** publica un servicio (categoría, ubicación, precio inicial).
2. **Proveedores** se postulan; pueden negociar el precio con contraofertas.
3. **Cliente** acepta una postulación → se crea automáticamente una conversación cliente-proveedor y se rechazan las demás postulaciones pendientes.
4. **Proveedor** hace el trabajo y lo marca como completado, eligiendo cómo se le paga:
   - **Efectivo**: se registra la transacción directo.
   - **Tarjeta**: se cobra con Stripe (PaymentIntent real, confirmado vía webhook con verificación de firma).
5. Ambas partes se **califican** entre sí. Si el cliente no califica dentro de 24h, un job programado (`pg_cron` en Supabase) le asigna automáticamente 5★ al proveedor y baja al mínimo la calificación que el proveedor le dio al cliente.

## Stack

- **Django 6** + **Django REST Framework**
- **PostgreSQL** vía **Supabase** (también se usa para Auth, Storage de imágenes y Realtime — el frontend se suscribe directo a cambios en tablas para actualizar la UI en vivo, sin necesidad de websockets propios)
- **Stripe** para pagos con tarjeta
- Autenticación por JWT de Supabase (`usuarios.authentication.SupabaseAuthentication`), sin sistema de auth propio de Django

## Apps

| App | Responsabilidad |
|---|---|
| `usuarios` | Cuentas, roles (cliente/proveedor/admin), perfiles, categorías, MFA |
| `servicios` | Publicaciones de servicio, postulaciones, ofertas/contraofertas, flujo de completar+pagar+calificar |
| `mensajeria` | Conversaciones y mensajes entre cliente y proveedor |
| `transacciones` | Registro de pagos (efectivo y tarjeta) |
| `calificaciones` | Ratings entre cliente y proveedor |

## Endpoints principales

Todos bajo `/api/`, requieren `Authorization: Bearer <jwt de Supabase>` salvo donde se indica.

**Usuarios** (`/api/usuarios/`): registro, login/MFA, perfil, categorías.

**Servicios** (`/api/servicios/`):
- `GET /` — catálogo público (sin auth)
- `POST /crear/`, `PATCH /<id>/editar/`, `DELETE /<id>/eliminar/` — cliente
- `GET /mis-trabajos/` — postulaciones activas del proveedor
- `POST /postulaciones/<id>/aceptar|rechazar|deshacer-rechazo/` — cliente
- `POST /postulaciones/<id>/cancelar/` — proveedor
- `POST /<id>/completar/` — proveedor, marca completado + registra pago (efectivo) + califica al cliente
- `POST /<id>/calificar/` — cliente califica al proveedor
- `GET /pendiente-calificar/` — servicio completado más reciente sin calificar del cliente
- `POST /<id>/pago/iniciar/` — proveedor, crea el cobro con Stripe
- `POST /pago/<id_transaccion>/cancelar/` — proveedor cancela un cobro con tarjeta pendiente
- `GET /<id>/pago/pendiente/`, `GET /pago/pendiente-cliente/` — cliente recupera el `client_secret` de un cobro pendiente (por servicio o el más reciente)
- `GET /<id>/pago/estado/` — proveedor consulta el estado real de la transacción con tarjeta
- `POST /webhook/stripe/` — recibido por Stripe, no lo llama el frontend

Los endpoints `GET` de arriba en `pendiente-calificar`, `pago/pendiente*` y `pago/estado` son respaldo de los eventos de Supabase Realtime: se consultan al cargar la app por si el evento (pago iniciado, servicio completado) ya había pasado antes de que el cliente se conectara a la suscripción.

## Setup local

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # completar con las credenciales de Supabase/Stripe/Resend
python manage.py migrate
python manage.py runserver
```

Para probar pagos con tarjeta en local hace falta el [Stripe CLI](https://stripe.com/docs/stripe-cli) reenviando el webhook:

```bash
stripe listen --forward-to localhost:8000/api/servicios/webhook/stripe/
```

### Variables de entorno

| Variable | Para qué |
|---|---|
| `SECRET_KEY`, `DEBUG` | Django |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Postgres (Supabase) |
| `SUPABASE_URL`, `SUPABASE_JWKS_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | Auth/Storage de Supabase |
| `RESEND_API_KEY`, `RESEND_FROM_EMAIL` | Correos transaccionales |
| `FRONTEND_URL` | Links en emails |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Pagos con tarjeta |

## Despliegue

Backend pensado para **Railway**, frontend para **Vercel**.
