from serialhub.protocols.dlms_gurux import GuruxDlmsDecoder


def test_decoder_instantiates() -> None:
    decoder = GuruxDlmsDecoder()
    result = decoder.decode(b"\x7E\xA0\x01\x00\x7E")

    assert result.protocol == "dlms-gurux"
    assert isinstance(result.lines, list)
