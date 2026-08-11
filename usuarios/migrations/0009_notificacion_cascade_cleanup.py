from django.db import migrations

# `notificacion.referencia_tabla` + `referencia_id` es una referencia
# generica (no un FK real, porque una notificacion puede apuntar a distintas
# tablas segun su tipo), asi que Postgres nunca la valida ni la limpia solo.
# Si la fila referenciada se borra, la notificacion queda huerfana. Estos
# triggers la limpian automaticamente sin importar por donde vino el borrado
# (Django, otro cascade, o un DELETE manual en Supabase).
#
# Ademas, casi todos los FK reales de la base estaban en NO ACTION aunque el
# modelo de Django ya declarara CASCADE/SET_NULL/PROTECT — Django aplica ese
# comportamiento "en la app" cuando el borrado pasa por el ORM, pero un
# DELETE hecho fuera de Django (SQL editor de Supabase, por ejemplo) chocaba
# con un error de FK en vez de comportarse como el resto del sistema espera.
# Este migration alinea los constraints reales con lo que los modelos ya
# declaran.

FORWARD_SQL = """
CREATE OR REPLACE FUNCTION public.limpiar_notificaciones_servicio()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
BEGIN
    DELETE FROM notificacion
    WHERE referencia_tabla = 'servicio'
      AND referencia_id = OLD.id_servicio;
    RETURN OLD;
END;
$function$;

DROP TRIGGER IF EXISTS trg_limpiar_notificaciones_servicio ON servicio;
CREATE TRIGGER trg_limpiar_notificaciones_servicio
AFTER DELETE ON servicio
FOR EACH ROW
EXECUTE FUNCTION public.limpiar_notificaciones_servicio();

CREATE OR REPLACE FUNCTION public.limpiar_notificaciones_mensaje()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
BEGIN
    DELETE FROM notificacion
    WHERE referencia_tabla = 'mensaje'
      AND referencia_id = OLD.id_mensaje;
    RETURN OLD;
END;
$function$;

DROP TRIGGER IF EXISTS trg_limpiar_notificaciones_mensaje ON mensaje;
CREATE TRIGGER trg_limpiar_notificaciones_mensaje
AFTER DELETE ON mensaje
FOR EACH ROW
EXECUTE FUNCTION public.limpiar_notificaciones_mensaje();

CREATE OR REPLACE FUNCTION public.limpiar_notificaciones_postulacion()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
BEGIN
    DELETE FROM notificacion
    WHERE referencia_tabla = 'postulacion'
      AND referencia_id = OLD.id_postulacion;
    RETURN OLD;
END;
$function$;

DROP TRIGGER IF EXISTS trg_limpiar_notificaciones_postulacion ON postulacion;
CREATE TRIGGER trg_limpiar_notificaciones_postulacion
AFTER DELETE ON postulacion
FOR EACH ROW
EXECUTE FUNCTION public.limpiar_notificaciones_postulacion();

CREATE OR REPLACE FUNCTION public.limpiar_notificaciones_calificacion()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
BEGIN
    DELETE FROM notificacion
    WHERE referencia_tabla = 'calificacion'
      AND referencia_id = OLD.id_calificacion;
    RETURN OLD;
END;
$function$;

DROP TRIGGER IF EXISTS trg_limpiar_notificaciones_calificacion ON calificacion;
CREATE TRIGGER trg_limpiar_notificaciones_calificacion
AFTER DELETE ON calificacion
FOR EACH ROW
EXECUTE FUNCTION public.limpiar_notificaciones_calificacion();

ALTER TABLE mensaje
  DROP CONSTRAINT mensaje_conversacion_id_7d366407_fk_conversac,
  ADD CONSTRAINT mensaje_conversacion_id_7d366407_fk_conversac
    FOREIGN KEY (conversacion_id) REFERENCES conversacion(id_conversacion)
    ON DELETE CASCADE;

ALTER TABLE mensaje
  DROP CONSTRAINT mensaje_emisor_id_0c31f449_fk_usuario_id_usuario,
  ADD CONSTRAINT mensaje_emisor_id_0c31f449_fk_usuario_id_usuario
    FOREIGN KEY (emisor_id) REFERENCES usuario(id_usuario)
    ON DELETE CASCADE;

ALTER TABLE mensaje
  DROP CONSTRAINT mensaje_receptor_id_47ad6db1_fk_usuario_id_usuario,
  ADD CONSTRAINT mensaje_receptor_id_47ad6db1_fk_usuario_id_usuario
    FOREIGN KEY (receptor_id) REFERENCES usuario(id_usuario)
    ON DELETE CASCADE;

ALTER TABLE oferta
  DROP CONSTRAINT oferta_postulacion_id_a34437ef_fk_postulacion_id_postulacion,
  ADD CONSTRAINT oferta_postulacion_id_a34437ef_fk_postulacion_id_postulacion
    FOREIGN KEY (postulacion_id) REFERENCES postulacion(id_postulacion)
    ON DELETE CASCADE;

ALTER TABLE oferta
  DROP CONSTRAINT oferta_emisor_id_fkey,
  ADD CONSTRAINT oferta_emisor_id_fkey
    FOREIGN KEY (emisor_id) REFERENCES usuario(id_usuario)
    ON DELETE SET NULL;

ALTER TABLE calificacion
  DROP CONSTRAINT calificacion_servicio_id_67b506f4_fk_servicio_id_servicio,
  ADD CONSTRAINT calificacion_servicio_id_67b506f4_fk_servicio_id_servicio
    FOREIGN KEY (servicio_id) REFERENCES servicio(id_servicio)
    ON DELETE CASCADE;

ALTER TABLE calificacion
  DROP CONSTRAINT calificacion_evaluado_id_133f98ca_fk_usuario_id_usuario,
  ADD CONSTRAINT calificacion_evaluado_id_133f98ca_fk_usuario_id_usuario
    FOREIGN KEY (evaluado_id) REFERENCES usuario(id_usuario)
    ON DELETE CASCADE;

ALTER TABLE calificacion
  DROP CONSTRAINT calificacion_evaluador_id_0a14f67c_fk_usuario_id_usuario,
  ADD CONSTRAINT calificacion_evaluador_id_0a14f67c_fk_usuario_id_usuario
    FOREIGN KEY (evaluador_id) REFERENCES usuario(id_usuario)
    ON DELETE CASCADE;

ALTER TABLE conversacion
  DROP CONSTRAINT conversacion_servicio_id_46742cdc_fk_servicio_id_servicio,
  ADD CONSTRAINT conversacion_servicio_id_46742cdc_fk_servicio_id_servicio
    FOREIGN KEY (servicio_id) REFERENCES servicio(id_servicio)
    ON DELETE CASCADE;

ALTER TABLE conversacion
  DROP CONSTRAINT conversacion_cliente_id_c68f7a39_fk_usuario_id_usuario,
  ADD CONSTRAINT conversacion_cliente_id_c68f7a39_fk_usuario_id_usuario
    FOREIGN KEY (cliente_id) REFERENCES usuario(id_usuario)
    ON DELETE CASCADE;

ALTER TABLE conversacion
  DROP CONSTRAINT conversacion_proveedor_id_bba83dbb_fk_usuario_id_usuario,
  ADD CONSTRAINT conversacion_proveedor_id_bba83dbb_fk_usuario_id_usuario
    FOREIGN KEY (proveedor_id) REFERENCES usuario(id_usuario)
    ON DELETE CASCADE;

ALTER TABLE postulacion
  DROP CONSTRAINT postulacion_servicio_id_bdbd2abf_fk_servicio_id_servicio,
  ADD CONSTRAINT postulacion_servicio_id_bdbd2abf_fk_servicio_id_servicio
    FOREIGN KEY (servicio_id) REFERENCES servicio(id_servicio)
    ON DELETE CASCADE;

ALTER TABLE postulacion
  DROP CONSTRAINT postulacion_proveedor_id_9d8f6c42_fk_usuario_id_usuario,
  ADD CONSTRAINT postulacion_proveedor_id_9d8f6c42_fk_usuario_id_usuario
    FOREIGN KEY (proveedor_id) REFERENCES usuario(id_usuario)
    ON DELETE CASCADE;

ALTER TABLE servicio
  DROP CONSTRAINT servicio_cliente_id_d532ed46_fk_usuario_id_usuario,
  ADD CONSTRAINT servicio_cliente_id_d532ed46_fk_usuario_id_usuario
    FOREIGN KEY (cliente_id) REFERENCES usuario(id_usuario)
    ON DELETE CASCADE;

ALTER TABLE transaccion
  DROP CONSTRAINT transaccion_cliente_id_c37454fc_fk_usuario_id_usuario,
  ADD CONSTRAINT transaccion_cliente_id_c37454fc_fk_usuario_id_usuario
    FOREIGN KEY (cliente_id) REFERENCES usuario(id_usuario)
    ON DELETE RESTRICT;

ALTER TABLE transaccion
  DROP CONSTRAINT transaccion_proveedor_id_e0493c06_fk_usuario_id_usuario,
  ADD CONSTRAINT transaccion_proveedor_id_e0493c06_fk_usuario_id_usuario
    FOREIGN KEY (proveedor_id) REFERENCES usuario(id_usuario)
    ON DELETE RESTRICT;

ALTER TABLE transaccion
  DROP CONSTRAINT transaccion_servicio_id_02e4c67a_fk_servicio_id_servicio,
  ADD CONSTRAINT transaccion_servicio_id_02e4c67a_fk_servicio_id_servicio
    FOREIGN KEY (servicio_id) REFERENCES servicio(id_servicio)
    ON DELETE CASCADE;

ALTER TABLE mfa_backup_code
  DROP CONSTRAINT mfa_backup_code_id_usuario_8cd485d0_fk_usuario_id_usuario,
  ADD CONSTRAINT mfa_backup_code_id_usuario_8cd485d0_fk_usuario_id_usuario
    FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario)
    ON DELETE CASCADE;

ALTER TABLE sucursal
  DROP CONSTRAINT sucursal_empresa_id_c9c1ad1c_fk_empresa_id_empresa,
  ADD CONSTRAINT sucursal_empresa_id_c9c1ad1c_fk_empresa_id_empresa
    FOREIGN KEY (empresa_id) REFERENCES empresa(id_empresa)
    ON DELETE CASCADE;
"""

REVERSE_SQL = """
DROP TRIGGER IF EXISTS trg_limpiar_notificaciones_servicio ON servicio;
DROP FUNCTION IF EXISTS public.limpiar_notificaciones_servicio();

DROP TRIGGER IF EXISTS trg_limpiar_notificaciones_mensaje ON mensaje;
DROP FUNCTION IF EXISTS public.limpiar_notificaciones_mensaje();

DROP TRIGGER IF EXISTS trg_limpiar_notificaciones_postulacion ON postulacion;
DROP FUNCTION IF EXISTS public.limpiar_notificaciones_postulacion();

DROP TRIGGER IF EXISTS trg_limpiar_notificaciones_calificacion ON calificacion;
DROP FUNCTION IF EXISTS public.limpiar_notificaciones_calificacion();

ALTER TABLE mensaje
  DROP CONSTRAINT mensaje_conversacion_id_7d366407_fk_conversac,
  ADD CONSTRAINT mensaje_conversacion_id_7d366407_fk_conversac
    FOREIGN KEY (conversacion_id) REFERENCES conversacion(id_conversacion);

ALTER TABLE mensaje
  DROP CONSTRAINT mensaje_emisor_id_0c31f449_fk_usuario_id_usuario,
  ADD CONSTRAINT mensaje_emisor_id_0c31f449_fk_usuario_id_usuario
    FOREIGN KEY (emisor_id) REFERENCES usuario(id_usuario);

ALTER TABLE mensaje
  DROP CONSTRAINT mensaje_receptor_id_47ad6db1_fk_usuario_id_usuario,
  ADD CONSTRAINT mensaje_receptor_id_47ad6db1_fk_usuario_id_usuario
    FOREIGN KEY (receptor_id) REFERENCES usuario(id_usuario);

ALTER TABLE oferta
  DROP CONSTRAINT oferta_postulacion_id_a34437ef_fk_postulacion_id_postulacion,
  ADD CONSTRAINT oferta_postulacion_id_a34437ef_fk_postulacion_id_postulacion
    FOREIGN KEY (postulacion_id) REFERENCES postulacion(id_postulacion);

ALTER TABLE oferta
  DROP CONSTRAINT oferta_emisor_id_fkey,
  ADD CONSTRAINT oferta_emisor_id_fkey
    FOREIGN KEY (emisor_id) REFERENCES usuario(id_usuario);

ALTER TABLE calificacion
  DROP CONSTRAINT calificacion_servicio_id_67b506f4_fk_servicio_id_servicio,
  ADD CONSTRAINT calificacion_servicio_id_67b506f4_fk_servicio_id_servicio
    FOREIGN KEY (servicio_id) REFERENCES servicio(id_servicio);

ALTER TABLE calificacion
  DROP CONSTRAINT calificacion_evaluado_id_133f98ca_fk_usuario_id_usuario,
  ADD CONSTRAINT calificacion_evaluado_id_133f98ca_fk_usuario_id_usuario
    FOREIGN KEY (evaluado_id) REFERENCES usuario(id_usuario);

ALTER TABLE calificacion
  DROP CONSTRAINT calificacion_evaluador_id_0a14f67c_fk_usuario_id_usuario,
  ADD CONSTRAINT calificacion_evaluador_id_0a14f67c_fk_usuario_id_usuario
    FOREIGN KEY (evaluador_id) REFERENCES usuario(id_usuario);

ALTER TABLE conversacion
  DROP CONSTRAINT conversacion_servicio_id_46742cdc_fk_servicio_id_servicio,
  ADD CONSTRAINT conversacion_servicio_id_46742cdc_fk_servicio_id_servicio
    FOREIGN KEY (servicio_id) REFERENCES servicio(id_servicio);

ALTER TABLE conversacion
  DROP CONSTRAINT conversacion_cliente_id_c68f7a39_fk_usuario_id_usuario,
  ADD CONSTRAINT conversacion_cliente_id_c68f7a39_fk_usuario_id_usuario
    FOREIGN KEY (cliente_id) REFERENCES usuario(id_usuario);

ALTER TABLE conversacion
  DROP CONSTRAINT conversacion_proveedor_id_bba83dbb_fk_usuario_id_usuario,
  ADD CONSTRAINT conversacion_proveedor_id_bba83dbb_fk_usuario_id_usuario
    FOREIGN KEY (proveedor_id) REFERENCES usuario(id_usuario);

ALTER TABLE postulacion
  DROP CONSTRAINT postulacion_servicio_id_bdbd2abf_fk_servicio_id_servicio,
  ADD CONSTRAINT postulacion_servicio_id_bdbd2abf_fk_servicio_id_servicio
    FOREIGN KEY (servicio_id) REFERENCES servicio(id_servicio);

ALTER TABLE postulacion
  DROP CONSTRAINT postulacion_proveedor_id_9d8f6c42_fk_usuario_id_usuario,
  ADD CONSTRAINT postulacion_proveedor_id_9d8f6c42_fk_usuario_id_usuario
    FOREIGN KEY (proveedor_id) REFERENCES usuario(id_usuario);

ALTER TABLE servicio
  DROP CONSTRAINT servicio_cliente_id_d532ed46_fk_usuario_id_usuario,
  ADD CONSTRAINT servicio_cliente_id_d532ed46_fk_usuario_id_usuario
    FOREIGN KEY (cliente_id) REFERENCES usuario(id_usuario);

ALTER TABLE transaccion
  DROP CONSTRAINT transaccion_cliente_id_c37454fc_fk_usuario_id_usuario,
  ADD CONSTRAINT transaccion_cliente_id_c37454fc_fk_usuario_id_usuario
    FOREIGN KEY (cliente_id) REFERENCES usuario(id_usuario);

ALTER TABLE transaccion
  DROP CONSTRAINT transaccion_proveedor_id_e0493c06_fk_usuario_id_usuario,
  ADD CONSTRAINT transaccion_proveedor_id_e0493c06_fk_usuario_id_usuario
    FOREIGN KEY (proveedor_id) REFERENCES usuario(id_usuario);

ALTER TABLE transaccion
  DROP CONSTRAINT transaccion_servicio_id_02e4c67a_fk_servicio_id_servicio,
  ADD CONSTRAINT transaccion_servicio_id_02e4c67a_fk_servicio_id_servicio
    FOREIGN KEY (servicio_id) REFERENCES servicio(id_servicio);

ALTER TABLE mfa_backup_code
  DROP CONSTRAINT mfa_backup_code_id_usuario_8cd485d0_fk_usuario_id_usuario,
  ADD CONSTRAINT mfa_backup_code_id_usuario_8cd485d0_fk_usuario_id_usuario
    FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario);

ALTER TABLE sucursal
  DROP CONSTRAINT sucursal_empresa_id_c9c1ad1c_fk_empresa_id_empresa,
  ADD CONSTRAINT sucursal_empresa_id_c9c1ad1c_fk_empresa_id_empresa
    FOREIGN KEY (empresa_id) REFERENCES empresa(id_empresa);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0008_vista_trabajos_aplicados_trabajo_terminado'),
        ('servicios', '0010_servicio_trabajo_terminado'),
        ('mensajeria', '0003_split_unread_count_by_participant'),
        ('calificaciones', '0001_initial'),
        ('transacciones', '0003_transaccion_stripe_payment_intent_id'),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
