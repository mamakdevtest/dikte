---
description: Güncel durumu Context Ledger'a kalıcı olarak kaydet
---

# /kaydet - Kalıcı durum kaydı

Sözleşme: `ai/workflows.md` → "Context Ledger contract" (tek doğruluk
kaynağı orası; burada sadece ZCode çağrı adımları var).

1. `.zcode/mamak-context/ACTIVE.json` oku; aktif görev klasörünü belirle.
   Yoksa `YYYY-MM-DD/HHmm-<görev>/` oluştur ve ACTIVE.json'ı güncelle.
2. Eksik sözleşme dosyalarını oluştur: NOW, DECISIONS, WORKLOG, AGENTS,
   EVIDENCE, COMPACTIONS, HANDOFF.
3. NOW.md'yi sözleşmeye göre yeniden yaz (append etme; <=150 satır).
4. WORKLOG'a damgalı kısa giriş; sub-agent handoff'larını AGENTS.md'ye
   3-6 satırlık özet olarak ekle; karar değişikliklerini DECISIONS'a yaz.
5. Görev bitmediyse HANDOFF'ı güncelle; bittiyse kapanış özeti yaz.

Kurallar: sır/token yok, transkript yok, Ledger asla commit edilmez.
Sonunda tek satır doğrulama ver: güncellenen dosyalar + NOW satır sayısı.
