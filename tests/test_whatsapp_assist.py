from app.config import settings
from app.course_detect import detectar_curso
from app.schemas.whatsapp_assist import WhatsAppMessage, format_whatsapp_reply
from app.tuning_store import invalidate_tuning_cache
from app.whatsapp_assist import gather_catalog_context


def test_format_whatsapp_reply_strips_emoji():
    raw = "Tudo certo! Vamos la? \U0001f44d"
    assert format_whatsapp_reply(raw) == "Tudo certo! Vamos la?"


def test_format_whatsapp_reply_single_line():
    raw = "Ola!\nTudo bem?\nPosso ajudar sim."
    assert format_whatsapp_reply(raw) == "Ola! Tudo bem? Posso ajudar sim."


def test_format_whatsapp_reply_keeps_list():
    raw = "Opcoes:\n- A\n- B"
    assert format_whatsapp_reply(raw) == raw


def test_detect_curso_no_superior():
    invalidate_tuning_cache()
    d = detectar_curso("Quais materias tem no superior no primeiro semestre?")
    assert d["sugestao"] == "sistemas"


def test_gather_catalog_skips_trabalhos_sem_ppc():
    invalidate_tuning_cache()
    q = (
        "Joao e Filipe ainda nao apresentaram os trabalhos. "
        "Isso afeta a nota desta semana?"
    )
    msgs = [WhatsAppMessage(author="Maria", text=q, outgoing=False)]
    ctx, expected = gather_catalog_context(msgs)
    assert ctx == ""
    assert expected is None


def test_gather_catalog_primeiro_semestre_superior():
    invalidate_tuning_cache()
    path = settings.data_dir / "knowledge" / "ppc-sistemas.md"
    if not path.is_file():
        return
    q = "Quais materias tem no superior no primeiro semestre?"
    msgs = [WhatsAppMessage(author="Maria", text=q, outgoing=False)]
    ctx, expected = gather_catalog_context(msgs)
    assert expected == 4
    assert "ATP" in ctx
    assert "ING" in ctx
    assert "1" in ctx or "Fase" in ctx
