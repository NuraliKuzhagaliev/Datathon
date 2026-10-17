"""Rebuild the reviewed public-source registry; does not inspect case footage."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "assets/rules/sources/V1900019680-2026-10-17.ax.txt"
sha = hashlib.sha256(source.read_bytes()).hexdigest()
title = "Правила осуществления кассовых операций и операций по инкассации банкнот, монет и ценностей в банках второго уровня, филиалах банков-нерезидентов Республики Казахстан, Национальном операторе почты и юридических лицах, исключительной деятельностью которых является инкассация банкнот, монет и ценностей (постановление НБРК от 29.11.2019 № 231)"
entries = [
    (
        "NB231-22",
        "Возможное оставление рабочего места до окончания обслуживания",
        22,
        "Обслуживание клиента кассовым работником банка второго уровня; видна активная незавершенная операция.",
        {
            "cashier_serving_customer": "Visible cashier and customer engaged in a cash service sequence.",
            "service_still_active": "Visible transaction context establishes service has not ended, not merely a waiting person.",
            "cashier_leaves_workplace": "Visible departure from the work area, not reaching, turning or an in-place movement.",
        },
        [
            "Обслуживание уже завершено.",
            "Сотрудник остается на рабочем месте.",
            "Не видны границы операции или рабочего места.",
        ],
        True,
    ),
    (
        "NB231-20-PRESENCE",
        "Возможный пересчет принимаемых денег без клиента",
        20,
        "Только прием и пересчет вносимых клиентом наличных денег; не внутренний пересчет после завершенного приема.",
        {
            "incoming_cash": "Visible cash being received from this customer, not inferred ledger data.",
            "cash_counting": "A visible counting action on that incoming cash.",
            "customer_absent": "The entire relevant customer area is visible and the customer is absent during receipt/counting.",
        },
        [
            "Внутренний пересчет ранее принятых денег.",
            "Выдача денег клиенту.",
            "Клиент или необходимая часть пространства вне кадра.",
        ],
        False,
    ),
    (
        "NB231-21",
        "Раздельный прием по приходным документам",
        21,
        "Несколько различимых приходных кассовых документов одного клиента.",
        {
            "separate_incoming_documents_visible": "Documents and amounts must be independently legible.",
            "cash_not_received_separately": "Complete visible sequence proves combined receipt.",
        },
        ["Нечитаемые документы.", "Электронная процедура не видна."],
        False,
    ),
    (
        "NB231-24",
        "Осмотр целостности и пломб сумки",
        24,
        "Прием наличных от подразделения инкассации или инкассаторской организации.",
        {
            "collection_bag_received": "A collection context is established from visible actions.",
            "inspection_omitted": "Complete unobscured start/end prove inspection omission.",
        },
        ["Инспекция могла происходить вне кадра.", "Пломба неразличима."],
        False,
    ),
    (
        "NB231-25",
        "Вскрытие поврежденной сумки при инкассаторе",
        25,
        "Видимое нарушение целостности инкассаторской сумки, ее вскрытие и пересчет.",
        {
            "damaged_collection_bag": "Damage and collection context are clearly visible.",
            "opening_and_counting": "Both opening and recount are visible.",
            "collector_absent": "Full relevant area proves absence, without inferring identity or authorization.",
        },
        ["Целостность или роль участника не устанавливается по видео."],
        False,
    ),
    (
        "NB231-42",
        "Контроль внутреннего пересчета и упаковки",
        42,
        "Внутренний пересчет, сортировка или упаковка; прямо исключены прием и выдача наличных клиенту.",
        {
            "internal_operation": "Context establishes internal sorting/counting/packing.",
            "no_customer_receipt_payment": "Ordinary customer receipt/payment exception is ruled out.",
            "no_supervising_worker_visible": "Complete relevant area and sequence are visible, without identity/permission inference.",
        },
        [
            "Обычный прием или выдача наличных клиенту.",
            "Контролирующий сотрудник может быть за кадром.",
        ],
        False,
    ),
]
rules = []
for rule_id, name, clause, applicability, predicates, exclusions, enabled in entries:
    rules.append(
        {
            "public": {
                "rule_id": rule_id,
                "display_name": name,
                "document_title": title,
                "source_url": "https://adilet.zan.kz/rus/docs/V1900019680",
                "clause": f"пункт {clause}",
                "revision": "Консолидированный текст Adilet, проверен 17.10.2026; содержит поправки 30.06.2026; выбранные пункты без пометки об изменении.",
                "effective_date": "2020-01-01",
                "applicability": applicability,
                "exclusions": exclusions,
                "enabled": enabled,
                "source_sha256": sha,
            },
            "predicates": predicates,
            "context": "Полная видимая последовательность до и после события; проверка добросовестного объяснения. Не выводить отсутствие из окклюзии.",
            "snapshot": "sources/" + source.name,
            "template": f"Возможный признак несоблюдения пункта {clause} Правил № 231. Требуется проверка человеком с учетом контекста; это не юридическое заключение.",
        }
    )
(ROOT / "assets/rules/registry.json").write_text(
    json.dumps(
        {"version": "2026-10-17.1", "rules": rules}, ensure_ascii=False, indent=2
    ),
    encoding="utf-8",
)
