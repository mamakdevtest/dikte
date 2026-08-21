# Dikte — ZCode Çalışma Talimatları

Bu dosya ZCode'un workspace talimat dosyasıdır. `promt-v2.md` içindeki Lead
Orchestrator akışının ZCode (GLM-5.3) için uyarlanmış halidir.

## Proje kimliği

Dikte: yerel-öncelikli sesli diktya / transkripsiyon / temizleme aracı.
Python + PyQt6, Windows ve Linux. Günlik gerçek kullanım hedeflidir; doğruluk
ve tekrarlanabilirlik hızlı yamadan önce gelir.

Ana modüller: `dikte.py` (uygulama), `settings_ui.py` (ayarlar), `config.py`,
`cli.py`, `hotkey.py`, `worker.py`, `ggml.py` (yerel sunucular), `overlay.py`,
`i18n.py`. Testler: `tests/` (offscreen Qt mimarisi mevcut).

## ZCode orkestrasyon modeli

ZCode'da sub-agent'lar Agent aracı ile çalışır. İki yerleşik tip:

- `general-purpose` — kod yazan, test çalıştıran, çok adımlı işler;
- `Explore` — salt-okunur, geniş tarama / kanıt toplama.

Baş agent (Lead) Graphify/daraltma işini merkezde yapar, işçilere odaklanmış
bağlam verir. İşçiler başka işçi çalıştıramaz.

### Sub-agent topolojisi (Agent aracı ile çalıştırılır)

| Agent | ZCode tipi | Sahiplik | Görev |
|---|---|---|---|
| Worker A — Save/Apply kök neden | general-purpose | `settings_ui.py`, `config.py`, `dikte.py`, `ggml.py` + testleri | Save çökmesini yeniden üret, kök nedeni bul, save-vs-apply hata sözleşmesini kur |
| Worker B — Startup / performans / ikon | general-purpose | `dikte.py`, `settings_ui.py`, ikon yardımcısı | Otomatik Settings, ilk-boyama gecikmesi, Windows ikon politikası |
| Worker C — Platform stabilite denetimi | Explore | salt-okunur | Süreç yaşam döngüsü, Qt callback'leri, hotkey, platform yolları; kanıtlı kısa rapor |
| Worker D — Taze doğrulayıcı | general-purpose (yazarı DEĞİL) | tüm diff | Bağımsız inceleme, hedefli doğrulama, eksik test raporu |

Kurallar:

- A ve B aynı dosyaya yazacaksa Lead bölüm/alan böler veya yazıları serileştirir.
- İşçi özetleri Context Ledger'daki `AGENTS.md` dosyasına kısa kaydedilir;
  tam transkript ana bağlama taşınmaz.
- Model yetenek probe'u (Claude/ANTHROPIC_* env) ZCode'da geçerli değildir;
  ZCode Agent aracının kendi modeliyle çalışır.

## Context Ledger

Konum: `.zcode/mamak-context/` (`.claude/mamak-context` eski yerdir; eski
içerik okunabilir ama yeni kayıtlar buraya yazılır).

Yapı:

```
.zcode/mamak-context/
  ACTIVE.json                        → aktif görev klasörünü işaret eder
  YYYY-MM-DD/HHmm-görev-adı/
    <tarih-saat>-görev-plan.md
    NOW.md        → yetkili güncel durum, <=150 satır / ~8KB
    DECISIONS.md  → karar defteri
    WORKLOG.md    → zaman sıralı iş günlüğü
    AGENTS.md     → sub-agent handoff özetleri
    EVIDENCE.md   → komut çıktıları / kanıtlar
    COMPACTIONS.md→ sıkıştırma (compaction) özetleri
    HANDOFF.md    → sonraki oturuma devir
```

Kurallar:

- Sır yok, tam sohbet transkripti yok; NOW.md güncel durumla ezilir.
- Ledger ve önbellek dosyaları Graphify indeksine katılmaz.
- Resume sırası: `ACTIVE.json → NOW.md → plan/DECISIONS/HANDOFF`,
  ancak repoyu yeniden keşfetmeden önce.

### Kaydet / kaydetme sözleşmesi

- **Kaydet modu** (`/kaydet`): durum Ledger'a kalıcı yazılır (NOW + WORKLOG +
  gerekirse HANDOFF). Uzun işlemlerden önce, her agent handoff'unda, kök neden
  bulunduğunda, doğrulama sonrası ve oturum kapanmadan önce çalıştırılır.
- **Kaydetme modu** (`/kaydetme`): sadece ekrana özet çıkarır, hiçbir Ledger
  dosyasına yazmaz. Deneme/sohbet amaçlı hızlı durum özetidir.

## Başlangıç kontrol listesi (her görevde)

1. `git status --short`, branch/HEAD, staged/unstaged; kullanıcının önceki
   değişiklikleri korunur, asla reset/stash/discard edilmez.
2. `ACTIVE.json` varsa resume akışı uygulanır.
3. Graphify: `graphify --version`, `graphify-out/graph.json` ve
   `GRAPH_REPORT.md` geniş ham dosya okumalarından ÖNCE kullanılır.
   Canlı kaynak her zaman kazanır: repomix → graf → hedef dosyalar → testler.
4. Bu görev push yetkisi içermez; açık kullanıcı talimatı olmadan push yok.

## Kalite kuralları

- Sırlar (API key, token, Authorization) asla yazdırılmaz/loglanmaz/kaydedilmez.
- Çökme "düzeldi" denmez sadece dışarıya `except Exception` eklendiği için.
- Pahalı başlatma Qt GUI thread'ini bloke etmez; widget erişimi GUI thread'inde kalır.
- Terminal CLI davranışı ve Linux semantiği korunur.
- Doğrulanmamış hiçbir şey için başarı iddiasında bulunulmaz.
- Test komutu: canlı depodaki `.github/workflows/tests.yml` doğrulanır;
  varsayılan aday `python -m unittest discover`.

## Zcode/Graphify tamamlama kapısı

Kaynak değiştikten sonra `graphify update .` çalıştır; grafın taze ve Ledger
dosyalarıyla kirlenmediğini doğrula. Graf tazeliği görev tamamının parçasıdır.
