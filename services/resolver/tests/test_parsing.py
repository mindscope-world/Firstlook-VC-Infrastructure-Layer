from email.message import EmailMessage

from firstlook_resolver.parsing import (
    clean_body,
    html_to_text,
    parse_rfc822,
    parse_signature,
    split_signature,
    strip_quoted,
)


def make_email(text=None, html=None, attachments=(), **headers) -> bytes:
    msg = EmailMessage()
    msg["From"] = headers.get("from_", "Wanjiru Kamau <wanjiru@mpesa-tools.co.ke>")
    msg["To"] = headers.get("to", "Paul Otieno <paul@savanna.vc>")
    if "cc" in headers:
        msg["Cc"] = headers["cc"]
    msg["Subject"] = headers.get("subject", "Intro")
    msg["Date"] = headers.get("date", "Tue, 02 Sep 2026 09:15:00 +0300")
    msg["Message-ID"] = headers.get("message_id", "<abc123@mail.example>")
    if "references" in headers:
        msg["References"] = headers["references"]
    if text is not None:
        msg.set_content(text)
    if html is not None:
        if text is None:
            msg.set_content(html, subtype="html")
        else:
            msg.add_alternative(html, subtype="html")
    for filename, ctype, data in attachments:
        maintype, subtype = ctype.split("/")
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return bytes(msg)


def test_parse_headers_and_participants():
    raw = make_email("Hello", cc="Amina <amina@acme.africa>, bob@gmail.com", references="<root@x> <mid@x>")
    e = parse_rfc822(raw)
    assert e.message_id == "<abc123@mail.example>"
    assert e.from_.email == "wanjiru@mpesa-tools.co.ke"
    assert e.from_.name == "Wanjiru Kamau"
    assert [a.email for a in e.cc] == ["amina@acme.africa", "bob@gmail.com"]
    assert e.thread_key == "<root@x>"
    assert e.date.utcoffset().total_seconds() == 3 * 3600
    roles = [r for r, _ in e.participants]
    assert roles == ["from", "to", "cc", "cc"]


def test_missing_message_id_is_stable():
    msg = EmailMessage()
    msg["From"] = "a@b.com"
    msg.set_content("hi")
    raw = bytes(msg)
    assert parse_rfc822(raw).message_id == parse_rfc822(raw).message_id
    assert parse_rfc822(raw).message_id.startswith("<sha256-")


def test_attachments_extracted():
    raw = make_email("See deck", attachments=[("deck.pdf", "application/pdf", b"%PDF-1.4 fake")])
    e = parse_rfc822(raw)
    assert len(e.attachments) == 1
    att = e.attachments[0]
    assert att.filename == "deck.pdf" and att.content_type == "application/pdf"
    assert att.data == b"%PDF-1.4 fake"
    assert len(att.sha256) == 64


def test_gmail_style_quote_removed():
    text = """Thanks Paul, Thursday works.

On Mon, Sep 1, 2026 at 10:02 AM Paul Otieno <paul@savanna.vc> wrote:
> Could we meet this week?
> Paul"""
    assert strip_quoted(text) == "Thanks Paul, Thursday works."


def test_wrapped_reply_header_removed():
    text = """Sounds good.

On Mon, Sep 1, 2026 at 10:02 AM Paul Otieno
<paul@savanna.vc> wrote:

Older text"""
    assert strip_quoted(text) == "Sounds good."


def test_outlook_header_removed():
    text = """Sharing the model now.

From: Paul Otieno <paul@savanna.vc>
Sent: Monday, September 1, 2026 10:02 AM
To: Wanjiru
Subject: RE: Model

Earlier message"""
    assert strip_quoted(text) == "Sharing the model now."


def test_forward_kept():
    text = """Paul - worth a look, see below.

---------- Forwarded message ---------
From: Founder <f@startup.io>
Hi, we're raising a seed round."""
    out = strip_quoted(text)
    assert "raising a seed round" in out


def test_html_gmail_quote_and_outlook_divider():
    html = """<div dir="ltr">New content here<br>Second line</div>
    <div class="gmail_quote"><div>On Mon wrote:</div><blockquote>old stuff</blockquote></div>"""
    full, unquoted = html_to_text(html)
    assert "old stuff" in full
    assert "old stuff" not in unquoted
    assert unquoted == "New content here\nSecond line"

    outlook = (
        """<div>Reply text</div><hr><div id="divRplyFwdMsg"><b>From:</b> x</div><div>quoted body</div>"""
    )
    _, unquoted = html_to_text(outlook)
    assert unquoted == "Reply text"


def test_signature_split_delimiter_and_signoff():
    body, sig = split_signature("Great chatting.\n\n-- \nJane Doe\nCEO, Acme")
    assert body == "Great chatting." and sig == "Jane Doe\nCEO, Acme"

    body, sig = split_signature(
        "Attached is our deck.\n\nBest regards,\nWanjiru Kamau\nCo-founder & CEO | M-Pesa Tools\n+254 712 345 678\n"
        "Sent from my iPhone"
    )
    assert body == "Attached is our deck."
    assert sig.startswith("Best regards,")
    assert "iPhone" not in sig


def test_signoff_before_long_paragraph_is_not_signature():
    text = "Thanks\n" + "This is a long paragraph " * 10
    body, sig = split_signature(text)
    assert sig is None and body == text.rstrip()


def test_parse_signature_fields():
    info = parse_signature(
        "Best,\nWanjiru Kamau\nCo-founder & CEO | M-Pesa Tools\n+254 712 345 678\nlinkedin.com/in/wanjiru\nmpesatools.co.ke",
        "Wanjiru Kamau",
    )
    assert info.name == "Wanjiru Kamau"
    assert info.title == "Co-founder & CEO"
    assert info.company == "M-Pesa Tools"
    assert info.phones == ["+254 712 345 678"]
    assert info.linkedin == "https://linkedin.com/in/wanjiru"
    assert "mpesatools.co.ke" in info.urls


def test_clean_body_end_to_end():
    raw = make_email(
        text="Hi Paul,\n\nHappy to introduce you to Amina.\n\nBest,\nWanjiru\n\nOn Mon, Paul wrote:\n> hi",
        html="<p>Hi Paul,</p><p>Happy to introduce you to Amina.</p><p>Best,<br>Wanjiru</p>"
        "<div class='gmail_quote'>On Mon, Paul wrote: hi</div>",
    )
    full, body, sig = clean_body(parse_rfc822(raw))
    assert body == "Hi Paul,\n\nHappy to introduce you to Amina."
    assert sig == "Best,\nWanjiru"
    assert "On Mon" in full
