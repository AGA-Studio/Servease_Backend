# APIs.md — Backend por crear (Servease)

> Generado 2026-08-02, actualizado con revisión de triggers reales en Supabase. NO es definitivo. Dirigido a desarrolladores backend.

---

## 1. Postular a un trabajo (crear `Postulacion`)

No existe ningún endpoint para crear una postulación. Solo existen acciones sobre postulaciones ya creadas (aceptar/rechazar/deshacer-rechazo/cancelar).

- **Para qué sirve**: proveedor se postula a un servicio abierto (`estado_id = ABIERTO`).
- **Datos de entrada**:
  - `precio_propuesto`
  - `mensaje`
- **Validaciones**: servicio existe y `estado_id = ABIERTO`; proveedor no se ha postulado ya al mismo servicio; proveedor no es el dueño del servicio.
- **Efectos esperados**: crea `postulacion` con `estado='pendiente'`. El trigger `on_postulacion_creada` (función `notificar_nueva_postulacion`) ya dispara la notificación al cliente automáticamente al hacer el INSERT — no hay que llamar nada manualmente, solo asegurarse de que el INSERT se haga vía tabla real y no solo vía ORM en memoria.

---

## 2. Perfil de proveedor (stats + portfolio)

Faltan datos agregados de proveedor: rating promedio, num_reviews, trabajos completados, ganancias totales, portfolio.

**Ya hay avance sin mergear** (rama `feature/axel`, commit `0879b14`, no está en `main`
- `ProveedorCategoriasView` — categorías/áreas de trabajo del proveedor (`usuario_area_trabajo`).
- `UltimasResenasView` — últimas 3 reseñas recibidas, vía función SQL `ultimas_resenas(uuid)` que **ya existe en la BD** (confirmado en `information_schema.routines`). Usa modelo `VistaUltimaResena` (`managed=False`, `.raw()`).

**Falta todavía**:
- Endpoint con stats agregados: `rating` promedio (avg `calificacion.puntuacion` donde `evaluado_id = usuario`), `num_reviews` (count), `trabajos_completados` (count `postulacion.estado='aceptada'` + `servicio.estado='completado'`), `ganancias_totales` (solo visible para el propio usuario, ya existe parcialmente en `vista_resumen_ganancias` pero es solo semana actual/pendiente/proyectado — falta el acumulado histórico total).
  - Se necesita una vista SQL nueva, ej. `vista_perfil_proveedor`, análoga a `vista_perfil_cliente` pero agregando categorías y trabajos completados.
- **Portfolio**: falta ver si se va a agregar algo de portfolio como tal para que el proveedor elija su portfolio o si lo vamos a hacer de que mostrar sus trabajos realizados donde haya obtenido mayor calificacion (opino que la segunda).

---

## 3. Mensajería (chat)

Tablas `conversacion` y `mensaje` existen y tienen modelos Django (`mensajeria/models/`), pero `mensajeria/views.py` está vacío — **no hay ni un solo endpoint de chat**.

`AceptarPostulacionView` (en `servicios/views.py`) ya crea la `Conversacion` automáticamente al aceptar una postulación (`Conversacion.objects.get_or_create(...)`), así que el dato existe, solo falta exponerlo.

- **Listar conversaciones** del usuario autenticado (como cliente o proveedor).
  - Campos necesarios: `id_conversacion, servicio_id, servicio_titulo, otro_usuario_id, otro_usuario_nombre, otro_usuario_foto, ultimo_mensaje, ultimo_mensaje_fecha, no_leidos_count`.
  - Requiere vista SQL nueva `vista_conversaciones` (join `conversacion` + último `mensaje` + conteo de no leídos + datos del otro participante).
- **Listar mensajes** de una conversación (`id_mensaje, contenido, fecha, leido, emisor_id, receptor_id`). Permiso: solo `cliente_id` o `proveedor_id` de esa conversación.
- **Crear mensaje**: body `contenido`; `emisor` = usuario autenticado, `receptor` = el otro participante de la conversación. El INSERT en `mensaje` ya dispara notificación automática — ver sección 4.
- **Marcar mensaje(s) como leído(s)**: individual o bulk por conversación.

**Esto falta ver si Erik lo tiene bien.**


---

## 4. Notificaciones

Tabla `notificacion` existe (`id_notificacion, id_usuario, tipo, titulo, contenido, leido, fecha, referencia_tabla, referencia_id`) pero **no tiene modelo Django en ningún lado** — nada la lee desde la API todavía.

**Los triggers SÍ existen para casi todo** (verificado directo en Supabase vía `pg_trigger`/`pg_proc`, no asumido):

| Trigger | Tabla / evento | Función | Estado |
|---|---|---|---|
| `on_servicio_creado` | `servicio` INSERT | `notificar_nuevo_post` | ✅ conectado |
| `on_postulacion_creada` | `postulacion` INSERT | `notificar_nueva_postulacion` | ✅ conectado |
| `on_postulacion_actualizada` | `postulacion` UPDATE | `notificar_cambio_estado_postulacion` (aceptada/rechazada/reconsiderada) | ✅ conectado |
| `on_postulacion_aceptada_efectos` | `postulacion` UPDATE | `efectos_postulacion_aceptada` (no es de notificación, son efectos de negocio) | ✅ conectado |
| `on_oferta_creada` | `oferta` INSERT | `notificar_nueva_oferta` | ✅ conectado |
| `on_servicio_completado` | `servicio` UPDATE (`estado_id = 5`) | `notificar_servicio_completado` (notifica a cliente y proveedor) | ✅ conectado |
| — | `mensaje` INSERT | `notificar_nuevo_mensaje` | ⚠️ **función existe, sin trigger asociado — huérfana** |
| — | `calificacion` INSERT | `notificar_nueva_calificacion` | ⚠️ **función existe, sin trigger asociado — huérfana** |

**Falta crear en Supabase**:
```sql
CREATE TRIGGER on_mensaje_creado
AFTER INSERT ON mensaje
FOR EACH ROW EXECUTE FUNCTION notificar_nuevo_mensaje();

CREATE TRIGGER on_calificacion_creada
AFTER INSERT ON calificacion
FOR EACH ROW EXECUTE FUNCTION notificar_nueva_calificacion();
```
Ambas funciones ya están escritas y probadas en su lógica (insertan correctamente en `notificacion` con `tipo`, `titulo`, `contenido`, `referencia_tabla`, `referencia_id`), solo falta el `CREATE TRIGGER`. Una vez creado esto, la sección 3 (mensajería) y la calificación de servicios ya generan notificaciones sin tocar Django.

**Falta en Django** (los triggers escriben en la tabla, pero nadie la lee vía API):
- Modelo `Notificacion` (managed=False o migración liviana, la tabla ya existe).
- Endpoint para listar notificaciones del usuario autenticado, ordenadas por fecha desc.
- Endpoint para marcar una notificación como leída.
- Endpoint para marcar todas como leídas.

---

## 5. Resumen de objetos SQL a crear/portar

| Objeto | Tipo | Estado | Para qué |
|---|---|---|---|
| `on_mensaje_creado` | Trigger | **Falta crear** | notificación de nuevo mensaje (función ya existe) |
| `on_calificacion_creada` | Trigger | **Falta crear** | notificación de nueva calificación (función ya existe) |
| `vista_conversaciones` | Vista | Falta crear | listar conversaciones con último mensaje y no leídos |
| `vista_perfil_proveedor` | Vista | Falta crear | stats agregados de proveedor (rating, reviews, trabajos completados) |
| Modelo Django `Notificacion` | Modelo | Falta crear | leer/marcar notificaciones desde la API |
| `ProveedorCategoriasView`, `UltimasResenasView` + `VistaUltimaResena` | Vistas Django | Existen en `feature/axel` (commit `0879b14`), sin mergear | portar a la rama actual |
| Columna `mensaje` en `postulacion` (o confirmar origen real en `vista_info_aplicantes.mensaje_proveedor`) | Columna | **Pendiente investigar** | payload de "postular a trabajo" (sección 1) |
| Tabla `proveedor_portfolio` (opcional) | Tabla | Decisión de producto pendiente | portfolio de proveedor (sección 2) |
