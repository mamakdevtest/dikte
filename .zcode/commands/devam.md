---
description: Kayıtlı görevi Ledger'dan geri yükle ve kaldığı yerden devam et
---

# /devam — Görevi geri yükle (resume)

Context Ledger'dan en son kaydedilen durumu yükle ve kaldığı yerden devam et.

## Adımlar

1. `.zcode/mamak-context/ACTIVE.json` → aktif görev klasörünü bul.
   - Yoksa: `.zcode/mamak-context/` ve eski `.claude/mamak-context/` altında
     en yeni görev klasörünü öner, kullanıcıya hangisi olduğunu doğrulamadan
     varsayılan olarak en yenisini seç ve bunu belirt.
2. Sırayla oku: `NOW.md` → plan dosyası → `DECISIONS.md` → `HANDOFF.md`.
3. `git status --short` çalıştır; Ledger'daki durum ile canlı ağaç arasındaki
   farkları not et. Kullanıcının Ledger'da kayıtlı olmayan değişikliklerini koru.
4. Gerekirse Graphify verisini (`graphify-out/`) kullanarak ilgili dosyaları
   daralt, ardından canlı dosyaları oku. Canlı kaynak kazanır.
5. Kullanıcıya kısa bir resume özeti ver: görev, kalınan adım, açık konular,
   önerilen ilk eylem. Sonra o ilk eyleme geç.

## Kurallar

- Repo, Ledger'dan daha yetkilidir; çelişkide canlı kod kazanır.
- Sır içerikli dosyaları okuma/ezme.
- Resume sonrası ilk anlamlı kilometre taşında `/kaydet` öner.
