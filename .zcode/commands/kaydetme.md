---
description: Durum özeti çıkar ama Ledger'a hiçbir şey yazma
---

# /kaydetme — Özet modu (kalıcı kayıt YOK)

Bu komut Context Ledger'a **hiçbir dosya yazmaz**. Sadece ekrana, sohbetin
geçerli durumunun özetini çıkarır. Deneme, hızlı kontrol veya "nerede kalmıştım"
sorusu içindir.

## Adımlar

1. `.zcode/mamak-context/ACTIVE.json` ve varsa aktif `NOW.md`'yi **salt okunur**
   oku (yoksa sohbet içinden derle).
2. Kullanıcıya şu başlıklarla kısa bir özet sun (markdown):
   - **Görev** — aktif görev ve öncelik sırası
   - **Durum** — tamamlananlar / devam edenler
   - **Açık konular** — engeller, doğrulanmamış iddialar
   - **Sonraki adım** — tek en önemli adım
   - **Kalıcı kayıt** — `Yapılmadı (kaydetme modu)`. Kalıcı istenirse `/kaydet`
3. Hiçbir Ledger dosyası oluşturma, değiştirme veya güncelleme.
4. Özet uzun olmasın: en fazla ~30 satır.
