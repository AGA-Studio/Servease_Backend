# API Endpoints — Servease Backend

Referencia de todos los endpoints actuales, agrupados por área. Todos los paths van después de `/api/`.

Convenciones generales:
- Auth por defecto: `Authorization: Bearer <access_token de Supabase>` (`SupabaseAuthentication`). Si no se indica lo contrario, el endpoint requiere `IsAuthenticated`.
- `IsClientRole` = `rol_id == 1`, `IsProviderRole` = `rol_id == 2`, `IsAdminRole` = `rol_id == 3`.
- Rate limiting: piso global `100/hora` (anónimo) / `1000/hora` (autenticado) sobre **todos** los endpoints, más límites específicos (`throttle_scope`) en los más sensibles/costosos — se indican por endpoint.

---

## Cuenta y autenticación (`usuarios/`)

### `POST /usuarios/signup/`
Registro de cliente nuevo. `AllowAny`, sin autenticación. Throttle: `signup` (5/hora).
Body (`multipart/form-data`): `email`, `password`, `nombre`, `apellido_pa`, `segundo_nombre` y `apellido_ma` (opcionales), `photo` (opcional).
Crea el usuario en Supabase Auth (`email_confirm=True`, confirmación propia vía correo), sube la foto de perfil si se manda, crea la fila en `usuario` con `rol_id=1` y `estado=False`, y envía un correo con link de confirmación (Resend). Si cualquier paso falla, revierte lo ya creado (usuario Auth, foto, fila en `usuario`).

### `POST /usuarios/confirm-email/`
Confirma la cuenta con el token del correo de signup. `AllowAny`. Throttle: `confirm-email` (20/hora).
Body: `{"token": "..."}`. Marca `usuario.estado = True`.

### `GET /usuarios/auth/`
Perfil completo del usuario logueado (`MeView`). Regresa todos los campos de `usuario` + `rol` + `id_categorias` (categorías del proveedor, ver `areas-trabajo`) + `id_categoria` (campo legado, casi siempre `null`).

### `PATCH /usuarios/auth/`
Actualiza `url_foto_perfil` (debe apuntar a la carpeta propia del usuario en el bucket `profile_photos`).

### `DELETE /usuarios/auth/`
Elimina la cuenta del usuario logueado (cliente o proveedor). Borra el usuario en Supabase Auth; `usuario` se borra solo por `ON DELETE CASCADE`.

### `PATCH /usuarios/auth/personal-info/`
Modifica nombre, apellidos, celular, descripción de perfil. Solo `IsClientRole`.

### `POST /usuarios/settings/password-reset/`
Dispara el correo de restablecimiento de contraseña de Supabase. Throttle: `password-reset` (5/hora).

---

## MFA (doble factor)

### `POST /usuarios/mfa/enroll/`
Inicia el registro de un factor TOTP (QR/secret). Throttle: `mfa-enroll` (10/hora). Body opcional: `factor_type`, `friendly_name`.

### `POST /usuarios/mfa/<factor_id>/challenge/`
Crea el challenge para verificar el factor recién registrado. Throttle: `mfa-challenge` (20/hora).

### `POST /usuarios/mfa/<factor_id>/verify/`
Verifica el código TOTP. Body: `{"code": "...", "challenge_id": "..."}`. Throttle: `mfa-verify` (20/hora).

### `POST /usuarios/mfa/backup-codes/generate/`
Genera 8 códigos de respaldo (formato `XXXXX-XXXXX`), invalida los anteriores no usados. Throttle: `mfa-backup-generate` (10/hora). Regresa los códigos en claro **una sola vez** (se guardan hasheados).

### `POST /usuarios/mfa/backup-codes/verify/`
Body: `{"code": "..."}`. Consume un código de respaldo válido. Throttle: `mfa-backup-verify` (15/hora). Regresa cuántos códigos quedan.

---

## Administración

### `POST /usuarios/<id_usuario>/disable/`
Deshabilita a un usuario (`estado = False`). Solo `IsAdminRole`.

---

## Categorías

### `GET /usuarios/categorias/`
Lista todas las categorías (`id_categoria`, `nombre`).

### `GET /usuarios/categorias/<id_categoria>/`
Detalle de una categoría.

---

## Perfil de cliente (público)

### `GET /usuarios/<id_usuario>/perfil-cliente/`
Perfil público de un cliente: nombre, foto, fecha de registro, descripción, número de publicaciones, rating y número de reviews.

### `GET /usuarios/<id_usuario>/reviews/`
Reviews recibidas por ese cliente, más recientes primero.

### `GET /usuarios/<id_usuario>/home/`
Servicios publicados por ese cliente para su pantalla de inicio, incluye `fotos_proveedores_aplicantes` (avatares de quienes ya se postularon). **No valida ownership** — cualquier usuario autenticado puede consultar el home de otro `id_usuario`.

### `GET /usuarios/<id_usuario>/ultimas-publicaciones/`
Últimas 5 publicaciones del cliente. Solo el dueño (`id_usuario` debe coincidir con el JWT).

### `GET /usuarios/<id_usuario>/mis-publicaciones/`
Todas las publicaciones del cliente, paginadas (`page_size=10`, máx 50) y filtrables por `?estado=` y `?categoria_id=`. Solo el dueño.

---

## Proveedor

### `GET / PATCH /usuarios/disponibilidad/`
Ver o cambiar el estado "disponible para trabajar" del proveedor. Solo `IsProviderRole`.
- `PATCH` body: `{"disponible": true|false}`

### `GET / PUT /usuarios/areas-trabajo/`
Ver o **reemplazar por completo** las categorías en las que trabaja el proveedor (M2M vía `usuario_area_trabajo`). Solo `IsProviderRole`.
- `PUT` body: `{"categorias": [1, 3]}` — sustituye el set completo, no agrega.

### `GET /usuarios/resumen-ganancias/`
Resumen de ganancias del proveedor logueado. Solo `IsProviderRole`.
- `ganancias_esta_semana`: transacciones completadas desde el lunes actual.
- `ganancias_pendiente`: trabajos en progreso con postulación aceptada (dinero por cobrar).
- `ganancias_proyectado`: estimado semanal según el ritmo actual (`ganado hasta hoy / días transcurridos * 7`).

### `GET /usuarios/trabajos-aplicados/`
Postulaciones hechas por el proveedor logueado, en **todos** los estados (no filtra por defecto). Solo `IsProviderRole`.
Filtros opcionales combinables:
- `?estado_id=` → `1` aceptado, `2` pendiente, `3` rechazada, `6` contraoferta.
- `?categoria_id=` → una de las categorías del servicio.

### `GET /usuarios/trabajos-aplicados/cards/`
Igual que `/trabajos-aplicados/` (mismos filtros), pero con el shape reducido para tarjetas: `categoria`, `estado`, `titulo`, `tiempo_transcurrido`, `presupuesto`, `foto` (la primera imagen de las que se suben al bucket `service_images` al crear la publicación). Solo `IsProviderRole`.

### `GET /usuarios/trabajos-disponibles/`
Servicios abiertos (`estado_id=7`, "Recibiendo Propuestas"), filtrados automáticamente por las áreas de trabajo del proveedor logueado. Solo `IsProviderRole`.
Filtros opcionales combinables:
- `?categoria_id=` → acota a una categoría específica dentro de sus áreas.
- `?precio_min=`, `?precio_max=`

---

## Servicios (`servicios/`)

### `GET /servicios/`
Catálogo público de servicios (excluye `Cancelado`). `AllowAny`. Filtros: `?categoria_id=`, `?estado=`.

### `POST /servicios/crear/`
Crea una solicitud de servicio nueva. Solo `IsClientRole`. Throttle: `servicio-create` (20/hora).
Body: `titulo`, `descripcion`, `precio_inicial` (>0), `latitud`/`longitud` (deben caer dentro del área de Tijuana — bounding box, excluye Tecate/Rosarito/Ensenada), `id_categoria`, `id_tipo_cambio` (opcional), `imagenes` (opcional, URLs deben apuntar a la carpeta propia en el bucket `service_images`), `fecha_final` (opcional, `YYYY-MM-DDTHH:MM`).
El `estado` se fija a `Recibiendo Propuestas` (`ABIERTO`) automáticamente.

### `PATCH /servicios/<id_servicio>/editar/`
Edita una publicación. Solo el cliente dueño, y solo si sigue `Recibiendo Propuestas`.

### `DELETE /servicios/<id_servicio>/eliminar/`
Cancela una publicación (borrado lógico, `estado → Cancelado`). Solo el cliente dueño, y solo si sigue `Recibiendo Propuestas`.

### `GET /servicios/<id_servicio>/detalle/`
Detalle completo de un servicio + info del cliente que lo publicó (rating, foto, número de publicaciones, tiempo transcurrido).

### `GET /servicios/<id_servicio>/aplicantes/`
Postulaciones a ese servicio (info del proveedor, rating, precio propuesto/acordado). Solo el cliente dueño del servicio.

### `POST /servicios/ofertas/crear/`
Envía una oferta/contraoferta sobre una postulación. Solo el cliente dueño del servicio o el proveedor de esa postulación. Throttle: `oferta-create` (20/hora).
Body: `id_postulacion`, `monto` (>0), `comentario` (opcional). El `estado` se fija a `Pendiente` automáticamente.

---

## Catálogo de estados (`estado`)

Tabla compartida por `servicio`, `postulacion`, `oferta`, `transaccion` y `conversacion` vía FK `estado_id`:

| id | descripcion |
|----|-------------|
| 1 | aceptado |
| 2 | pendiente |
| 3 | rechazada |
| 4 | progreso |
| 5 | completado |
| 6 | contraoferta |
| 7 | abierto |
| 8 | cancelado |

Nota: `oferta.estado_id` para "en negociación" usa `6` (`contraoferta`), y `conversacion.estado_id` para "activa" usa `7` (`abierto`) — no hay filas 9/10 aparte, se reutilizan estos 8 estados para todo.

---

## Pendientes / riesgos conocidos

- **Posible endpoint duplicado al mergear `feature/axel`**: ese branch (commit `0879b14`, ver `api.md`) trae `ProveedorCategoriasView` — categorías/áreas de trabajo del proveedor vía `usuario_area_trabajo`. Es lo mismo que ya existe aquí como `GET/PUT /usuarios/areas-trabajo/` (`AreasTrabajoView`), que además ya soporta lectura y escritura y ya está probado contra datos reales. Al mergear esa rama, descartar `ProveedorCategoriasView` a favor de `AreasTrabajoView` para no dejar dos formas de hacer lo mismo.
- `usuario.id_categoria` (campo legado, un solo valor) sigue existiendo pero ya no se usa — reemplazado por `areas_trabajo` (M2M, múltiples categorías por proveedor).
- `vista_post_details`, `vista_home_cliente` y `vista_info_aplicantes` todavía leen columnas de texto viejas (`servicio.estado`, `postulacion.estado`, `transaccion.estado`) en vez de `estado_id` — pendiente de migrar para poder eliminar esas columnas.
- `HomeClienteView` no valida que el `id_usuario` de la URL sea el del usuario autenticado.
