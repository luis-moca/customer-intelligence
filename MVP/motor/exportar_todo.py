"""
Exportación completa para escalar: la foto de la cartera (132 campos +
upsell_content aparte) + el libro de eventos de MRR + la tabla de última
conexión. Tres archivos separados en salida/ — no se fusionan, eso es
trabajo de análisis, no de exportación.

Volumen real contra Odoo: 4 consultas normales (foto, log, conexiones, y el
descubrimiento de campos bloqueados) + ~273 lecturas individuales, pequeñas
y espaciadas, solo para upsell_content (el único campo con el bug de
"Expected singleton" al leerlo en lote). Mismo patrón ya usado varias veces
en este proyecto sin incidentes.

No imprime valores de clientes en la terminal — solo conteos y nombres de
campo. Los datos reales quedan únicamente en los archivos de salida/, en
esta máquina.
"""
import json
import os
import time

from fuente_odoo import conectar, LIMITE_SEGURIDAD_CUENTAS

CARPETA_SALIDA = os.path.join(os.path.dirname(__file__), "salida")

CAMPOS_SALE_ORDER = """
activity_date_deadline activity_ids activity_state activity_summary
activity_type_icon activity_type_id activity_user_id amount_invoiced
amount_paid amount_to_invoice amount_unpaid amount_total campaign_id
cart_quantity client_order_ref close_reason_id closed_task_count
commercial_partner_id commission_plan_id company_id completed_task_percentage
contract_value country_code country_id create_date create_uid currency_id
currency_rate database_count database_ids date_order display_name end_date
enterprise_has_download enterprise_is_enterprise enterprise_saas
enterprise_users expected_next_invoice_date first_contract_date
fiscal_position_id has_odoo_sh history_count hosting id industry_id
internal_note internal_note_display invoice_count invoice_date_diff
invoice_ids invoice_status is_closing is_renewing is_upselling
last_invoice_date locked l10n_mx_edi_cfdi_to_public
l10n_mx_edi_partner_address_complete l10n_mx_edi_payment_method_id
l10n_mx_edi_usage maintenance_is_activated maintenance_is_paying medium_id
message_attachment_count message_ids message_partner_ids
my_activity_date_deadline name next_invoice_date non_recurring_total note
note_order odoo_sh_extra_gb odoo_sh_extra_stagings odoo_sh_extra_workers
odoo_sh_project_activated opportunity_id order_line order_log_ids origin
origin_order_id partner_id partner_invoice_id partner_shipping_id
partner_status payment_term_id payment_token_id pending_transaction
percentage_satisfaction plan_billing_period_unit plan_id prepayment_percent
pricelist_id project_account_id project_count project_id project_ids
rating_avg_text rating_percentage_satisfaction recurring_details
recurring_monthly recurring_total renewal_count require_payment
require_signature sale_order_template_id source_id start_date
starred_user_ids subscription_child_ids subscription_id subscription_state
subscription_tag_ids subscription_task_ids tag_ids tasks_count tasks_ids
team_currency_id team_id team_user_id timesheet_count timesheet_total_duration
to_renew transition_date upsell_count upsell_order_id user_id validity_date
version warehouse_id website_message_ids website_order_line
""".split()

# Bug de módulo custom: truena "Expected singleton" al leerse junto con
# otros campos o en lote. Se pide aparte, cuenta por cuenta.
CAMPO_ROTO_EN_LOTE = "upsell_content"

def _falla(consultar, modelo, dominio, campos):
    if not campos:
        return False
    try:
        consultar(modelo, "search_read", [dominio], {"fields": campos, "limit": 1})
        return False
    except Exception:
        return True


def encontrar_bloqueados(consultar, modelo, dominio, campos):
    """Bisección: no interpreta el texto del error, solo si truena o no.
    Misma lógica ya probada en replicar_filtro.py, generalizada a cualquier
    modelo/dominio para reusarla en los 3 orígenes de datos."""
    bloqueados = []

    def buscar(subset):
        if not subset or not _falla(consultar, modelo, dominio, subset):
            return
        if len(subset) == 1:
            bloqueados.append(subset[0])
            return
        mitad = len(subset) // 2
        buscar(subset[:mitad])
        buscar(subset[mitad:])

    buscar(list(campos))
    return bloqueados


def leer_todo(consultar, modelo, dominio, campos, etiqueta, limite=None):
    bloqueados = encontrar_bloqueados(consultar, modelo, dominio, campos)
    restantes = [c for c in campos if c not in bloqueados]
    opciones = {"fields": restantes}
    if limite:
        opciones["limit"] = limite
    filas = consultar(modelo, "search_read", [dominio], opciones)
    print("%s: %d filas, %d campos leídos, %d bloqueados por permiso%s"
          % (etiqueta, len(filas), len(restantes), len(bloqueados),
             (" (%s)" % ", ".join(bloqueados)) if bloqueados else ""))
    if limite and len(filas) >= limite:
        print("[alerta] se llegó al tope de seguridad (%d) en %s — puede "
              "estar cortado, revisa el filtro antes de confiar en esto."
              % (limite, etiqueta))
    return filas


def guardar(nombre, datos):
    os.makedirs(CARPETA_SALIDA, exist_ok=True)
    ruta = os.path.join(CARPETA_SALIDA, nombre)
    with open(ruta, "w") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    print("Guardado: %s (%.1f MB)\n" % (ruta, os.path.getsize(ruta) / 1e6))


def main():
    uid, consultar = conectar()

    dominio_cartera = [("user_id", "=", uid), ("is_subscription", "=", True),
                       ("state", "=", "sale")]

    # --- 1. La foto: sale.order, 132 campos de lote + upsell_content aparte ---
    print("=== 1/3: Foto de la cartera ===")
    foto = leer_todo(consultar, "sale.order", dominio_cartera,
                      CAMPOS_SALE_ORDER, "sale.order",
                      limite=LIMITE_SEGURIDAD_CUENTAS)

    print("Leyendo upsell_content orden por orden (con pausa, sin prisa)...")
    errores = 0
    for i, fila in enumerate(foto, 1):
        try:
            r = consultar("sale.order", "read", [[fila["id"]], [CAMPO_ROTO_EN_LOTE]])
            fila[CAMPO_ROTO_EN_LOTE] = r[0].get(CAMPO_ROTO_EN_LOTE)
        except Exception:
            fila[CAMPO_ROTO_EN_LOTE] = None
            errores += 1
        time.sleep(0.15)
        if i % 50 == 0:
            print("   %d/%d..." % (i, len(foto)))
    print("upsell_content: %d de %d leídos, %d errores individuales\n"
          % (len(foto) - errores, len(foto), errores))

    guardar("cartera_foto.json", foto)

    ids_ordenes = [f["id"] for f in foto]

    # --- 2. El libro de eventos: sale.order.log, ligado a las mismas órdenes ---
    print("=== 2/3: Libro de eventos de MRR ===")
    esquema_log = consultar("sale.order.log", "fields_get", [], {"attributes": ["type"]})
    campos_log = sorted(esquema_log.keys())
    eventos = leer_todo(consultar, "sale.order.log",
                        [("order_id", "in", ids_ordenes)],
                        campos_log, "sale.order.log")
    guardar("cartera_eventos_log.json", eventos)

    # --- 3. Última conexión: openerp.enterprise.database ---
    print("=== 3/3: Última conexión ===")
    esquema_db = consultar("openerp.enterprise.database", "fields_get", [],
                           {"attributes": ["type"]})
    campos_db = sorted(esquema_db.keys())
    conexiones = leer_todo(consultar, "openerp.enterprise.database",
                           [("subscription_id", "in", ids_ordenes)],
                           campos_db, "openerp.enterprise.database")
    guardar("cartera_conexiones.json", conexiones)

    print("Listo. 3 archivos en %s" % CARPETA_SALIDA)


if __name__ == "__main__":
    main()
