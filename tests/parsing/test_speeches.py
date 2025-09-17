from bundestag_mine_refactor.parsing import parse_speeches


def test_parse_speeches_extracts_multiple_segments():
    text = (
        "Eröffnung der Sitzung\n"
        "Präsidentin Bärbel Bas:\n"
        "Guten Tag, ich eröffne die Sitzung.\n"
        "\n"
        "Dr. Marco Buschmann (FDP):\n"
        "Wir beraten heute wichtige Gesetzesinitiativen. (Beifall)\n"
        "\n"
        "Zuruf von der SPD: Das sehen wir auch so!\n"
        "\n"
        "Bundesministerin Annalena Baerbock:\n"
        "Außenpolitisch stehen wir vor großen Herausforderungen.\n"
    )

    speeches = parse_speeches(text, "TEST-1")

    assert len(speeches) == 3
    assert speeches[0].speaker_name == "Bärbel Bas"
    assert speeches[0].role == "Präsidentin"
    assert speeches[0].party is None
    assert "eröffne die Sitzung" in speeches[0].text

    assert speeches[1].speaker_name == "Dr. Marco Buschmann"
    assert speeches[1].party == "FDP"
    assert "Beifall" not in speeches[1].text

    assert speeches[2].speaker_name == "Annalena Baerbock"
    assert speeches[2].role == "Bundesministerin"
