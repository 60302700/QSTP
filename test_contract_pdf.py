"""ponytail self-check: dummy contract PDF is a structurally valid PDF."""
import re

from resend_mail import _dummy_contract_pdf


def test_dummy_contract_pdf():
    pdf = _dummy_contract_pdf("Ada Lovelace", "Acme Startup", "Backend Intern")

    assert pdf.startswith(b"%PDF-1.4")
    assert pdf.endswith(b"%%EOF")
    assert b"Ada Lovelace" in pdf
    assert b"Acme Startup" in pdf

    # every "N 0 obj" offset recorded in xref must point at the real byte offset
    xref_pos = pdf.rindex(b"\nxref\n")
    xref_table = pdf[xref_pos:].decode("latin-1")
    offsets = [int(line[:10]) for line in xref_table.splitlines()[4:9]]
    for i, off in enumerate(offsets, start=1):
        assert pdf[off:off + len(f"{i} 0 obj".encode())] == f"{i} 0 obj".encode()


if __name__ == "__main__":
    test_dummy_contract_pdf()
    print("ok")
