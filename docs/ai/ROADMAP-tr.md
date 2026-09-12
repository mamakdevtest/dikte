# Dikte — Modernizasyon Yol Haritası

> Durum: **öneri, henüz uygulanmadı.** Bu belgedeki hiçbir şey kodlanmadı.
> Aşağıdaki bulguların tamamı 2026-09-12'de `master @ ffe8a5c` üzerinde
> salt-okunur bir incelemeden çıktı (Linux, KDE/Wayland, Python 3.14.7).
> Canlı kaynak her zaman bu dosyadan üstündür.
>
> İngilizce aslı: [`ROADMAP.md`](ROADMAP.md)

## 0. Nasıl okunmalı

- **§1–§2** bulgular: gerçekte ne bozuk ve bunu hangi komut ya da dosya kanıtlıyor.
  Hiçbiri bir tasarım dokümanından çıkarım yapılarak yazılmadı.
- **§3** teknoloji sorusunu cevaplıyor (Python mu, C++ mı, başka bir şey mi).
- **§4** "arayüz düzgün görünmüyor" şikâyetinin tek kök nedenini açıklıyor.
- **§5** fazlı plan. Her fazın görevleri, dosyaları, doğrulaması ve bitti-kabul
  kriteri var. Sıralama cazibeye göre değil, **bağımlılığa** göre.
- **§7** yalnızca ürün sahibinin verebileceği kararlar. Faz 2'yi bloke ediyorlar.

## 1. Doğrulanmış başlangıç durumu

Çalıştırılan komutlar ve gerçek sonuçları:

| Kontrol | Komut | Sonuç |
|---|---|---|
| Test takımı | `python3.14 -m unittest discover` | **1473 test, 102,7 sn — OK** (0 hata, 0 başarısızlık) |
| CLI duman testi | `python3.14 dikte.py --help` | çıkış 0, 25 komut listelendi |
| Çalışma sağlığı | `python3.14 dikte.py doctor` | tüm araçlar bulundu (`pw-record`, `wl-copy`, `ydotool`, `ffmpeg`, `pactl`, `kwriteconfig6`, `claude`, `codex`); Deepgram anahtarı var; codex temizliği yapılandırılmış; uygulama çalışıyor |
| Arayüz görüntüsü | `python3.14 tools/shoot_ui.py --out /tmp/dikte-shots --themes blue --langs tr,en` | **60 PNG yazıldı** — 11 sayfa × 2 dil + overlay/result/live/thinking/dialog durumları |
| Grafik tazeliği | `graphify-out/GRAPH_REPORT.md` | `e240740`'dan üretilmiş; **HEAD `ffe8a5c` → bayat** |
| Kod boyutu | `wc -l` | Kök modüllerde 22.792 satır + `ui/` altında 6.383 satır ≈ **29k satır**. Monolitler: `settings_ui.py` 3.239 · `overlay.py` 2.086 · `dikte.py` 2.053 · `config.py` 1.786 |
| Sessiz hata yüzeyi | `grep -c 'except Exception'` (testler hariç) | **313 yer** |

Takım yeşil. **Asıl bulgu bu**: §2'deki her kusur, tamamen yeşil bir 1.473
testlik takımın içinden geçiyor. Yani takım, kuralların varsaydığı güvenlik ağı
değil.

## 2. Bulgu kaydı

Önem: **S1** günlük kullanımı engeller · **S2** görünür bozulma · **S3** cila.

### 2.1 İşlevsellik ve güvenilirlik (F)

| # | Önem | Bulgu | Kanıt |
|---|---|---|---|
| F1 | S1 | **Açık olan güvenilirlik turu bitmemiş.** R1 (dinamik aktivite kaydı), R2 (bağımsız toplantı/dikte/ajan/sonuç overlay görünümleri), R3 (güvenli eşzamanlı yakalama politikası), R4 (sınıflandırmadan önce sesi kaydetme), R6 (kurtarma arayüzü), R7 (düzenleme seviyesi eşitliği), R8 (regresyon kapsamı) ve V4 doğrulaması işaretsiz. Görev dosyası sebebini de yazıyor: *"the prior static coordinator and shared meeting/dictation overlay do not provide independent simultaneous activities."* | `docs/ai/TASKS.md:13-21` |
| F2 | S1 | **313 `except Exception` yeri.** AGENTS.md 3. ve 4. kuralı "kanıt olmadan başarı iddia etme" ve "kaydedildi ama uygulanamadı ayrı durumlardır" diyor. Bu yoğunlukta bu kural incelemeyle uygulanabilir değil; başarısız bir model indirmesinin, başarısız bir yapıştırmanın ya da başarısız bir kaydetmenin göstergede normal görünmesinin mekanizması bu. | `grep -rn 'except Exception' --include=*.py` |
| F3 | S2 | **Kaydedilmiş ama kapatılmamış üç boşluk**: `OverlayCoordinator.update` her `show_*`/`dismiss` sonrası tetiklenmiyor (ara sıra konum kayması); `Config.data` üzerinde kısmen kilitlenmiş süreç-içi okuma yarışı; süreçler arası dosya kilidi yok. | `docs/ai/VERIFICATION.md` "Gaps / notes" |
| F4 | S2 | **Paketleme üst verisi hem kendisiyle hem ürünle çelişiyor.** `pyproject.toml` `license = { text = "MIT" }` diyor, `README.md` ve `LICENSE` ise GPL-3.0 — üstelik PyQt6 GPL-3.0 ya da ticari lisanslı olduğu için MIT iddiası yazım hatası değil, lisans çatışması. `requires-python = ">=3.11,<3.14"` 3.14'ü dışlıyor; oysa takımın tamamı yerelde 3.14'te geçiyor. | `pyproject.toml:11,10` |

### 2.2 Yerelleştirme (L)

| # | Önem | Bulgu | Kanıt |
|---|---|---|---|
| L1 | S1 | **104 farklı kullanıcı-metni `t()` ile çevrilmek isteniyor ama Türkçe karşılığı yok**, dolayısıyla Türkçe arayüzde İngilizce görünüyor. Ölçüm: `tools/i18n_gaps.py`, ürün kodundaki her `t()`/`_t()` sabitini geziyor. En kötüleri: `ui/local_models.py` (26), `ui/pages/general.py` (15), `ui/pages/meeting.py` (8), `ui/pages/providers.py` (6), `ui/pages/agent.py` (6). | `python tools/i18n_gaps.py` |
| L2 | S1 | `"Overlay/Indicator"` **koda gömülü İngilizce bir sabit**; hem menü etiketi hem sayfa başlığı olarak kullanılıyor. | `settings_ui.py:507`, `ui/pages/overlay.py:59` |
| L3 | S2 | Kenar çubuğu alt bilgisi `"Local"` ve `"Ready"` metinlerini gömülü tutuyor. Tabloda yalnızca `"Ready: {model}"` var. | `i18n.t("Ready") == "Ready"`, `i18n.t("Local") == "Local"` |
| L4 | S2 | Çevrilmemiş metinler arasında **çalışma durumları ve yıkıcı onaylar** var: `Checking…`, `Downloading…`, `Download stopped.`, `Fetching the model list…`, `Delete model`, `Delete {name} from this machine?`. Bunlar tam olarak kullanıcının veri kaybetmeden önce anlaması gereken metinler. | ölçüm çıktısı |
| L5 | S2 | **Mevcut Türkçe karşılıklar kötü ya da tutarsız.** `"Runs on" → "Şunun üstünde çalışır"` form etiketi olarak kullanılan bir cümle parçası. `"Prompts" → "Promptlar"` iken ekran görüntülerinde `Promtlar`/`Promptlar` karışık. `"Local"` çipi çevrilmemiş, hemen yanında `"Local dictation" → "Yerel dikte"` var. | `i18n.py:531,993,897` |
| L6 | S1 | **i18n korkuluğu küme değil sayaçtı.** `test_user_visible_strings_reach_t` 102 ölçen bir tarama üzerinde `len(missing) <= 104` doğruluyordu — iki birim gevşeklik, yeni bir boşluğu eskisinden ayırmanın imkânı yok (bir çevrilmemiş metni başkasıyla değiştirmek sayıyı korur), boşluk kapandığında sıkma yok ve `_t` takma adı kapsam dışı — her sayfanın kenar çubuğunda görünen `Local` ve `Ready` tam da bu yüzden görünmez kaldı. Faz 0'da tam-küme kaydıyla değiştirildi. | `tests/test_i18n.py`, `tests/i18n_untranslated.json` |
| L7 | S3 | Yerel sayı/tarih biçimlendirmesi yok: süreler Türkçede `3.2s` / `2.0 sn` (nokta ondalık) çıkıyor, geçmiş satırları ISO `2026-08-21 12:05:00` gösteriyor. | `blue_tr_page00.png`, `blue_tr_page09.png` |

### 2.3 Arayüz ve görsel (U)

Aşağıdaki bulgular alınan 60 kareden, yüzey yüzey incelenerek çıkarıldı.

| # | Önem | Bulgu | Kanıt |
|---|---|---|---|
| U1 | S1 | **İki ölü ikon anahtarı kenar çubuğunu bozuyor.** `shell.NAV` `"history"` istiyor, `settings_ui.py:507` `"pip"` istiyor; ikisi de `ui/icons.py` içinde yok (56 ikon). On bir menü öğesinden ikisi ikonsuz kalıyor ve ikon sütunu bozuluyor. | ikon ölçümü: `'history' present: False`, `'pip' present: False` |
| U2 | S1 | **Birincil/ikincil buton hiyerarşisi yok.** `Kaydet` ile `Promptlar` her sayfada aynı alt şeritte, aynı ağırlıkta; sayfanın değiştirdiği her şeyi kalıcı kılan eylem olan Kaydet ne baskın ne de platformun beklediği yerde. | tüm `blue_tr_page*.png` |
| U3 | S2 | **Kontrast ve durum okunabilirliği.** Soluk metin katmanı ve tüm pasif kontroller 11 sayfanın 8'inde fazla silik; pasif ve etkin butonlar zor ayırt ediliyor. | overlay, geçmiş, tutanak, ses dosyası, kontrol paneli |
| U4 | S2 | **Aşırı büyük, yanlış ortalanmış boş durumlar.** Geçmiş'teki "kurtarılabilir" kartı kocaman boş bir kutu; kontrol panelindeki boş grafik kartı tam kart yüksekliğinde; Overlay sayfası boş durumunu hiç ortalamıyor. | `blue_tr_page09/00/10.png` |
| U5 | S2 | **Form sütunu hizası kayıyor.** Bir kart içindeki kontroller tek bir sol/sağ kenarı paylaşmıyor; kısayol satırı (kombo + Kur/Kaldır + alt satırdaki bağlantılar) etiket sütununa taşıyor. | `blue_tr_page04.png` |
| U6 | S2 | **`LivePopup` içeriğine göre boyutlanmıyor** — sabit ~500×520 panel, üç satır metinle birlikte üçte ikisi ölü alan; boş durumu da yok. | `blue_tr_live_expanded.png` |
| U7 | S3 | `Local` çipi tıklanabilir gibi duruyor ama değil; `1.0` sürüm etiketi etiketsiz. | her karede kenar çubuğu |
| U8 | S2 | **Bağlı içerik, ana anahtar kapalıyken devre dışı kalmıyor.** "Özel prompt" kapalı, ama altındaki tüm temizleme prompt bölümü düzenlenebilir kalıyor. | `blue_tr_page03.png` |
| U9 | S2 | 5 seçenekli "Düzenleme seviyesi" segment kontrolü sıkışık, tıklama hedefleri rahat boyutun altında. | `blue_tr_page03.png` |
| U10 | S2 | **Kayıt pili**: ortadaki simge etiketsiz ve düşük kontrastlı, `0:03` zamanlayıcısı "kayıt" bağlamı taşımıyor, Duraklat/Durdur birbirine çok yakın, sürükleme tutamacı yok. | `blue_tr_overlay_rec.png` |
| U11 | S2 | Meşgul pili ile "düşünüyor" paneli aynı üründen gelmiyor gibi — köşe yarıçapları, punto boyutları farklı; ikincil panelde metin "Cleaning up…" derken hiç etkinlik göstergesi yok. | `blue_tr_overlay_busy.png` |
| U12 | S3 | Tepsi menüsünde ikon, grup ayırıcı ve aç/kapat tipi öğeler için durum göstergesi yok. | `blue_tr_hintmenu.png` |

### 2.4 Platformlar arası ve dağıtım (X)

| # | Önem | Bulgu | Kanıt |
|---|---|---|---|
| X1 | S1 | **Hiçbir platform için dağıtılabilir bir yapı yok.** Kurulum, kaynak kopyası + geliştirici Python'u gerektiriyor: `install.sh` kısayol yazıyor ve `dikte`'nin `PATH`'te olmasını bekliyor; `install.ps1` Başlat menüsü girdisi ekliyor ama yine `pythonw dikte.py` çalıştırıyor. `.exe`, `.dmg`/`.app`, AppImage veya Flatpak yok. Günlük kullanılan bir araç için bu, benimsemedeki en büyük engel. | `install.sh`, `install.ps1`, paketleme yapılandırması yok |
| X2 | S1 | **Linux tarafındaki overlay XWayland'e bağımlı.** `dikte.py:41` göstergeyi ekran köşesine yerleştirebilmek için `QT_QPA_PLATFORM=xcb` ayarlıyor. Yalnızca Wayland çalışan, XWayland'siz bir oturumda gösterge hiç görünemez; kesirli ölçekleme de bu yolda güvenilir değil. | `dikte.py:41`, `README.md:236` |
| X3 | S1 | **Kısayol etiketleri platformdan bağımsız, yardım metinleri ise ters yönde platforma özel.** Arayüz her platformda `Meta+A` / `Meta+M` öneriyor; yardım metinleri ise KDE (`KDE kısayolu olarak kur`) veya macOS ifadelerini gömüyor. Windows `Win`, macOS `Cmd`/`⌘` ister; KDE metni Windows'ta anlamsız. | `ui/pages/agent.py`, `ui/pages/shortcuts.py`, `i18n.py:386` |
| X4 | S2 | **Hiçbir işletim sisteminde donmuş bir yapı derlenmiyor veya başlatılmıyor.** CI test takımını Linux, Windows **ve macOS** üzerinde çalıştırıyor (3.11–3.13; 3.14 Faz 0'da eklendi), yani macOS kod yolları gerçekten koşuyor — hiçbir işin yapmadığı şey dağıtılabilir bir yapı üretmek veya başlatmak; X1'in açık kalmasının sebebi bu. | `.github/workflows/tests.yml` |
| X5 | S2 | Takımın Windows'a özel kod yolu daha önce Linux'ta çalıştırılıyordu (`ctypes.windll`); şu an CI'da gerçekten koşturmak yerine mock'lanıyor. | `docs/ai/VERIFICATION.md` |

### 2.5 Mühendislik hijyeni (H)

| # | Önem | Bulgu | Kanıt |
|---|---|---|---|
| H1 | S2 | graphify grafiği bayat. AGENTS.md tazeliği bitiş kriteri sayıyor. | §1 |
| H2 | S3 | Ağaçta hiç `TODO`/`FIXME` yok — iyi disiplin, ama bilinen sorunlar yalnızca düz metin dokümanlarda yaşıyor ve yeni bir katkıcı onları bulamaz. | `grep -rn 'TODO\|FIXME'` → 0 |
| H3 | S3 | `settings_ui.py` (3.239 satır) ve `overlay.py` (2.086 satır) her değişikliğin yan etki riski taşıdığı boyutta. | `wc -l` |
| H4 | S2 | **Yutulan hataların üçte biri tek dosyada.** `settings_ui.py` **313 yerin 102'sini** barındırıyor; `dikte.py` 41. "Dürüst hata arayüzü" kuralının (§F2) en uygulanamaz olduğu yer bu iki monolit, üstelik her arayüz değişikliğinin dokunmak zorunda olduğu iki dosya da bunlar. | `python tools/except_audit.py` |
| H5 | S2 | **Kontrol paneli sayfası kabuğun kendi sayfa API'sini atlıyor.** `DashboardWindow.__init__` sekmesini doğrudan `QTabWidget`'e ekliyor, sonra menü düğmesini elle kurup `shell._nav_layout`, `shell._nav` ve `shell._nav_titles` özel alanlarına uzanıyor ve var olan tüm düğmelerin `clicked` sinyalini yeniden bağlıyor. `AppShell.add_page()`'i çağırmak yerine onu kopyalıyor; sayfa sayısının yalnızca `add_page` çağrılarından türetilememesinin ve ikon sözleşmesinin (T0.4) onu kapsamamasının sebebi bu. | `ui/app_window.py:23-53` |

## 3. Teknoloji kararı

### 3.1 Verdict: Python 3.11+ / PyQt6'da kalınmalı

Kolay olduğu için değil, **§2'deki sorunların hiçbiri dilde yaşamadığı için.**

- Başarım açısından kritik her adım zaten Python'un dışında çalışıyor: ses
  yakalama (`pw-record` / `ffmpeg` / WinMM / AVFoundation), VAD matematikleri,
  çıkarım (`whisper.cpp`, `llama.cpp`) ve dosya g/ç. Python süreçleri yönetiyor
  ve bir ayarlar penceresi çiziyor. Orkestratörü yeniden yazmak milisaniye
  kazandırır.
- Gerçekten zor olan platforma özel işler — global kısayollar (evdev /
  `RegisterHotKey` / Carbon), sentetik yapıştırma (`ydotool` / `SendInput` /
  CoreGraphics), cihaz numaralandırma (`pactl` / WASAPI / AVFoundation) — zaten
  ctypes ve platform API'leriyle native olarak yazılmış. **Yeniden yazımın en
  pahalıya mal olacağı, en az kazanç getirecek kısmı tam olarak burası.**
- Yok olacak varlıklar: 29k satır kod, 1.473 yeşil test, belgelenmiş bir tasarım
  sözleşmesi ve çalışan bir `install.sh`/`install.ps1` ikilisi. Yeniden yazım
  dördünü de sıfırlar ve kullanıcıya hiçbir fayda sağlamadan geri kazanmaya
  çalışır.
- PyQt6 zaten native araç setini getiriyor. Akıcı animasyon gerekirse Qt
  Quick/QML PyQt6'nın içinde geliyor — bu bir dil değişikliği değil, çizim
  yolu değişikliği.

**Dürüst istisna:** ürünün <100 MB kurulum dosyası ya da <100 ms soğuk açılış
gibi *katı* bir gereksinimi varsa derlenmiş bir kabuk savunulabilir. Depoda böyle
bir gereksinim yazılı değil ve X1 (hiç yapı yok) Python içinde çözülebilecek bir
paketleme sorunu.

### 3.2 Neden C++/Qt değil

Pariteye 6–12 ayda ulaşır ve tüm platform katmanını sıfırdan türetmek zorunda
kalır. §2.1, §2.2 ve §2.3'teki — kullanıcının gerçekten hissettiği — hiçbir
bulguyu çözmez.

### 3.3 Diğer yığınlar ve burada neden kaybediyorlar

| Seçenek | Karar |
|---|---|
| **Rust + Tauri** | Webview ekler; `docs/ai/GOAL.md` bunu açıkça kapsam dışı sayıyor ("Embedding HTML/webview/Electron/QtWebEngine to fake fidelity"). Tek dilli projeyi Python arka uç + Rust kabuk + web ön uç üçlüsüne çevirir; her işletim sisteminin kısayol/yapıştırma/ses entegrasyonu yine Rust ile baştan yazılmalı. |
| **Electron** | Ürün kimliğiyle çelişir (yerel-öncelikli, hesapsız, küçük araç), 150 MB+ taban, daha kötü soğuk açılış. |
| **Rust + egui / Slint** | *Yeni* bir uygulama için makul. Bunun için, C++/Qt sorununun daha küçük ekosistemli hâli. |
| **PyQt6 içinde Qt Quick / QML** | Masada tutulmaya değer tek çizim seviyesi değişikliği. §2.3 için gerekli değil — onlar tasarım kararları, çizim sınırı değil. Yalnızca Faz 3'te gerçek bir QPainter tavanına çarpılırsa düşünülmeli. |

### 3.4 Yığın içinde yapılmaya değer yükseltmeler

Canlı depo verisiyle (GitHub API / PyPI, 2026-09-12'de alındı):

| Bileşen | Şimdi | Değerlendirme |
|---|---|---|
| `whisper.cpp` | kullanılıyor | ★53.6k, son push **2026-09-11**, MIT, CUDA/ROCm/Vulkan ile GPU. **Kalsın.** |
| `llama.cpp` | kullanılıyor | ★128k, son push 2026-09-12, MIT. **Kalsın.** |
| **`sherpa-onnx`** | kullanılmıyor | ★14.7k, son push **2026-09-11**, Apache-2.0, **1.13.8 sürümü 2026-09-10**, platform başına hazır ikili dosyalar, yalnızca ONNX. **İkinci yerel motor adayı**: akışlı Zipformer transducer modelleri torch bağımlılığı olmadan gerçek ara sonuçlar verebilir. Ekleyici, ikame değil. |
| `faster-whisper` | kullanılmıyor | ★25.4k ama son push **2025-11-19** (~10 aydır durgun) ve CTranslate2 + cuDNN çekiyor. Popüler cevap olmasına rağmen **alınmasın**. |
| `whisperX` | kullanılmıyor | Etkin, ama torch + pyannote gerektiriyor — uygulamanın zaten ses kanalından türettiği konuşmacı etiketleri için ağır bir bağımlılık ağacı. **Red.** |
| VAD | elle yazılmış dB kapısı | Çalışıyor, bağımlılıksız ve mevcut `silence_db` / `margin` arayüzü bunun üstüne kurulu. `silero-vad` (MIT, etkin) var ama ölçülmemiş bir kazanç için yeni bir çalışma zamanı bağımlılığı demek. **Önce ölç; körlemesine yeniden yazma.** |
| Paketleme | yok | Uygulama için `pyinstaller` 6.22.2 (etkin, bootloader istisnası); `nuitka` 4.2.1 etkin ama AGPL araç ve derlemeleri çok uzun. **PyInstaller.** |

### 3.5 PyQt6 vs PySide6 — varsayım değil, karar

| | PyQt6 | PySide6 |
|---|---|---|
| Son sürüm | 6.11.0 (2026-03-30) | 6.11.2 (2026-08-18) |
| Lisans | GPL-3.0 **ya da ticari** | LGPL-3.0 / GPL-2.0 / GPL-3.0 |
| Sonuç | İkili dosya dağıtmak tüm uygulamayı GPL-3.0 yapmaya zorlar | İkili dağıtım, kendi kodunuz için copyleft yükümlülüğü doğurmaz |

Proje bugün GPL-3.0 beyan ediyor, dolayısıyla **PyQt6 yasal ve teknik olarak
geçme sebebi yok** — API neredeyse aynı, geçiş çoğunlukla içe aktarma adı
değişikliği (`pyqtSignal`→`Signal`, `pyqtSlot`→`Slot`). Ama `pyproject.toml` MIT
diyor ve bu PyQt6 ile bağdaşmıyor. **Birini seçin:** ya üst veriyi GPL-3.0 olarak
düzeltip kalın, ya PySide6'ya geçip GPL dışı bir yapı seçeneğini elinizde tutun.
Bu, §7'deki **Q1** sorusu.

## 4. Görsel yön sorunu — "arayüz düzgün görünmüyor" şikâyetinin kök nedeni

Tek bir tasarım yok; üç tane var ve üçü de hâlâ depoda:

1. **`docs/design-reference.md` (2026-08-21)** — "Sıcak Teknik Minimalizm":
   sıcak taş `#F4F1EA` zemin, kum `#EEE9DE` kenar çubuğu, fildişi `#FBFAF6`
   yüzeyler, mürekkep `#242628` metin, *tek* vurgu olarak terrakota `#E4573D`.
   Açık negatifler: mor yok, neon yok, cam yok, büyük köşe yarıçapı yok.
   **Uygulanmamış.**
2. **`docs/settings-*.webp`, hâlâ README'de gömülü** — başlık çubuğu olan düz
   koyu bir pencere, mavi alt çizgili **dokuz yatay sekme**, onay kutusu formu,
   sağ altta mavi Kaydet butonu, **kenar çubuğu yok**. Bu *önceki bir arayüz
   nesli*. Mevcut yapıda 226 px kenar çubuğu ve on bir sayfa var.
   **README artık var olmayan bir ürünü tanıtıyor.**
3. **`ui/tokens.py`, gerçekte dağıtılan** — altı *yalnızca koyu* renk odası
   (`blue`, `green`, `violet`, `orange`, `pink`, `teal`), her biri doygun bir
   vurguyla karıştırılmış kömür tabanlı, artı erişilemeyen gerçek bir `LIGHT`
   paleti.

Son madde tercih değil, somut bir hata:

```
normalize('light') -> 'blue'
```

Altı ismin dışındaki her tema adı `blue`'ya zorlanıyor; yani `ui_theme: "light"`
sessizce koyu bir odaya dönüşüyor ve `LIGHT` token sözlüğü
(`ui/tokens.py:74-98`) yalnızca alias olarak yaşayan ölü kod hâline geliyor.
**Artık erişilebilir bir açık tema yok ve belgelenen tasarım brifi dağıtılan
tasarım değil.**

Plandaki sonucu: **§7/Q2 cevaplanmadan §2.3'ü düzeltmek dördüncü bir nesil
üretir.** Önce yön kilitlenmeli.

## 5. Fazlı yol haritası

Süreler tek bir odaklı mühendis için geliştirici-günü cinsindendir ve
doğrulanamayan macOS/Windows turlarını içermez.

### Faz 0 — Korkuluklar — **UYGULANDI 2026-09-12**

Bu fazın amacı, sonraki beş fazın sessizce gerilememesi. Hiçbiri kullanıcıya
görünmüyor. Her satırın kanıtı §9'da.

| Görev | Teslim edilen | Nasıl çalıştığı gösterildi |
|---|---|---|
| T0.1 | Lisans çelişkisi **belgelendi, çözülmedi** — Q1 hâlâ açık. `pyproject.toml` içindeki bir yorum çelişkiyi yazıyor ve Q1'e işaret ediyor. | `pyproject.toml:10-15` |
| T0.2 | `requires-python` `>=3.11,<3.15` oldu; üç CI matrisine de `"3.14"` eklendi. Eski sınır, takımın zaten geçtiği bir yapılandırmayı dışlıyordu; yani kodu değil paketleme politikasını anlatıyordu. | 1477 test 3.14.7'de yerelde geçiyor; Windows/macOS 3.14 doğrulanmadı diye açıkça işaretlendi |
| T0.3 | Sayaç korkuluğu **tam-küme kaydıyla** değiştirildi — `tests/i18n_untranslated.json`, çağrı yerleriyle birlikte 104 kayıt — üretici olarak da `tools/i18n_gaps.py`. Tarama artık `_t` takma adını da izliyor. İki yön de kırmızı oluyor. | iki kez kırmızı kanıtlandı: `Ask` düşürülünce → `['Ask']`; `Nobody translated this` uydurulunca → `['Nobody translated this']` |
| T0.4 | Yeni `tests/test_icon_contracts.py`, ve bulduğu iki ölü anahtar düzeltildi: `settings_ui.py:507` artık `monitor` istiyor, `ui/icons.py` bir `history` glifi kazandı. | önce kırmızı kanıtlandı, iki kusuru da adıyla: `settings_ui.py:503 add_page('history')`, `settings_ui.py:507 add_page('pip')`, `ui.shell.NAV → ['history']` |
| T0.5 | `tools/shoot_ui.py` bir yüzey manifestosu, kaynaktan türeyen sayfa-sayısı çapraz kontrolü ve `--check` kazandı; hatırlanmaya gerek kalmadan koşması için Linux CI işine bağlandı. | iki dal da kırmızı kanıtlandı: `missing: blue_en_overlay_somehow_missing.png` ve `blank: blue_tr_overlay_rec.png`; yeşil koşu `30 surfaces x 2 theme-and-language runs, all drawn` diyor |
| T0.6 | Yeni `tools/except_audit.py`. | ilk sayım: **36 modülde 313 yer**, bunların 102'si `settings_ui.py`'de → bulgu H4 |
| T0.7 | Grafik tazelendi. | `5372 nodes, 9509 edges, 311 communities`; `Built from commit: ffe8a5c7` (= HEAD) |
| — | Faz sonrası tam takım | `Ran 1477 tests in 101.1s — OK` (önce 1473). `git diff --check` temiz. |

**Doğrulama sözleşmesine uyuldu:** her korkuluk, düzeltmeden *önce* kırmızı olması
gereken ağaca karşı çalıştırıldı ve hata çıktısı yukarıya birebir yazıldı. Hiç
kırmızı olmamış bir korkuluk, bir şeyi test ettiğinin kanıtı değildir.

**Bunu yaparken ortaya çıkan iki bulgu**, taramada öngörülmeyen: H4 (yutulan
hataların üçte biri tek dosyada) ve H5 (kontrol paneli sayfası
`AppShell.add_page()`'i tamamen atlıyor; sayfa sayısının tek bir çağrı biçiminden
değil iki tanesinden türetilmek zorunda kalmasının sebebi bu).

### Faz 1 — Yerelleştirmeyi kapatma (2–3 g)

| Görev | Ne | Dosyalar |
|---|---|---|
| T1.1 | 103 metnin tamamını çevir; çalışma durumları ve yıkıcı onaylar dahil (L4) | `i18n.py` |
| T1.2 | Gömülü `"Overlay/Indicator"` sabitini sil; sayfaya gerçek çevrilmiş bir ad ver (L2) | `settings_ui.py`, `ui/pages/overlay.py`, `i18n.py` |
| T1.3 | Kenar çubuğu çipleri `Local` / `Ready`'yi çevir, sürümü etiketle (L3, U7) | `ui/shell.py`, `i18n.py` |
| T1.4 | **Türkçeyi sadece doldurma, gözden geçir.** `"Şunun üstünde çalışır"`ı etiket olarak düzelt, *prompt* için tek biçim seç, çip ile ismi uyumlu hâle getir (L5) | `i18n.py` |
| T1.5 | Yerel biçimlendirme yardımcısı: ondalık/binlik ayırıcı, süre, ISO→yerel tarih. Tek modül, tek kural (L7) | yeni `ui/format.py`, `ui/pages/history.py`, `ui/pages/dashboard.py` |
| T1.6 | Platforma göre kısayol etiketleri ve yardım metni: `Win` / `Cmd ⌘` / `Ctrl` ve KDE'ye özel metin yalnızca KDE'de (X3) | `ui/pages/agent.py`, `ui/pages/shortcuts.py`, `hotkey.py`, `i18n.py` |

**Doğrulama:** T0.3 korkuluğu boş istisna listesiyle geçer; ekran turu `tr` ile
yeniden alınır ve her kare Türkçe okunur; `python -m unittest discover` yeşil.

### Faz 2 — Tasarım sistemi (4–6 g) — *Q2'ye bağlı*

| Görev | Ne | Dosyalar |
|---|---|---|
| T2.1 | **Tek bir görsel yön kilitle** ve tek doğruluk kaynağına yaz (bkz. Q2) | `ui/tokens.py`, `docs/design-reference.md` |
| T2.2 | **Erişilebilir bir açık temayı geri getir.** `normalize()`'ı `light`/`dark`'ı kendine eşleyecek şekilde düzelt ya da dürüstçe emekliye ayırıp `LIGHT`'ı sil. Bir yapılandırma değeri sessizce başka bir temaya dönüşmemeli. | `ui/tokens.py` |
| T2.3 | Kontrast ölçeğini yeniden kur: `fg2`/`fg3` doğrulanmış kontrast oranına, ve etkin / hover / odak / **pasif** durumlar birbirinden ayrı | `ui/tokens.py`, `ui/qss.py` |
| T2.4 | Kontrol yüksekliği ve boşluk ritmini bir kez tanımla; her sayfa bundan türesin (U5'i çözer) | `ui/tokens.py`, `ui/qss.py`, `ui/widgets.py` |
| T2.5 | Buton hiyerarşisi: sayfa başına tam olarak bir birincil eylem, platform geleneğine göre konumlanmış; yıkıcı eylemler görsel olarak ayrılmış (U2) | `ui/widgets.py`, `ui/shell.py`, tüm sayfalar |
| T2.6 | Durum bağlama kuralı: ana anahtarı kapalı bir kontrol, "etkin değil" diye tarif edilmek yerine devre dışı bırakılır (U8) | sayfa modülleri |

**Doğrulama:** kontrast oranları ölçülüp kaydedilir; tur iki temada da alınır;
depoda yazılı bir token tablosu; `tests/test_theme.py` genişletilir.

### Faz 3 — Yüzey yüzey yeniden inşa (10–14 g)

Bu sırayla — en görünür önce ve her yüzeyin T0.5'ten gelen kendi doğrulama karesi var.

| Sıra | Yüzey | Çözdüğü |
|---|---|---|
| 1 | Kayıt pili + duraklatılmış/meşgul/uyarı/hata durumları | U10, U11 |
| 2 | Sonuç overlay'i + canlı popup (içeriğe göre boyutlanma, boş durum) | U6 |
| 3 | Düşünme paneli — pille aynı görsel aile | U11 |
| 4 | Tepsi menüsü — ikonlar, ayırıcılar, aç/kapat durumu | U12 |
| 5 | Kontrol paneli (istatistik anlamı, boş durumlar) | U4 |
| 6 | Dokuz ayar sayfası | U2–U5, U9 |
| 7 | Native Wayland gösterge yolu ya da belgelenmiş, test edilmiş yedek | X2 |

**Doğrulama:** alınan her kare kilitlenen yöne karşı incelenir; altın-görüntü
manifestosu her commit'te bilinçli güncellenir, asla körlemesine değil.

### Faz 4 — Güvenilirliği kapatma (7–10 g)

Zaten açık olan turu kendi bağımlılık sırasıyla kapat:

| Görev | Kaynak | Ne |
|---|---|---|
| T4.1 | F1/R1 | Dinamik aktivite-oturum kaydı; koordinatör sahipli geometri |
| T4.2 | F1/R2 | Bağımsız toplantı/dikte/ajan/sonuç görünümleri; sınırlı detay yüzeyi |
| T4.3 | F1/R3 | Güvenli eşzamanlı yakalama politikası; "bu cihaz meşgul" için yıkıcı olmayan arayüz |
| T4.4 | F1/R4 | Ses, herhangi bir sınıflandırmadan önce kalıcı yazılır; çökmede bulunabilir kayıt |
| T4.5 | F1/R6 | Geçmiş/Tutanak kurtarma detayları, açık silme, yeniden deneme arayüzü |
| T4.6 | F1/R7 | Düzenleme seviyesi göçünün tamamlanması + EN/TR eşitliği |
| T4.7 | F1/R8 | Yukarıdaki her kusur için deterministik regresyon kapsamı |
| T4.8 | F2 | `except Exception` istisna listesini yak: kalan her yer ya hatasını bildirir ya da gerekçesiyle açıkça listelenir |
| T4.9 | F3 | `OverlayCoordinator.update` tetikleyicisi; `Config.data` okuma yarışını kapat; süreçler arası kilide karar ver |

**Doğrulama:** `docs/ai/TASKS.md` R1–R8 işaretli; son diff üzerinde taze bir
gözden geçiren (V4); yeni regresyon testleri adlarıyla
`docs/ai/VERIFICATION.md`'de, tam takım yeşil.

### Faz 5 — Dağıtım ve platformlar arası (15–20 g)

| Görev | Ne |
|---|---|
| T5.1 | İşletim sistemi başına PyInstaller spec'i; donmuş uygulama geliştirici Python'u istememeli |
| T5.2 | Donmuş ürünü **başlatan** ve açılışı doğrulayan işletim sistemi başına CI derleme işleri — mevcut CI yalnızca test çalıştırıyor (X4) |
| T5.3 | Linux: AppImage + Flatpak (+ `.desktop`, ikonlar, PipeWire/portal izinleri) |
| T5.4 | Windows: donmuş uygulamayı mevcut `install.ps1` üzerinden dağıt; isteğe bağlı taşınabilir zip |
| T5.5 | macOS: `.app`/`.dmg`, imzalama + notarization, `NSMicrophoneUsageDescription` ve açık bir Erişilebilirlik-izni akışı — kısayol yolu buna ihtiyaç duyuyor ve bugün hiçbir yerde yazılı değil |
| T5.6 | İşletim sistemi başına yazılı, elle doğrulama protokolü (kontrol listesi); böylece bir macOS/Windows iddiasının arkasında umut değil kanıt olur |
| T5.7 | macOS kod yollarının hiç değilse çalıştırılması için bir macOS CI koşucusu ekle |

**Doğrulama:** her işletim sisteminden indirilen bir yapı açılır, kaydeder,
yazıya çevirir, yapıştırır ve kapanır; her koşu gözlemlendiği işletim sistemi ve
sürümüyle `docs/ai/VERIFICATION.md`'ye yazılır.

### Faz 6 — Ürün derinliği (isteğe bağlı, sıralı)

Yalnızca Faz 5'ten sonra. Değere göre sıralı:

1. İlk çalıştırma deneyimi: çalışan üç adımlı bir sihirbaz (mikrofon → model →
   test); çünkü yerel model indirmesi bugün sürtünmenin en yüksek olduğu an.
2. `sherpa-onnx` akışlı ara sonuçları, isteğe bağlı ikinci yerel motor olarak (§3.4).
3. `dikte doctor --json`'dan teşhis paketi — zaten %80 hazır — telemetri olmadan
   hata raporu için.
4. Toplantılar için kanal ayrımının ötesinde konuşmacı ayrıştırma kalitesi.

## 6. Doğrulama sözleşmesi

Her faz için pazarlıksız, `ai/workflows.md`'den devralınmış:

- Yeni korkuluk, düzeltmeden önce **kırmızı**, sonrasında **yeşil** olduğu
  kanıtlanır. Hiç kırmızı olmamış bir korkuluk kanıt değildir.
- Hedefli modüller → tam takım → `git diff --check`.
- Her faz gerçek komut çıktısını `docs/ai/VERIFICATION.md`'ye yazar.
  Tahmini PASS yok.
- Ekran turu yeniden alınır ve incelenir; varsayılmaz.
- Faz tamam sayılmadan önce grafik tazelenir.
- §7/Q3 açık kararı olmadan yeni üçüncü taraf bağımlılık yok.

## 7. Kararlar

2026-09-12'de kaydedildi. Açık kalan her şey, ona bağlı olan fazı bloke ediyor.

| # | Soru | Cevap |
|---|---|---|
| **Q1** | **Lisans niyeti**: GPL-3.0'da mı kalınacak (PyQt6 kalır) yoksa GPL dışı bir yapı seçeneği mi korunacak (PySide6'ya geçilir)? | **Ertelendi.** Faz 0 çelişkiyi `pyproject.toml` içinde belgeliyor ve üst veriyi olduğu gibi bırakıyor. **T5.5'i hâlâ bloke ediyor** — imzalı kapalı kaynak ikili dağıtım bu cevaplanmadan mümkün değil ve mevcut durum iki okumada da dağıtılabilir değil. |
| **Q2** | **Görsel yön** | **Cevap: belgelenen "Sıcak Teknik Minimalizm"e dönülüyor** — sıcak taş `#F4F1EA` zemin, kum `#EEE9DE` kenar çubuğu, fildişi `#FBFAF6` yüzeyler, mürekkep `#242628` metin, tek vurgu olarak terrakota `#E4573D` ve **gerçek bir açık + gerçek bir koyu tema**. Bu, `docs/design-reference.md`'yi yeniden bağlayıcı sözleşme yapıyor ve altı türetilmiş koyu renk odasını ürün yüzeyi olmaktan çıkarıyor. |
| **Q3** | **Bağımlılık politikası** | **Cevap: stdlib + PyQt6 kuralı sürüyor.** Paketleme araçları **yalnızca derleme zamanı** istisnası; yani Faz 5'te PyInstaller serbest ve çalışma zamanına hiçbir yeni şey girmiyor. Dolayısıyla `ui/format.py` (T1.5) elle yazılıyor ve `sherpa-onnx` (§3.4) **alınmıyor**. |
| **Q4** | **Dağıtım**: hangi kurulum dosyaları olmalı? | **Hâlâ açık.** Faz 5'i boyutlandırır; Faz 1 veya 2'ye başlamak için gerekli değil. |
| **Q5** | **Donanım erişimi** | **Cevap: bir Windows makinesi var.** Yani Faz 5 Windows'ta elle doğrulanabilir ve T5.6 protokolü onu kapsamalı. **macOS doğrulanmamış kalıyor** — orada iddia edilen her şey yalnızca CI kaynaklı ve öyle etiketlenmeli. |

### Q2'nin planın sindirmesi gereken sonuçları

Sıcak yönü kilitlemek bir palet takası değil; mevcut ürün yüzeyini emekliye
ayırıyor. Somut olarak Faz 2'nin yapması gerekenler:

- `ui/tokens.py`'yi kurallı temalar `light` ve `dark` olacak şekilde yeniden
  yazmak; altı renk odası ya kaldırılır ya isteğe bağlı ikincil bir küme olur —
  bu karar Faz 2'nin içinde, öncesinde değil;
- `LIGHT`'ı erişilebilir kılmak (T2.2), `normalize()`'ın çöpe attığı bir alias
  olmaktan çıkarmak;
- **`docs/settings-*.webp` görsellerini yeniden çekmek** — şu an yatay sekmeli,
  kenar çubuksuz *önceki* bir arayüz neslini tanıtıyorlar — ve README'nin
  ekran görüntüsü tablosunu hâlâ var olan sayfalara indirmek;
- vurgu kullanımını yeniden türetmek: terrakota bir *kayıt* sinyali, düğme rengi
  değil; bu, `ui/qss.py` içindeki her `accent` dolgulu kontrolü değiştirir.


## 8. Risk kaydı

| Risk | Etki | Önlem |
|---|---|---|
| Arayüz, yön kilitlenmeden yeniden inşa edilirse | Dördüncü bir tasarım nesli; emek çöpe gider | T2.1 başlamadan Q2 cevaplanır |
| Faz 4 durum makinesine, Faz 3 aynı overlay'e dokunurken | Birleştirme çakışmaları ve çift regresyon | Faz 4, Faz 3'ten sonra, ayrı dallarda |
| 103 metni çevirmek Türkçe metin kalitesini düşürürse | Arayüz, kullanıcıların çoğunun gördüğü dilde kötüleşir | T1.4 doldurma değil, ana dili konuşan biriyle gözden geçirme görevi |
| Faz 5 (üç işletim sistemi × imzalama × notarization) bütün bütçeyi yerse | Özellik çalışması durur | Faz 5 en sonda ve bölünebilir; yalnızca T5.1–T5.2 bile en büyük engeli kaldırır |
| 313 `except Exception` yeri yeniden inşa sırasında gerçek bir arızayı saklarsa | Kullanıcıya görünen bir kusur, başarı gibi görünerek yayınlanır | T0.6 ölçülebilir kılar; T4.8 her yeri ya dürüst ya belgeli hâle getirir |
| macOS/Windows yolları doğrulanmadan yayınlanırsa | İlk gerçek kullanımda güven kaybı | Q5; ve T5.6 protokolü, `VERIFICATION.md`'de işletim sistemi başına kanıtla |

## 9. Değişiklik kaydı ve kanıt

### 2026-09-12 — Faz 0 uygulandı

Dokunulan dosyalar (6 değişti, 6 eklendi):

| Dosya | Değişiklik |
|---|---|
| `pyproject.toml` | `requires-python` → `>=3.11,<3.15`; lisans çelişkisi yerinde belgelendi, Q1'e işaret ediyor |
| `.github/workflows/tests.yml` | üç matrise de `"3.14"` eklendi, doğrulanmamış platformlar notuyla; yeni bir Linux adımı `tools/shoot_ui.py --check` koşuyor |
| `tests/test_i18n.py` | sayaç korkuluğu tam-küme korkuluğuyla değiştirildi; `untranslated_strings()` ve `recorded_gaps()` üreticinin de paylaşabilmesi için modül seviyesine alındı |
| `tests/i18n_untranslated.json` | yeni — kayıtlı boşluk kümesi, çağrı yerleriyle 104 kayıt |
| `tests/test_icon_contracts.py` | yeni — `shell.NAV` ve ikon API'sine geçen her sabit üzerinde ikon-anahtarı bütünlüğü |
| `tools/i18n_gaps.py` | yeni — boşluk kaydının üreticisi/okuyucusu |
| `tools/except_audit.py` | yeni — geniş yakalayıcı sayımı |
| `tools/shoot_ui.py` | yüzey manifestosu, kaynaktan türeyen sayfa sayısı, `--check`, ve `--check`'in CI'a bağlanması |
| `ui/icons.py` | `history` glifi eklendi (`shell.NAV` istiyordu ve boş çiziliyordu) |
| `settings_ui.py` | overlay sayfası hiç var olmayan `"pip"` ikonunu istiyordu; artık `monitor` istiyor |

Ham sonuçlar:

```
$ python3.14 -m unittest discover
Ran 1477 tests in 101.148s
OK

$ python3.14 tools/shoot_ui.py --out /tmp/dikte-check --themes blue --langs tr,en --check
wrote 60 PNGs to /tmp/dikte-check
surface check OK: 30 surfaces x 2 theme-and-language runs, all drawn

$ python3.14 tools/except_audit.py
313 broad handlers in 36 modules. `--list` shows them, `--allowlist` prints the skeleton.

$ git diff --check      # temiz
```

Kırmızı kanıtlar, her düzeltme inmeden önce koşuldu:

```
ikon korkuluğu, öncesi:  settings_ui.py:503 add_page('history')
                         settings_ui.py:507 add_page('pip')
                         ui.shell.NAV requests unknown icon keys: ['history']
i18n korkuluğu, düşür:   AssertionError: Lists differ: [] != ['Ask']
i18n korkuluğu, uydur:   AssertionError: Lists differ: [] != ['Nobody translated this']
yüzey denetimi, eksik:   ['missing: blue_en_overlay_somehow_missing.png']
yüzey denetimi, boş:     ['blank: blue_tr_overlay_rec.png']
```

Grafik: `5372 nodes, 9509 edges, 311 communities`, `Built from commit: ffe8a5c7`.

### Faz 0 sırasında bu belgede düzeltilenler

Kaydediliyor, çünkü sessizce kendini düzelten bir plan, nerede yanıldığını
gösterenden daha kötüdür:

- **X4 yanlıştı.** macOS CI koşucusu olmadığını iddia ediyordu.
  `.github/workflows/tests.yml` baştan beri `test-macos` işini `macos-latest`
  üzerinde koşuyor. Bulgu daha zayıf hâliyle ayakta: hiçbir iş donmuş bir yapı
  derlemiyor veya başlatmıyor.
- **L1 düşük ölçülmüştü.** Tek ölçüm kaynağı olarak `tools/i18n_gaps.py` ile
  103 → 104.
- **L6 biçim olarak yanlıştı.** Takımın i18n boşluğunu hiç korumadığını
  söylüyordu. Koruyordu — iki birim gevşekliği olan, `_t` takma adını göremeyen
  bir sayaç olarak. Düzeltilmiş bulgu daha güçlü ve daha kesin.
- **T0.5 fazla belirtilmişti.** Plan altın-görüntü turu istiyordu; piksel altın
  görüntüler Qt sürümleri ve platformlar arasında deterministik değil ki bu depo
  bunu yasaklıyor. Bunun yerine, gerekçesi aracın içine yazılarak
  varlık-ve-boş-olmama denetimi teslim edildi.

---

*2026-09-12'de `master @ ffe8a5c` üzerinde salt-okunur bir incelemeyle
başlandı; Faz 0 aynı gün uygulandı. İngilizce aslı: [`ROADMAP.md`](ROADMAP.md).*
