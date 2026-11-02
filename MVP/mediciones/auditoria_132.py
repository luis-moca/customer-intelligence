"""
Auditoria completa de los 132 campos de CAMPOS_SALE_ORDER: donde quedo cada
uno, con razon explicita. Se corre para verificar que la suma da 132 exacto
(el proyecto ya se equivoco de aritmetica antes, no se repite a ciegas).
"""
# 'rutas' va PRIMERO: es quien pone motor/ en el camino de busqueda — sin eso,
# el import de abajo falla al correr desde esta carpeta.
import rutas  # noqa: F401
from exportar_todo import CAMPOS_SALE_ORDER

# --- 1. YA EN EL PANEL Y YA EN EL MODELO (usados hoy en backtest_temporal.py) ---
EN_MODELO_HOY = [
    "recurring_monthly",  # -> mrr, del log
    "country_id", "industry_id", "plan_billing_period_unit", "hosting",
    "l10n_mx_edi_cfdi_to_public", "l10n_mx_edi_partner_address_complete",
    "first_contract_date",  # -> antiguedad_meses, dias_hasta_aniversario
]

# --- 2. YA EN EL PANEL (atributos_estaticos) PERO EXCLUIDOS DEL MODELO A OJO
#         — esto es exactamente lo que hice mal: estaban listos y no entraron ---
EN_PANEL_NO_EN_MODELO = [
    "plan_id", "source_id", "medium_id", "campaign_id", "team_id",
    "company_id", "currency_id", "pricelist_id", "has_odoo_sh",
    "l10n_mx_edi_usage", "l10n_mx_edi_payment_method_id",
]

# --- 3. LLAVES: identifican, no predicen. No son "descartados", son otra cosa ---
LLAVES = [
    "id", "name", "partner_id", "commercial_partner_id", "subscription_id",
    "order_log_ids", "opportunity_id", "database_ids", "project_id",
    "invoice_ids", "message_ids", "tasks_ids", "order_line", "origin_order_id",
    "upsell_order_id", "user_id", "subscription_state",
]

# --- 4. EXCLUIDOS CON RAZON YA MEDIDA en fases anteriores (fuga confirmada,
#         o ya estaba en el "43 fuera" de campos_export.md) ---
EXCLUIDO_RAZON_MEDIDA = {
    "enterprise_users": "FUGA CONFIRMADA: 519/519 churn en 0 vs 1460/1460 activas con usuarios.",
    "end_date": "FUGA CONFIRMADA: 97% lleno en churn vs 2% en activas.",
    "close_reason_id": "solo existe si ya churneo — etiqueta post-mortem, no predictor.",
    "invoice_status": "categorizado como ETIQUETA/DIAGNOSTICO desde el inicio del proyecto.",
    "country_code": "es el pais de quien factura (siempre casi el mismo), no el del cliente.",
    "currency_rate": "tipo de cambio del dia — disfraz de la fecha.",
    "database_count": "vale 1 en todas las cuentas, cero varianza.",
    "display_name": "duplica name + cliente.",
    "enterprise_saas": "redundante — hosting ya dice lo mismo con 3 valores.",
    "client_order_ref": "referencia unica por orden, sin señal.",
    "note_order": "autorreferencia de la orden, plomeria.",
    "message_attachment_count": "contador congelado sin señal propia.",
    "message_partner_ids": "empleados suscritos, no contactos del cliente.",
    "my_activity_date_deadline": "su valor depende de QUIEN consulta — roto como dato.",
    "partner_invoice_id": "= partner_id en la enorme mayoria de casos.",
    "partner_shipping_id": "se vende software, no se envian cajas.",
    "partner_status": "HTML crudo, no un dato limpio.",
    "project_account_id": "duplica project_id.",
    "project_ids": "duplica project_count.",
    "website_order_line": "subconjunto de order_line.",
    "recurring_details": "HTML imprimible, mismo contenido que order_line.",
    "starred_user_ids": "preferencia de vista personal del CS, no dato del cliente.",
    "subscription_tag_ids": "estilo personal del CS — sirve dentro de UNA cartera, no al mezclar.",
    "tag_ids": "misma razon que subscription_tag_ids.",
    "validity_date": "confirmado por Luis: es vigencia de cotizacion, no el contrato.",
    "warehouse_id": "casi constante, no hay logistica fisica en el negocio.",
    "website_message_ids": "subconjunto de message_ids.",
    "note": "texto legal repetido (terminos y condiciones), no señal.",
    "activity_ids": "redundante con activity_state/deadline/type.",
    "activity_summary": "texto libre, nota personal del CS.",
    "activity_type_icon": "icono de UI, pintura de pantalla.",
    "create_date": "fecha del DOCUMENTO, no del cliente — engaña en renovaciones.",
    "date_order": "misma razon que create_date.",
    "start_date": "fecha de ESTA orden, no la del cliente — engaña en renovaciones.",
    "activity_date_deadline": "capa de accion: 0% churn con actividad abierta (circularidad medida) — se lee para callarse, jamas para entrenar.",
    "activity_state": "misma razon: capa de accion, no entrenamiento.",
    "activity_type_id": "misma razon: capa de accion, no entrenamiento.",
    "activity_user_id": "misma razon: capa de accion, no entrenamiento.",
}

# --- 5. LOS QUE NADIE DECIDIO. Existian, campos_export.md los tenia dentro
#         de los 104/133, pero nunca llegaron al panel ni se evaluaron. ESTA
#         es la lista que te debia completa. ---
NUNCA_EVALUADOS = [
    "amount_invoiced", "amount_paid", "amount_to_invoice", "amount_unpaid",
    "amount_total", "cart_quantity", "commission_plan_id", "contract_value",
    "create_uid", "closed_task_count", "completed_task_percentage",
    "enterprise_has_download", "enterprise_is_enterprise", "fiscal_position_id",
    "history_count", "internal_note", "internal_note_display", "invoice_count",
    "invoice_date_diff", "is_closing", "is_renewing", "is_upselling",
    "locked", "maintenance_is_activated", "maintenance_is_paying",
    "next_invoice_date", "expected_next_invoice_date", "last_invoice_date",
    "non_recurring_total", "odoo_sh_extra_gb", "odoo_sh_extra_stagings",
    "odoo_sh_extra_workers", "odoo_sh_project_activated", "origin",
    "payment_term_id", "payment_token_id", "pending_transaction",
    "percentage_satisfaction", "prepayment_percent", "project_count",
    "rating_avg_text", "rating_percentage_satisfaction", "recurring_total",
    "renewal_count", "require_payment", "require_signature",
    "sale_order_template_id", "subscription_child_ids", "subscription_task_ids",
    "tasks_count", "team_currency_id", "team_user_id", "timesheet_count",
    "timesheet_total_duration", "to_renew", "transition_date", "upsell_count",
    "version",
]


def main():
    todos = set(CAMPOS_SALE_ORDER)
    grupos = {
        "1. Ya en el modelo hoy": EN_MODELO_HOY,
        "2. En el panel, excluidos del modelo a ojo (el error)": EN_PANEL_NO_EN_MODELO,
        "3. Llaves (no son features)": LLAVES,
        "4. Excluidos con razon ya medida": sorted(EXCLUIDO_RAZON_MEDIDA.keys()),
        "5. NUNCA EVALUADOS (el hueco real)": NUNCA_EVALUADOS,
    }

    vistos = set()
    for nombre, lista in grupos.items():
        print("%s: %d campos" % (nombre, len(lista)))
        for c in lista:
            if c not in todos:
                print("   [ERROR] '%s' no esta en CAMPOS_SALE_ORDER" % c)
            if c in vistos:
                print("   [ERROR] '%s' esta repetido en otra categoria" % c)
            vistos.add(c)

    total = sum(len(l) for l in grupos.values())
    print("\nTOTAL clasificado: %d" % total)
    print("CAMPOS_SALE_ORDER tiene: %d" % len(CAMPOS_SALE_ORDER))

    faltantes = todos - vistos
    if faltantes:
        print("\n[ERROR] %d campos de CAMPOS_SALE_ORDER no aparecen en NINGUNA categoria:"
              % len(faltantes))
        for c in sorted(faltantes):
            print("   ", c)
    else:
        print("\nOK: los 132 quedaron clasificados, ninguno perdido, ninguno repetido.")


if __name__ == "__main__":
    main()
