from __future__ import annotations

import json
from pathlib import Path


EXPORT_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "watson" / "cardioia-dialog.json"
)
EXPECTED_INTENTS = {
    "saudacao",
    "relatar_sintoma",
    "sinal_alerta",
    "preparar_consulta",
    "limites_assistente",
    "agradecimento",
    "despedida",
}
EXPECTED_CUSTOM_ENTITIES = {"sintoma", "intensidade", "confirmacao"}


def load_export():
    return json.loads(EXPORT_PATH.read_text(encoding="utf-8"))


def test_export_is_utf8_json_for_portuguese_dialog_skill():
    raw = EXPORT_PATH.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")

    skill = load_export()
    assert skill["name"] == "CardioIA Acolhe"
    assert skill["language"] == "pt-br"
    assert skill["learning_opt_out"] is True


def test_exactly_seven_intents_have_at_least_five_unique_examples_each():
    skill = load_export()
    intents = {item["intent"]: item for item in skill["intents"]}

    assert set(intents) == EXPECTED_INTENTS
    for name, intent in intents.items():
        examples = [example["text"].strip().casefold() for example in intent["examples"]]
        assert len(examples) >= 5, name
        assert len(examples) == len(set(examples)), name


def test_required_entities_and_synonyms_are_present_and_sys_number_is_enabled():
    skill = load_export()
    entities = {item["entity"]: item for item in skill["entities"]}

    assert EXPECTED_CUSTOM_ENTITIES <= set(entities)
    assert "sys-number" in entities
    for name in EXPECTED_CUSTOM_ENTITIES:
        entity = entities[name]
        assert entity["values"], name
        assert all(value["synonyms"] for value in entity["values"]), name
        for value in entity["values"]:
            synonyms = {item.casefold() for item in value["synonyms"]}
            assert value["value"].casefold() not in synonyms, (name, value["value"])

    assert entities["sys-number"]["values"] == []
    assert skill["system_settings"]["system_entities"]["enabled"] is True
    conditions = " ".join(node["conditions"] for node in skill["dialog_nodes"])
    assert "@sys-number" in conditions


def test_emergency_is_first_fallback_is_last_and_sibling_chain_is_consistent():
    nodes = load_export()["dialog_nodes"]

    assert nodes[0]["dialog_node"] == "node_emergencia"
    assert nodes[-1]["dialog_node"] == "node_fallback"
    assert nodes[-1]["conditions"] == "anything_else"
    assert "sinal_alerta" in nodes[0]["conditions"]
    assert "@sys-number.numeric_value >= 7" in nodes[0]["conditions"]
    assert "$sintoma == 'dor_no_peito'" in nodes[0]["conditions"]

    for previous, current in zip(nodes, nodes[1:]):
        assert current["previous_sibling"] == previous["dialog_node"]


def test_dialog_preserves_required_context_and_has_explicit_clinical_boundaries():
    skill = load_export()
    contexts = [node.get("context", {}) for node in skill["dialog_nodes"]]
    context_keys = set().union(*(context.keys() for context in contexts))

    assert {"sintoma", "intensidade", "duracao"} <= context_keys
    all_responses = " ".join(
        value["text"]
        for node in skill["dialog_nodes"]
        for generic in node["output"]["generic"]
        for value in generic.get("values", [])
    ).casefold()
    emergency_response = skill["dialog_nodes"][0]["output"]["generic"][0]["values"][0][
        "text"
    ].casefold()

    assert "192" in emergency_response
    assert "não realiza diagnóstico" in emergency_response
    assert "não prescrevo" in all_responses
    assert "anything_else" == skill["dialog_nodes"][-1]["conditions"]


def test_first_turn_entity_can_start_collection_without_welcome_context():
    nodes = {
        node["dialog_node"]: node for node in load_export()["dialog_nodes"]
    }
    condition = nodes["node_capturar_sintoma"]["conditions"]

    assert "$etapa == null" in condition
    assert "@sintoma" in condition
