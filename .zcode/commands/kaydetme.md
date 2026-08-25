---
description: Durum özeti çıkar ama Ledger'a hiçbir şey yazma
---

# /kaydetme - Özet modu (kalıcı kayıt YOK)

Bu komut Context Ledger'a **hiçbir dosya yazmaz** (sözleşme:
`ai/workflows.md` → "Context Ledger contract"; kalıcı mod için `/kaydet`).

1. `.zcode/mamak-context/ACTIVE.json` ve varsa NOW.md'yi salt okunur oku
   (yoksa sohbetten derle).
2. Kısa markdown özet sun (~30 satır üst sınır):
   - **Görev** - aktif görev ve öncelik sırası
   - **Durum** - tamamlananlar / devam edenler
   - **Açık konular** - engeller, doğrulanmamış iddialar
   - **Sonraki adım** - tek en önemli adım
   - **Kalıcı kayıt** - `Yapılmadı (kaydetme modu)`
3. Hiçbir Ledger dosyası oluşturma/değiştirme.
