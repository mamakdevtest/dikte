---
description: Güncel durumu Context Ledger'a kalıcı olarak kaydet
---

# /kaydet — Kalıcı durum kaydı

Mevcut görevin durumunu `.zcode/mamak-context/` altındaki Context Ledger'a yaz.

## Adımlar

1. `.zcode/mamak-context/ACTIVE.json` dosyasını oku; aktif görev klasörünü belirle.
   - ACTIVE.json yoksa veya boşsa: kullanıcıdan (veya mevcut sohbetten) görev
     adını türet ve `.zcode/mamak-context/YYYY-MM-DD/HHmm-<görev-adı>/` klasörünü
     oluştur, ACTIVE.json'ı güncelle.
2. Klasörde eksik dosyaları şablonla oluştur:
   `NOW.md`, `DECISIONS.md`, `WORKLOG.md`, `AGENTS.md`, `EVIDENCE.md`,
   `COMPACTIONS.md`, `HANDOFF.md`.
3. **NOW.md**'yi yeniden yaz (append etme): görev, öncelik sırası, güncel durum,
   açık konular, sonraki adım, engeller. Hedef <=150 satır / ~8KB.
4. **WORKLOG.md**'ye tarih-saat damgalı kısa bir giriş ekle (yapılan iş, kanıt yolu).
5. Bu oturumda sub-agent çalıştıysan her biri için **AGENTS.md**'ye 3-6 satırlık
   handoff özeti ekle (agent, sahip olduğu dosyalar, sonuç, kanıt).
6. Verilen kararlarda önemli değişiklik varsa **DECISIONS.md**'ye ekle.
7. Görev devam ediyorsa **HANDOFF.md**'yi güncelle; bitmişse sonlandırma özeti yaz.

## Kurallar

- Sır/anahtar/token asla yazılmaz.
- Tam sohbet transkripti yazılmaz; sadece damıtılmış durum.
- Dosya yazımlarından sonra kullanıcıya tek satır doğrulama ver:
  hangi dosyalar güncellendi ve NOW.md'nin satır sayısı.
