"""#FT-ZOMBIE-DISMISS-REACTIVATION (Raiz 1, Rui 10 Jul) — regra ÚNICA: um dispensado só
reacorda com sinal POSTERIOR à dispensa. O print Info PRÉ-EXISTENTE (o que motivou a
dispensa) já não reacorda; a tag -ft manual (override) sim."""
import datetime as dt
import app.services.ft_boundary as F

_UTC = dt.timezone.utc
_DISMISSED_AT = dt.datetime(2026, 7, 10, 0, 13, tzinfo=_UTC)


def test_manual_ft_always_reactivates(monkeypatch):
    monkeypatch.setattr(F, "_manual_ft_boundary", lambda tn: dt.datetime(2026, 7, 2, tzinfo=_UTC))
    monkeypatch.setattr(F, "_lobby_ft_boundary", lambda tn: (None, None))
    assert F.has_new_ft_signal("x", _DISMISSED_AT) is True
    assert F.has_new_ft_signal("x", None) is True          # -ft trumps mesmo sem decided_at


def test_preexisting_info_does_not_reactivate(monkeypatch):   # ★ o zombie
    monkeypatch.setattr(F, "_manual_ft_boundary", lambda tn: None)
    monkeypatch.setattr(F, "_lobby_ft_boundary",
                        lambda tn: (dt.datetime(2026, 7, 2, 19, 19, tzinfo=_UTC), 7))
    assert F.has_new_ft_signal("x", _DISMISSED_AT) is False   # Info 07-02 19:19 < dispensa 07-10


def test_posterior_info_reactivates(monkeypatch):
    monkeypatch.setattr(F, "_manual_ft_boundary", lambda tn: None)
    monkeypatch.setattr(F, "_lobby_ft_boundary",
                        lambda tn: (dt.datetime(2026, 7, 10, 1, 0, tzinfo=_UTC), 7))
    assert F.has_new_ft_signal("x", _DISMISSED_AT) is True    # Info DEPOIS da dispensa


def test_no_signal_no_reactivation(monkeypatch):
    monkeypatch.setattr(F, "_manual_ft_boundary", lambda tn: None)
    monkeypatch.setattr(F, "_lobby_ft_boundary", lambda tn: (None, None))
    assert F.has_new_ft_signal("x", _DISMISSED_AT) is False


def test_info_without_decided_at_is_conservative(monkeypatch):
    monkeypatch.setattr(F, "_manual_ft_boundary", lambda tn: None)
    monkeypatch.setattr(F, "_lobby_ft_boundary",
                        lambda tn: (dt.datetime(2026, 7, 2, tzinfo=_UTC), 7))
    assert F.has_new_ft_signal("x", None) is False            # sem decided_at → Info não reacorda
