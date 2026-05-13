from metal_calc.engine.risk_rules import evaluate_rfq_risk_flags


def test_high_volume_flag():
    flags = evaluate_rfq_risk_flags({"quantity": 10000})
    assert any(f.code == "HIGH_VOLUME_ORDER" for f in flags)


def test_unspecified_finish_flag():
    flags = evaluate_rfq_risk_flags({"finish": "nieokreślone"})
    assert any(f.code == "UNSPECIFIED_FINISH" for f in flags)


def test_large_assembly_scope_flag():
    flags = evaluate_rfq_risk_flags(
        {
            "product_family": "structure",
            "component_list": [f"part_{i}" for i in range(20)],
        }
    )
    assert any(f.code == "LARGE_ASSEMBLY_SCOPE" for f in flags)


def test_no_flags_for_standard_case():
    flags = evaluate_rfq_risk_flags(
        {
            "quantity": 100,
            "finish": "surowe",
            "product_family": "wire",
            "component_list": ["A", "B"],
        }
    )
    assert flags == []
