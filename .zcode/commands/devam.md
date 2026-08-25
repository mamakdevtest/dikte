---
description: Kayıtlı görevi Ledger'dan geri yükle ve kaldığı yerden devam et
---

# /devam - Görevi geri yükle (resume)

Sözleşme: `ai/workflows.md` → "Context Ledger contract".

1. `.zcode/mamak-context/ACTIVE.json` → aktif görev klasörü; yoksa en yeni
   görev klasörünü seç ve bunu kullanıcıya belirt.
2. Sırayla oku: NOW.md → plan → DECISIONS.md → HANDOFF.md.
3. `git status --short` çalıştır; Ledger ile canlı ağaç farklarını not et;
   kullanıcının kayıt dışı değişikliklerini koru.
4. Gerekirse graphify-out/ ile okumayı daralt; çelişkide canlı kod kazanır.
5. Kısa resume özeti ver: görev, kalınan adım, açık konular, ilk eylem —
   sonra o eyleme geç.

Resume sonrası ilk kilometre taşında `/kaydet` öner.
