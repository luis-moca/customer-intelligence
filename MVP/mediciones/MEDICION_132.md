# Medicion de los 132 campos — 3 desenlaces, 9 carteras

Suscripciones: 1987

- Tasa base **expansion**: 71.3%
- Tasa base **contraccion**: 29.1%
- Tasa base **churn**: 25.8%

Veredicto por reglas, no por opinion. Propuesta para que Luis decida.

| Campo | Lleno | Val. | EXPANSION | CONTRACCION | CHURN | Global |
|---|---|---|---|---|---|---|
| `pending_transaction` | 100% | 2 | NADA False -> 71% (n=1977) | NADA False -> 29% (n=1977) | NADA False -> 26% (n=1977) | **CASI CONSTANTE** |
| `percentage_satisfaction` | 100% | 2 | NADA -1 -> 71% (n=1985) | NADA -1 -> 29% (n=1985) | NADA -1 -> 26% (n=1985) | **CASI CONSTANTE** |
| `team_currency_id` | 100% | 2 | NADA 35 -> 71% (n=1986) | NADA 35 -> 29% (n=1986) | NADA 35 -> 26% (n=1986) | **CASI CONSTANTE** |
| `team_id` | 100% | 2 | NADA 167 -> 71% (n=1978) | NADA 167 -> 29% (n=1978) | NADA 167 -> 25% (n=1978) | **CASI CONSTANTE** |
| `team_user_id` | 100% | 2 | NADA 2296248 -> 71% (n=1978) | NADA 2296248 -> 29% (n=1978) | NADA 2296248 -> 25% (n=1978) | **CASI CONSTANTE** |
| `locked` | 100% | 1 | NADA  | NADA  | NADA  | **CONSTANTE** |
| `rating_avg_text` | 100% | 1 | NADA  | NADA  | NADA  | **CONSTANTE** |
| `rating_percentage_satisfaction` | 100% | 1 | NADA  | NADA  | NADA  | **CONSTANTE** |
| `order_log_ids` | 100% | 31 | FUGA 1 -> 0% (n=246) | FUGA 7 -> 77% (n=52) | FUGA 1 -> 0% (n=246) | **FUGA EN LOS 3** |
| `activity_user_id` | 15% | 14 | FUERTE 7630795 -> 85% (n=52) | FUERTE 7630795 -> 40% (n=52) | FUGA 3852650 -> 0% (n=70) | **FUGA PARCIAL** |
| `close_reason_id` | 27% | 16 | DEBIL 142 -> 79% (n=188) | FUERTE 142 -> 15% (n=188) | FUGA 142 -> 100% (n=188) | **FUGA PARCIAL** |
| `closed_task_count` | 14% | 14 | FUGA 2 -> 100% (n=59) | FUGA 2 -> 0% (n=59) | FUERTE 2 -> 10% (n=59) | **FUGA PARCIAL** |
| `enterprise_has_download` | 100% | 2 | NADA True -> 69% (n=962) | DEBIL True -> 24% (n=962) | FUGA True -> 0% (n=962) | **FUGA PARCIAL** |
| `enterprise_is_enterprise` | 100% | 2 | NADA False -> 72% (n=526) | DEBIL False -> 22% (n=526) | FUGA False -> 97% (n=526) | **FUGA PARCIAL** |
| `enterprise_users` | 74% | 58 | FUERTE 3 -> 61% (n=223) | DEBIL 0 -> 22% (n=526) | FUGA 0 -> 97% (n=526) | **FUGA PARCIAL** |
| `maintenance_is_activated` | 100% | 2 | FUERTE True -> 86% (n=650) | DEBIL True -> 20% (n=650) | FUGA True -> 0% (n=650) | **FUGA PARCIAL** |
| `maintenance_is_paying` | 100% | 2 | FUERTE True -> 83% (n=252) | DEBIL True -> 34% (n=252) | FUGA True -> 0% (n=252) | **FUGA PARCIAL** |
| `payment_term_id` | 98% | 10 | FUERTE 8 -> 90% (n=68) | FUERTE 8 -> 16% (n=68) | FUGA 8 -> 0% (n=68) | **FUGA PARCIAL** |
| `subscription_state` | 100% | 2 | NADA 6_churn -> 72% (n=526) | DEBIL 6_churn -> 22% (n=526) | FUGA 6_churn -> 97% (n=526) | **FUGA PARCIAL** |
| `activity_date_deadline` | 15% | 93 | NADA False -> 70% (n=1692) | NADA False -> 28% (n=1692) | DEBIL False -> 29% (n=1692) | **SEÑAL DEBIL** |
| `activity_summary` | 15% | 193 | NADA False -> 70% (n=1694) | NADA False -> 28% (n=1694) | DEBIL False -> 29% (n=1694) | **SEÑAL DEBIL** |
| `amount_invoiced` | 44% | 403 | NADA 0.0 -> 70% (n=1113) | DEBIL 0.0 -> 35% (n=1113) | NADA 0.0 -> 27% (n=1113) | **SEÑAL DEBIL** |
| `amount_unpaid` | 33% | 415 | DEBIL 0.0 -> 63% (n=1338) | DEBIL 0.0 -> 34% (n=1338) | NADA 0.0 -> 23% (n=1338) | **SEÑAL DEBIL** |
| `campaign_id` | 15% | 178 | DEBIL False -> 67% (n=1691) | NADA False -> 31% (n=1691) | NADA False -> 25% (n=1691) | **SEÑAL DEBIL** |
| `country_id` | 100% | 8 | NADA 168 -> 70% (n=227) | DEBIL 168 -> 25% (n=227) | DEBIL 168 -> 17% (n=227) | **SEÑAL DEBIL** |
| `enterprise_saas` | 100% | 2 | NADA False -> 72% (n=441) | DEBIL False -> 32% (n=441) | NADA False -> 28% (n=441) | **SEÑAL DEBIL** |
| `fiscal_position_id` | 99% | 9 | NADA 109 -> 72% (n=263) | NADA 137 -> 31% (n=442) | DEBIL 109 -> 19% (n=263) | **SEÑAL DEBIL** |
| `has_odoo_sh` | 100% | 2 | DEBIL True -> 77% (n=299) | DEBIL True -> 38% (n=299) | DEBIL True -> 18% (n=299) | **SEÑAL DEBIL** |
| `l10n_mx_edi_cfdi_to_public` | 100% | 2 | DEBIL True -> 77% (n=880) | NADA True -> 31% (n=880) | NADA True -> 23% (n=880) | **SEÑAL DEBIL** |
| `l10n_mx_edi_usage` | 96% | 6 | DEBIL False -> 80% (n=76) | DEBIL False -> 21% (n=76) | DEBIL False -> 34% (n=76) | **SEÑAL DEBIL** |
| `non_recurring_total` | 21% | 97 | DEBIL 0.0 -> 64% (n=1572) | DEBIL 0.0 -> 35% (n=1572) | NADA 0.0 -> 29% (n=1572) | **SEÑAL DEBIL** |
| `odoo_sh_extra_stagings` | 15% | 5 | DEBIL 1 -> 76% (n=266) | DEBIL 1 -> 38% (n=266) | DEBIL 1 -> 18% (n=266) | **SEÑAL DEBIL** |
| `odoo_sh_extra_workers` | 15% | 8 | NADA 1 -> 73% (n=239) | DEBIL 1 -> 37% (n=239) | DEBIL 1 -> 20% (n=239) | **SEÑAL DEBIL** |
| `odoo_sh_project_activated` | 100% | 2 | DEBIL True -> 78% (n=289) | DEBIL True -> 38% (n=289) | DEBIL True -> 18% (n=289) | **SEÑAL DEBIL** |
| `payment_token_id` | 46% | 895 | DEBIL False -> 75% (n=1081) | DEBIL False -> 22% (n=1081) | NADA False -> 27% (n=1081) | **SEÑAL DEBIL** |
| `timesheet_count` | 20% | 169 | DEBIL 0.0 -> 64% (n=1580) | DEBIL 0.0 -> 35% (n=1580) | NADA 0.0 -> 29% (n=1580) | **SEÑAL DEBIL** |
| `timesheet_total_duration` | 20% | 138 | DEBIL 0 -> 64% (n=1581) | DEBIL 0 -> 35% (n=1581) | NADA 0 -> 29% (n=1581) | **SEÑAL DEBIL** |
| `activity_ids` | 15% | 6 | FUERTE 1 -> 82% (n=241) | DEBIL 1 -> 37% (n=241) | FUERTE 1 -> 9% (n=241) | **SEÑAL FUERTE** |
| `activity_state` | 15% | 4 | DEBIL overdue -> 81% (n=207) | DEBIL overdue -> 36% (n=207) | FUERTE overdue -> 8% (n=207) | **SEÑAL FUERTE** |
| `activity_type_icon` | 15% | 7 | DEBIL fa-tasks -> 79% (n=212) | DEBIL fa-tasks -> 37% (n=212) | FUERTE fa-tasks -> 6% (n=212) | **SEÑAL FUERTE** |
| `activity_type_id` | 15% | 9 | FUERTE 26 -> 83% (n=59) | FUERTE 26 -> 44% (n=59) | FUERTE 4 -> 5% (n=150) | **SEÑAL FUERTE** |
| `amount_paid` | 78% | 1104 | NADA 0.0 -> 72% (n=434) | DEBIL 0.0 -> 20% (n=434) | FUERTE 0.0 -> 15% (n=434) | **SEÑAL FUERTE** |
| `amount_to_invoice` | 20% | 184 | NADA 0.0 -> 69% (n=1590) | NADA 0.0 -> 31% (n=1590) | FUERTE 0.0 -> 9% (n=1590) | **SEÑAL FUERTE** |
| `amount_total` | 100% | 1020 | FUERTE 489.6 -> 56% (n=75) | FUERTE 489.6 -> 17% (n=75) | FUERTE 489.6 -> 36% (n=75) | **SEÑAL FUERTE** |
| `cart_quantity` | 100% | 170 | FUERTE 2 -> 46% (n=67) | FUERTE 2 -> 51% (n=67) | FUERTE 1 -> 79% (n=120) | **SEÑAL FUERTE** |
| `completed_task_percentage` | 14% | 25 | FUERTE 1.0 -> 97% (n=171) | FUERTE 1.0 -> 7% (n=171) | NADA 0.0 -> 27% (n=1708) | **SEÑAL FUERTE** |
| `contract_value` | 100% | 844 | DEBIL 1020.0 -> 62% (n=55) | FUERTE 732.47 -> 12% (n=67) | FUERTE 732.47 -> 46% (n=67) | **SEÑAL FUERTE** |
| `create_uid` | 100% | 532 | FUERTE 9349015 -> 29% (n=68) | FUERTE 10076004 -> 41% (n=54) | FUERTE 10076004 -> 4% (n=54) | **SEÑAL FUERTE** |
| `database_count` | 97% | 3 | DEBIL 0 -> 75% (n=65) | FUERTE 0 -> 18% (n=65) | FUERTE 0 -> 89% (n=65) | **SEÑAL FUERTE** |
| `database_ids` | 97% | 3 | DEBIL 0 -> 75% (n=65) | FUERTE 0 -> 18% (n=65) | FUERTE 0 -> 89% (n=65) | **SEÑAL FUERTE** |
| `end_date` | 27% | 375 | NADA False -> 71% (n=1446) | NADA False -> 32% (n=1446) | FUERTE False -> 1% (n=1446) | **SEÑAL FUERTE** |
| `history_count` | 64% | 32 | FUERTE 4 -> 55% (n=152) | FUERTE 7 -> 44% (n=50) | FUERTE 0 -> 41% (n=720) | **SEÑAL FUERTE** |
| `hosting` | 100% | 3 | FUERTE premise -> 54% (n=94) | DEBIL paas -> 39% (n=306) | DEBIL paas -> 19% (n=306) | **SEÑAL FUERTE** |
| `industry_id` | 25% | 19 | DEBIL 19 -> 65% (n=110) | FUERTE 19 -> 41% (n=110) | FUERTE 7 -> 16% (n=89) | **SEÑAL FUERTE** |
| `internal_note` | 53% | 867 | FUERTE False -> 47% (n=929) | DEBIL False -> 38% (n=929) | DEBIL False -> 19% (n=929) | **SEÑAL FUERTE** |
| `internal_note_display` | 91% | 1545 | FUERTE False -> 58% (n=169) | DEBIL False -> 21% (n=169) | FUERTE False -> 56% (n=169) | **SEÑAL FUERTE** |
| `invoice_count` | 100% | 80 | FUERTE 5 -> 42% (n=60) | FUERTE 1 -> 2% (n=441) | FUERTE 3 -> 10% (n=175) | **SEÑAL FUERTE** |
| `invoice_date_diff` | 33% | 127 | FUERTE 365 -> 86% (n=135) | FUERTE 365 -> 11% (n=135) | FUERTE 365 -> 99% (n=135) | **SEÑAL FUERTE** |
| `invoice_ids` | 100% | 80 | FUERTE 5 -> 42% (n=60) | FUERTE 1 -> 2% (n=441) | FUERTE 3 -> 10% (n=175) | **SEÑAL FUERTE** |
| `invoice_status` | 100% | 4 | DEBIL no -> 80% (n=773) | DEBIL no -> 23% (n=773) | FUERTE to invoice -> 61% (n=122) | **SEÑAL FUERTE** |
| `is_renewing` | 100% | 2 | FUERTE True -> 83% (n=653) | FUERTE True -> 39% (n=653) | FUERTE True -> 40% (n=653) | **SEÑAL FUERTE** |
| `is_upselling` | 100% | 2 | FUERTE True -> 85% (n=286) | DEBIL True -> 24% (n=286) | DEBIL True -> 19% (n=286) | **SEÑAL FUERTE** |
| `l10n_mx_edi_payment_method_id` | 91% | 6 | FUERTE 18 -> 84% (n=57) | FUERTE 3 -> 14% (n=152) | FUERTE False -> 45% (n=173) | **SEÑAL FUERTE** |
| `medium_id` | 17% | 20 | FUERTE 6 -> 94% (n=239) | FUERTE 6 -> 18% (n=239) | DEBIL 6 -> 31% (n=239) | **SEÑAL FUERTE** |
| `message_attachment_count` | 100% | 78 | FUERTE 2 -> 39% (n=199) | FUERTE 8 -> 17% (n=88) | FUERTE 14 -> 46% (n=50) | **SEÑAL FUERTE** |
| `message_partner_ids` | 100% | 11 | DEBIL 1 -> 76% (n=107) | FUERTE 1 -> 17% (n=107) | FUERTE 1 -> 9% (n=107) | **SEÑAL FUERTE** |
| `note` | 100% | 681 | FUERTE <p>

<span sty -> 58% (n=99) | FUERTE <p data-oe-ver -> 45% (n=74) | FUERTE <p>

<span sty -> 63% (n=99) | **SEÑAL FUERTE** |
| `odoo_sh_extra_gb` | 15% | 94 | FUERTE 100 -> 93% (n=71) | NADA 100 -> 31% (n=71) | FUERTE 100 -> 11% (n=71) | **SEÑAL FUERTE** |
| `opportunity_id` | 40% | 794 | FUERTE False -> 55% (n=1193) | FUERTE False -> 40% (n=1193) | NADA False -> 24% (n=1193) | **SEÑAL FUERTE** |
| `order_line` | 100% | 14 | FUERTE 7 -> 92% (n=75) | FUERTE 6 -> 17% (n=169) | FUERTE 7 -> 5% (n=75) | **SEÑAL FUERTE** |
| `origin` | 93% | 1763 | FUERTE SaaS Subscript -> 95% (n=81) | DEBIL False -> 21% (n=129) | FUERTE False -> 45% (n=129) | **SEÑAL FUERTE** |
| `origin_order_id` | 43% | 849 | FUERTE False -> 89% (n=1139) | FUERTE False -> 19% (n=1139) | DEBIL False -> 35% (n=1139) | **SEÑAL FUERTE** |
| `partner_status` | 100% | 2 | NADA <i class="fa f -> 69% (n=55) | DEBIL <i class="fa f -> 35% (n=55) | FUERTE <i class="fa f -> 13% (n=55) | **SEÑAL FUERTE** |
| `plan_billing_period_unit` | 100% | 2 | DEBIL month -> 75% (n=666) | FUERTE month -> 43% (n=666) | FUERTE month -> 38% (n=666) | **SEÑAL FUERTE** |
| `plan_id` | 100% | 7 | FUERTE 178 -> 92% (n=96) | FUERTE 173 -> 43% (n=665) | FUERTE 176 -> 1% (n=159) | **SEÑAL FUERTE** |
| `project_account_id` | 19% | 3 | FUERTE 114208 -> 90% (n=366) | FUERTE 114208 -> 9% (n=366) | FUERTE 114208 -> 8% (n=366) | **SEÑAL FUERTE** |
| `project_count` | 24% | 3 | FUERTE 1 -> 91% (n=465) | FUERTE 1 -> 9% (n=465) | FUERTE 1 -> 13% (n=465) | **SEÑAL FUERTE** |
| `project_id` | 19% | 3 | FUERTE 2831 -> 90% (n=366) | FUERTE 2831 -> 9% (n=366) | FUERTE 2831 -> 8% (n=366) | **SEÑAL FUERTE** |
| `project_ids` | 24% | 3 | FUERTE 1 -> 91% (n=465) | FUERTE 1 -> 9% (n=465) | FUERTE 1 -> 13% (n=465) | **SEÑAL FUERTE** |
| `recurring_details` | 100% | 1147 | DEBIL <div class="pb -> 66% (n=53) | FUERTE <div class="pb -> 17% (n=53) | FUERTE <div class="pb -> 43% (n=53) | **SEÑAL FUERTE** |
| `recurring_monthly` | 100% | 830 | DEBIL 40.8 -> 64% (n=88) | FUERTE 40.8 -> 15% (n=88) | FUERTE 54.4 -> 40% (n=52) | **SEÑAL FUERTE** |
| `recurring_total` | 100% | 888 | FUERTE 489.6 -> 60% (n=80) | FUERTE 489.6 -> 16% (n=80) | FUERTE 489.6 -> 39% (n=80) | **SEÑAL FUERTE** |
| `renewal_count` | 33% | 15 | FUERTE 3 -> 85% (n=67) | FUERTE 2 -> 43% (n=132) | FUERTE 2 -> 46% (n=132) | **SEÑAL FUERTE** |
| `require_payment` | 100% | 2 | FUERTE False -> 87% (n=193) | DEBIL False -> 22% (n=193) | FUERTE False -> 37% (n=193) | **SEÑAL FUERTE** |
| `require_signature` | 100% | 2 | DEBIL False -> 78% (n=423) | FUERTE False -> 42% (n=423) | DEBIL False -> 33% (n=423) | **SEÑAL FUERTE** |
| `sale_order_template_id` | 100% | 13 | FUERTE 92 -> 93% (n=94) | FUERTE 87 -> 44% (n=518) | FUERTE 90 -> 1% (n=148) | **SEÑAL FUERTE** |
| `source_id` | 18% | 23 | FUERTE 85771 -> 94% (n=207) | FUERTE 85771 -> 18% (n=207) | DEBIL 85771 -> 32% (n=207) | **SEÑAL FUERTE** |
| `starred_user_ids` | 70% | 3 | FUERTE 0 -> 82% (n=588) | NADA 0 -> 26% (n=588) | DEBIL 0 -> 34% (n=588) | **SEÑAL FUERTE** |
| `subscription_child_ids` | 62% | 28 | FUERTE 7 -> 98% (n=52) | FUERTE 7 -> 44% (n=52) | DEBIL 4 -> 17% (n=114) | **SEÑAL FUERTE** |
| `subscription_id` | 43% | 849 | FUERTE False -> 89% (n=1139) | FUERTE False -> 19% (n=1139) | DEBIL False -> 35% (n=1139) | **SEÑAL FUERTE** |
| `subscription_tag_ids` | 98% | 4 | FUERTE 2 -> 84% (n=193) | FUERTE 3 -> 44% (n=77) | FUERTE 3 -> 53% (n=77) | **SEÑAL FUERTE** |
| `subscription_task_ids` | 80% | 94 | DEBIL 5 -> 63% (n=79) | FUERTE 8 -> 47% (n=55) | FUERTE 0 -> 47% (n=396) | **SEÑAL FUERTE** |
| `tag_ids` | 75% | 17 | FUERTE 8 -> 60% (n=60) | DEBIL 7 -> 21% (n=76) | FUERTE 7 -> 12% (n=76) | **SEÑAL FUERTE** |
| `tasks_count` | 21% | 17 | FUERTE 2 -> 98% (n=80) | FUERTE 2 -> 2% (n=80) | FUERTE 2 -> 10% (n=80) | **SEÑAL FUERTE** |
| `tasks_ids` | 21% | 17 | FUERTE 2 -> 98% (n=80) | FUERTE 2 -> 2% (n=80) | FUERTE 2 -> 10% (n=80) | **SEÑAL FUERTE** |
| `to_renew` | 100% | 2 | DEBIL True -> 78% (n=350) | FUERTE True -> 18% (n=350) | FUERTE True -> 83% (n=350) | **SEÑAL FUERTE** |
| `upsell_count` | 14% | 9 | FUERTE 1 -> 81% (n=199) | DEBIL 1 -> 25% (n=199) | DEBIL 1 -> 19% (n=199) | **SEÑAL FUERTE** |
| `user_id` | 100% | 9 | DEBIL 7630795 -> 78% (n=181) | DEBIL 9349015 -> 23% (n=216) | FUERTE 3852650 -> 51% (n=323) | **SEÑAL FUERTE** |
| `version` | 97% | 26 | FUERTE 16.0 -> 42% (n=67) | FUERTE False -> 18% (n=66) | FUERTE False -> 89% (n=66) | **SEÑAL FUERTE** |
| `warehouse_id` | 100% | 3 | DEBIL 1 -> 68% (n=50) | FUERTE 1 -> 12% (n=50) | FUERTE 1 -> 84% (n=50) | **SEÑAL FUERTE** |
| `website_message_ids` | 99% | 86 | FUERTE 2 -> 25% (n=63) | FUERTE 14 -> 15% (n=66) | FUERTE 16 -> 48% (n=58) | **SEÑAL FUERTE** |
| `website_order_line` | 100% | 10 | FUERTE 3 -> 91% (n=188) | FUERTE 3 -> 12% (n=188) | FUERTE 5 -> 14% (n=117) | **SEÑAL FUERTE** |
| `client_order_ref` | 100% | 1987 | NADA  | NADA  | NADA  | **SIN SEÑAL EN NINGUNO** |
| `commercial_partner_id` | 100% | 1953 | NADA  | NADA  | NADA  | **SIN SEÑAL EN NINGUNO** |
| `company_id` | 100% | 3 | NADA 17 -> 71% (n=1965) | NADA 17 -> 29% (n=1965) | NADA 17 -> 25% (n=1965) | **SIN SEÑAL EN NINGUNO** |
| `country_code` | 100% | 3 | NADA MX -> 71% (n=1965) | NADA MX -> 29% (n=1965) | NADA MX -> 25% (n=1965) | **SIN SEÑAL EN NINGUNO** |
| `create_date` | 100% | 1987 | NADA  | NADA  | NADA  | **SIN SEÑAL EN NINGUNO** |
| `currency_id` | 100% | 3 | NADA 35 -> 71% (n=809) | NADA 35 -> 30% (n=809) | NADA 35 -> 28% (n=809) | **SIN SEÑAL EN NINGUNO** |
| `currency_rate` | 100% | 540 | NADA 1.0 -> 71% (n=822) | NADA 1.0 -> 29% (n=822) | NADA 1.0 -> 29% (n=822) | **SIN SEÑAL EN NINGUNO** |
| `date_order` | 100% | 1565 | NADA  | NADA  | NADA  | **SIN SEÑAL EN NINGUNO** |
| `display_name` | 100% | 1987 | NADA  | NADA  | NADA  | **SIN SEÑAL EN NINGUNO** |
| `expected_next_invoice_date` | 100% | 616 | NADA  | NADA  | NADA  | **SIN SEÑAL EN NINGUNO** |
| `first_contract_date` | 100% | 1026 | NADA  | NADA  | NADA  | **SIN SEÑAL EN NINGUNO** |
| `id` | 100% | 1987 | NADA  | NADA  | NADA  | **SIN SEÑAL EN NINGUNO** |
| `is_closing` | 100% | 2 | NADA False -> 71% (n=1960) | NADA False -> 29% (n=1960) | NADA False -> 26% (n=1960) | **SIN SEÑAL EN NINGUNO** |
| `l10n_mx_edi_partner_address_complete` | 100% | 2 | NADA False -> 73% (n=701) | NADA False -> 29% (n=701) | NADA False -> 28% (n=701) | **SIN SEÑAL EN NINGUNO** |
| `last_invoice_date` | 99% | 773 | NADA  | NADA  | NADA  | **SIN SEÑAL EN NINGUNO** |
| `message_ids` | 100% | 394 | NADA  | NADA  | NADA  | **SIN SEÑAL EN NINGUNO** |
| `name` | 100% | 1987 | NADA  | NADA  | NADA  | **SIN SEÑAL EN NINGUNO** |
| `next_invoice_date` | 100% | 960 | NADA  | NADA  | NADA  | **SIN SEÑAL EN NINGUNO** |
| `note_order` | 100% | 1987 | NADA  | NADA  | NADA  | **SIN SEÑAL EN NINGUNO** |
| `partner_id` | 100% | 1955 | NADA  | NADA  | NADA  | **SIN SEÑAL EN NINGUNO** |
| `partner_invoice_id` | 100% | 1954 | NADA  | NADA  | NADA  | **SIN SEÑAL EN NINGUNO** |
| `partner_shipping_id` | 100% | 1955 | NADA  | NADA  | NADA  | **SIN SEÑAL EN NINGUNO** |
| `prepayment_percent` | 100% | 4 | NADA 1.0 -> 71% (n=1962) | NADA 1.0 -> 30% (n=1962) | NADA 1.0 -> 26% (n=1962) | **SIN SEÑAL EN NINGUNO** |
| `pricelist_id` | 100% | 9 | NADA 181 -> 72% (n=1112) | NADA 181 -> 30% (n=1112) | NADA 179 -> 28% (n=809) | **SIN SEÑAL EN NINGUNO** |
| `start_date` | 100% | 931 | NADA  | NADA  | NADA  | **SIN SEÑAL EN NINGUNO** |
| `transition_date` | 11% | 155 | NADA False -> 69% (n=1761) | NADA False -> 32% (n=1761) | NADA False -> 28% (n=1761) | **SIN SEÑAL EN NINGUNO** |
| `upsell_order_id` | 8% | 169 | NADA False -> 70% (n=1819) | NADA False -> 30% (n=1819) | NADA False -> 26% (n=1819) | **SIN SEÑAL EN NINGUNO** |
| `validity_date` | 98% | 817 | NADA  | NADA  | NADA  | **SIN SEÑAL EN NINGUNO** |
| `commission_plan_id` | 4% | 7 | NADA False -> 72% (n=1914) | NADA False -> 29% (n=1914) | NADA False -> 26% (n=1914) | **VACIO** |
| `my_activity_date_deadline` | 1% | 18 | NADA False -> 71% (n=1970) | NADA False -> 29% (n=1970) | NADA False -> 26% (n=1970) | **VACIO** |
