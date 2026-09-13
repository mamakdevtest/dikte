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
| L5 | S2 | **Mevcut Türkçe karşılıklar kötü.** `"Runs on" → "Şunun üstünde çalışır"` üç sayfada (Ajan, Toplantı, API) form etiketi olarak kullanılan bir cümle parçasıydı; artık `"Çalıştığı yer"`. `"Local"` çipi çevrilmemişti, hemen yanında `"Local dictation" → "Yerel dikte"` vardı; artık `"Yerel"`. **Düzeltme:** tarama ayrıca `Promtlar`/`Promptlar` yazım ikiliği iddia ediyordu — `Promtlar` depoda hiçbir yerde geçmiyor, ekran görüntüsünün yanlış okunmasıydı. Tablo baştan beri `Promptlar` diyor. | `i18n.py:531,993`; 2026-09-12'de düzeltildi |
| L6 | S1 | **i18n korkuluğu küme değil sayaçtı.** `test_user_visible_strings_reach_t` 102 ölçen bir tarama üzerinde `len(missing) <= 104` doğruluyordu — iki birim gevşeklik, yeni bir boşluğu eskisinden ayırmanın imkânı yok (bir çevrilmemiş metni başkasıyla değiştirmek sayıyı korur), boşluk kapandığında sıkma yok ve `_t` takma adı kapsam dışı — her sayfanın kenar çubuğunda görünen `Local` ve `Ready` tam da bu yüzden görünmez kaldı. Faz 0'da tam-küme kaydıyla değiştirildi. | `tests/test_i18n.py`, `tests/i18n_untranslated.json` |
| L7 | S3 | Yerel sayı/tarih biçimlendirmesi yok: süreler Türkçede `3.2s` / `2.0 sn` (nokta ondalık) çıkıyordu, geçmiş satırları ISO `2026-08-21 12:05:00` gösteriyordu. **Faz 1'de düzeltildi**, `ui/format.py` ile. | `blue_tr_page00.png`, `blue_tr_page09.png` |
| L8 | S2 | **Çeviri tablosu, kimsenin sormadığı girdiler taşıyor.** İki statik ölçüm ayrışıyor, çünkü anahtar sık sık bir değişken üzerinden geliyor: çağrı yerlerini taramak 131 anahtarın `t("literal")` çağıranı olmadığını söylüyor, ürün kodundaki tüm string sabitlerini taramak 69 diyor. Beşi değiştirilmiş (superseded) oldukları kanıtlanıp Faz 1'de silindi (`"No KDE shortcut installed."` ×3, `"Registered in KDE: {shortcut}"`, `{retry}` öncesi tutanak mesajı). Kalanlar çalışma zamanı kapsaması gerektiriyor — statik tarama bunu cevaplayamaz ve iki sayı da fazla rapor ediyor. | Faz 1 silmesi; ölçüm aracı Faz 6'da öneriliyor |
| L9 | S2 | **Bir kaynak metin İngilizce değil Türkçe yazılmıştı.** `ui/pages/dashboard.py` `t("Genel bakış — son dikte ve toplantılarınız")` çağırıyordu ve tabloda bu Türkçe metni kendine eşleyen bir girdi vardı — yani *İngilizce* pencere Türkçe gösteriyordu, Türkçe pencere doğru görünüyordu ve boşluk korkuluğu bunu göremiyordu (girdi var mı diye soruyor, vardı). Çağrı yerinde düzeltildi; ardından yeni korkuluk, düzeltmenin kaçırdığı **aynı girdinin ikinci ve önceden var olan bir kopyasını** hemen buldu. | `tests/test_i18n.py::test_no_source_string_is_already_turkish` |

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
| X2 | S1 | **Linux tarafındaki overlay XWayland'e bağımlı.** `dikte.py` göstergeyi ekran köşesine yerleştirebilmek için `QT_QPA_PLATFORM=xcb` ayarlıyor; yalnızca Wayland çalışan, XWayland'siz bir oturumda gösterge hiç yerleştirilemiyor ve kesirli ölçekleme de bu yolda güvenilir değil. **2026-09-12'de belgelenmiş, test edilmiş yedek olarak kapatıldı:** sınır duruyor (layer-shell yolu üçüncü taraf modül gerektirir; bu ajanın değil kullanıcının kararı), ama pencereyi yerleştiremeyen oturum artık sessiz değil — `paste.indicator_platform()` `XCB` / `NATIVE` / `UNPLACED` döndürüyor, Gösterge sayfası geçerli olduğunda söylüyor, README'ler belgeliyor ve import anındaki davranış kendi sürecinde test ediliyor. Bu satırdaki atıf `dikte.py:41`'di; blok 33–37'ye kaymıştı. | `dikte.py:33-37`, `paste.py`, `README.md` |
| X3 | S3 | **2026-09-12'de düzeltildi: bu bulgu büyük ölçüde yanlıştı.** Kısayol alanı zaten platforma göre öneri listesi seçiyor (`SHORTCUTS` / `WIN_SHORTCUTS` / `MAC_SHORTCUTS`, `hotkey.desktop_name()` ile), iki kısayol varsayılanı da boş yani yeni kurulumda hiç ipucu görünmüyor, ve KDE'ye özel açıklama `hotkey.shortcut_needs_restart()` ile koşullu, macOS için ayrı bir dal var. Taramanın itiraz ettiği `Meta+A`, ürünün değil `tools/shoot_ui.py`'nin kendi test verisinden geliyordu — **bir ekran görüntüsü aracı, ürün hakkında bir bulgu uydurdu.** Ayakta kalan tek şey L8: kimsenin sormadığı üç KDE'ye özel anahtar. | `settings_ui.py:127-141`, `hotkey.py:desktop_name`, `tools/shoot_ui.py:CHANGED` |
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
| H6 | S3 | **`ui/components.py` ölü kod ve canlı olanı gölgeliyor.** `ui/widgets.py`'yi kopyalayan bir `Button` ve `Dropdown` tanımlıyor; hiçbir kaynak dosya, test ya da belge onu import etmiyor. `Button`'ı `btn()`'in yükseklik mantığının kopyasıydı, çağrısı değil — yani ritimden habersizce sapabilirdi. Silinmedi, kaydedildi: bir modülü kaldırmak kendi incelemesi olan ayrı bir değişiklik. | `grep -rn "components" --include=*.py .` dosyanın kendisi dışında hiçbir şey bulmuyor |
| H7 | S3 | **Uzun metin beş sayfa modülünde kopyalanmış.** Aynı yardım metni `audiofile.py` (×3), `cleanup.py`, `general.py` ve `history.py`'de ikişer kez geçiyor. Çoğu neredeyse kesinlikle bir if/else'in iki dalı, iki canlı öğe değil — ama `cleanup.py`'deki birlikte çiziliyordu, kare üzerinde doğrulandı ve düzeltildi. Kalanlar gerçekte neyin çizildiğine göre yargılanmalı; o iş yüzey turunun. | her sayfa modülünde 40 karakterden uzun `t("…")` literalleri üzerinde bir tarama |

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
değişikliği (`pyqtSignal`→`Signal`, `pyqtSlot`→`Slot`). `pyproject.toml` MIT
diyordu ve bu PyQt6 ile bağdaşmıyordu; açık kalan soru §7'deki **Q1**'di.

**13.09.2026'da cevaplandı: üst veri `GPL-3.0-only` olarak düzeltildi ve PyQt6
kalıyor.** Permissif yol bir lisans seçimi değil bir göçtü — copyleft seçen
bir projenin ihtiyacı olmayan üst veriyi satın almak için PySide6'ya geçmek —
o yüzden tartılıp reddedildi. Yani Faz 5'in yapıları GPL-3.0 yapıları; zaten
fiilen öyleydiler, değişen şey paketleme üst verisinin bunu artık söylüyor
olması. `docs/ai/DECISIONS.md`'ye kaydedildi.

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
   **README artık var olmayan bir ürünü tanıtıyor.** *(13.09.2026'da düzeltildi: yedi
   kare de sevk edilen yapıdan `tools/shoot_ui.py --readme` ile yeniden çekildi —
   koyu, İngilizce, 1475x1489, değiştirilmeden önce gözle incelendi. 13.09.2026'da
   sekizincisi katıldı: `docs/setup.webp`, ilk-kurulum sihirbazının mikrofon adımı;
   fixtür cihaz listesiyle çizildi, yani resim alındığı kum havuzunun değil ürünün.)*
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
| T0.1 ✅ | Lisans çelişkisi **13.09.2026'da çözüldü** — `pyproject.toml` `GPL-3.0-only` beyan ediyor, `LICENSE` ve iki README ile uyuşuyor, PyQt6 kalıyor (Q1, karar `docs/ai/DECISIONS.md`'de). | `pyproject.toml:11` |
| T0.2 | `requires-python` `>=3.11,<3.15` oldu; üç CI matrisine de `"3.14"` eklendi. Eski sınır, takımın zaten geçtiği bir yapılandırmayı dışlıyordu; yani kodu değil paketleme politikasını anlatıyordu. | 1477 test 3.14.7'de yerelde geçiyor; Windows/macOS 3.14 doğrulanmadı diye açıkça işaretlendi |
| T0.3 | Sayaç korkuluğu **tam-küme kaydıyla** değiştirildi — `tests/i18n_untranslated.json`, çağrı yerleriyle birlikte 104 kayıt — üretici olarak da `tools/i18n_gaps.py`. Tarama artık `_t` takma adını da izliyor. İki yön de kırmızı oluyor. | iki kez kırmızı kanıtlandı: `Ask` düşürülünce → `['Ask']`; `Nobody translated this` uydurulunca → `['Nobody translated this']` |
| T0.4 | Yeni `tests/test_icon_contracts.py`, ve bulduğu iki ölü anahtar düzeltildi: `settings_ui.py:507` artık `monitor` istiyor, `ui/icons.py` bir `history` glifi kazandı. | önce kırmızı kanıtlandı, iki kusuru da adıyla: `settings_ui.py:503 add_page('history')`, `settings_ui.py:507 add_page('pip')`, `ui.shell.NAV → ['history']` |
| T0.5 | `tools/shoot_ui.py` bir yüzey manifestosu, kaynaktan türeyen sayfa-sayısı çapraz kontrolü ve `--check` kazandı; hatırlanmaya gerek kalmadan koşması için Linux CI işine bağlandı. | iki dal da kırmızı kanıtlandı: `missing: blue_en_overlay_somehow_missing.png` ve `blank: blue_tr_overlay_rec.png` (turun temaları o zaman `blue,orange`'dı; şimdi `light,dark` koşuyor); yeşil koşu `30 surfaces x 2 theme-and-language runs, all drawn` diyor |
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

### Faz 1 — Yerelleştirmeyi kapatma — **UYGULANDI 2026-09-12**

| Görev | Teslim edilen | Nasıl çalıştığı gösterildi |
|---|---|---|
| T1.1 | 104 metnin tamamı çevrildi; tablonun sonunda, kaynak modüle göre gruplanmış tarihli bir blok olarak. Blok, yeni metinlerin buraya değil yukarıdaki konusal bölümlere gitmesi gerektiğini yazıyor. | `python tools/i18n_gaps.py` → **`0 strings reach t() with no Turkish entry`**; kayıt boş ve korkuluk yeniden dolarsa kırmızı oluyor |
| T1.2 | İngilizce kaynak artık eğik çizgili `"Overlay/Indicator"` değil `"Indicator"`; hem menü etiketinde hem sayfa başlığında. Türkçesi `"Gösterge"`. | `settings_ui.py:507`, `ui/pages/overlay.py:59`; yeniden çekilen karede doğrulandı |
| T1.3 | `"Local"` → `"Yerel"`, `"Ready"` → `"Hazır"`, ve etiketsiz `1.0` artık `"Sürüm"` tooltip'i taşıyor. | yeniden çekilen karede kenar çubuğu alt bilgisi: `whisper-1 · Yerel · ● Hazır · 1.0` |
| T1.4 | `"Runs on" → "Çalıştığı yer"` (üç sayfada cümle değil form etiketi). *prompt* alt maddesi yanlış bir öncül çıktı — bkz. §9. | `i18n.py:531` |
| T1.5 | Yeni `ui/format.py` (`decimal_separator`, `number`, `seconds`, `when`) ve `meeting.format_when`'in saniyeli damgaları da okuyacak şekilde genişletilmesi; böylece ay adları ikinci kez yazılmadı. Geçmiş listesi, geçmiş detay penceresi ve kontrol panelinde uygulandı. | yeniden çekilen kareler `21 Ağu 2026 12:05 (2,0 sn)`, `3,2 sn`, `10 dk` okuyor — öncesi `2026-08-21 12:05:00`, `3.2s` |
| T1.6 | **Yapılacak bir şey yoktu** — bulgu yanlıştı. Düzeltilmiş X3'e bakın. | `settings_ui.py:127-141` |
| — | İş yapılırken iki kusur daha bulundu: **L8** (ölü girdiler) ve **L9** (İngilizce kaynak yerine Türkçe metin). L9 kalıcı bir korkuluk kazandı. | `tests/test_i18n.py::test_no_source_string_is_already_turkish`, düzeltme inmeden önce kırmızı kanıtlandı |

**Doğrulama:** boşluk kaydı boş; tur `tr` ve `en` ile yeniden alındı ve kare kare
okundu — o karelerde kalan her İngilizce metin arayüz değil veri (bir model
kimliği, bir sağlayıcı kimliği, fixture'ın kendi toplantı başlığı).

### Faz 2 — Tasarım sistemi — **bitti 2026-09-12**

| Görev | Durum | Teslim edilen ve bunu neyin kanıtladığı |
|---|---|---|
| T2.1 | **bitti** | Belgelenen sıcak yön artık tek yön. `ui/tokens.py` bir sıcak-taş `LIGHT` ve bir sıcak-kömür `DARK` taşıyor, başka hiçbir şey yok. **Altı doygun renk odası emekliye ayrıldı.** Her biri bir kömür tabanın tek bir vurguyla karışımıydı — altısının da "aynı koyu arayüz, farklı renkli düğme" olarak okunmasının ve uygulamanın takip ettiğini iddia ettiği tasarıma hiç benzememesinin sebebi buydu. `RETIRED_THEMES` adlarını saklıyor, böylece `normalize()` hâlâ tema sanmak yerine yerlerine ne geçtiğini açıkça söyleyebiliyor. |
| T2.2 | **bitti** | `light` ve `dark` kendine eşleniyor; açık tema ilk kez erişilebilir. Varsayılan `blue`'dan `dark`'a taşındı (`config.py`, `settings_ui.py`, `dikte.py`, `ui/shell.py`). Seçici iki temayı sunuyor ve dairelerin seçim halkası paletin mürekkebinden geliyor; böylece açık bir daire açık kenar çubuğunda artık kaybolmuyor. |
| T2.3 | **bitti** | Her metin eşleşmesi üzerine çizildiği arka plana karşı ölçüldü: `fg` 12,2–12,7:1, `fg2` 7,5:1, `fg3` en kötü 5,5–5,6:1, durum renkleri kendi tonlarında çip etiketi olarak 4,6–6,5:1, dolgulu düğme 14,5–17,0:1 ve çizgiler 1,31–1,90:1 ile görünür. `tests/test_theme.py` hepsini sabitliyor. Durum gözden geçirmesi gerçek kusuru buldu: `ghost` ve `danger`, `border-color: transparent`'ı odak kuralının *altında* bildirdiği için QSS'in belge-sırası eşitliği onlara hiç odak halkası bırakmıyordu — tek bir odak kuralı her değişkenden sonra konularak düzeltildi, değişken başına korkuluk altına alındı. **Doğrulanmadı:** halkanın gerçekten çizildiği; çünkü odaklanmamış offscreen pencerede odak oluşmuyor. |
| T2.4 | **bitti** | Ritim `ui/tokens.py`'de bir kez bildiriliyor (`CONTROL`, `ROW_HEIGHT`, `CELL`, `INDICATOR`) ve başka hiçbir yer kendi yüksekliğini seçemiyor. Alanlar, açılır kutular, düğmeler, segment kontrolü ve kenar çubuğu satırları `CONTROL["md"]`'ye taşındı; böylece bir kontrol ile komşusu şansa değil kuruluma göre hizalanıyor. Korkuluk altında: sheet'te 1px üstü literal `min-height`, 14px üstü literal `height` yok; kodda 14 üstü `setFixedHeight` yok. |
| T2.5 | **bitti** | Düğme seviyeleri artık referansın dediği anlama geliyor. Ajan ve Toplantı sayfalarındaki `Reset to default` ikincildi ve referans Reset'i ghost örneği olarak adlandırıyor — artık ghost. İndirilmiş bir modeli silen `Delete` ghost'tu, yani bir yer iminin ağırlığındaydı, üstelik onaylı yıkıcı bir eylemde — artık danger. İki eylem satırı da yıkıcı düğmeleri boşluktan sonraya alıyor: Geçmiş'te Sil, Kopyala ile boşluk arasındaydı; Tutanak'ta aynı biçim ters sırayla vardı, yani iki sayfa birbiriyle de çelişiyordu. Korkuluk altında: satırının boşluğundan önce eklenen danger düğmesi takımı kırmızı yapıyor. |
| T2.6 | **bitti** | Her ana anahtar bağımlılarına karşı denetlendi. `auto_paste` ve `skip_silent` bağlıydı; temizleme sayfasının prompt editörleri ise `ui.widgets.gate()`'in elle kopyalanmış ve `except Exception: pass` içine sarılmış hâliyle kapılanıyordu — bağlantı başarısız olsa editörler açık kalır, üstteki anahtar ise promptların devrede olmadığını söylerdi. Artık paylaşılan yardımcıyı çağırıyor. Kalan anahtarların (`result_overlay_enabled`, `live_transcript`, `keep_audio`) bağımlısı yok: köşe seçici kayıt göstergesine ait ve bilgi notu bir kontrolü kapılamıyor, davranışı tarif ediyor. Pikselle doğrulandı: anahtar kapalıyken prompt alanı `surface2` (devre dışı arka planı) çiziyor. |

**Teslim edildiği hâliyle doğrulama:** `unittest discover` 1500 test OK, 85 sn;
`tools/quick_tests.py` 1361 test, 14 sn; `shoot_ui.py --check` 2 tema × 1 dil
boyunca 60 kare çizdi ve yüzey manifestosu bozulmadı; iki temanın farklı olduğu
dosya adıyla değil **pikselle** kanıtlandı.

Düğme işinden bir şey daha çıktı: tur bunların hiçbirini kontrol edemezmiş. Her
ayar sayfası bir kaydırma alanında yaşıyor ve çekim sabit 1000×700'dü, yani Geçmiş
sayfasının silme satırı ile Tutanak sayfasının eylem satırı tek bir karede hiç
görünmemiş. Artık her sayfa ölçülüp pencere ona göre büyütülüyor ve kareler kendi
yüksekliklerinde 700–2040 px arasında çıkıyor. Sıralama düzeltmesi sonra kare
üzerinde doğrulandı: satırda 101 px yıkıcı-kırmızı metin ve son güvenli eylemle
arasında ölçülmüş 250 px boşluk.

Bunu yaparken çıkan bulgular "Düzeltmeler"de kayıtlı: tur, iddia ettiği her tema
adı için tek palet çiziyordu (N1); terrakota tasarımın kullandığı hiçbir boyutta
düğme metnini taşıyamıyor (N2); hiçbir şeyle eşleşmeyen bir stil kuralı iki biçimde
daha sessizce başarısız oluyor (N3); ve tur her sayfanın yalnızca üstünü
fotoğraflıyordu (N4).

### Faz 3 — Yüzey yüzey yeniden inşa (10–14 g) — **bitti 2026-09-12, yedi yüzeyin hepsi**

Bu sırayla — en görünür önce ve her yüzeyin T0.5'ten gelen kendi doğrulama karesi
var. Her bulgu, hiçbir şey değiştirilmeden önce koda ve güncel bir kareye karşı
yeniden kontrol ediliyor: taramanın arayüz bulgularından üçü şimdiden eskimiş ya da
yanlış çıktı (X3, L5'in `Promtlar` yarısı ve U10'un büyük kısmı) ve üçü de eski
ekran görüntülerinden yazılmıştı.

| Sıra | Durum | Yüzey | Neyi çözdüğü |
|---|---|---|---|
| 1 | **bitti** | Kayıt pili + duraklatılmış/meşgul/uyarı/hata durumları | U10 iddia iddia kontrol edildi: zamanlayıcı kayıt bağlamını **taşıyor** (kırmızı nokta, zamanlayıcı ve Duraklat/Durdur tek bir kontrol olarak okunuyor), Duraklat ile Durdur **sıkışık değil**, ve "sürükleme tutamacı yok" belgelenmiş davranışa aykırı — `i18n.py:887` kullanıcıya göstergenin "sürüklenemez" olduğunu söylüyor ve onu Ayarlar köşeye göre yerleştiriyor. Tek gerçek kusur, canlı-yazı düğmesi ile Duraklat ve Durdur'un **hiçbir biçimde adı olmamasıydı**: pil tek bir elle çizilen widget ve yalnızca toplantı anahtarı hiç tooltip ya da erişilebilir açıklama kurmuştu. Düzeltildi; yeni bölge-adı sözleşmesi, bölge adı olmadan eklenen bir `_hover_*` bayrağında kırmızı oluyor. U11'in meşgul-pil karşılaştırması sıradaki yüzeyin işi, çünkü iki kareyi birden gerektiriyor. |
| 2 | **bitti** | Sonuç overlay'i + canlı popup (içeriğe göre boyutlanma, boş durum) | U6'nın ilk yarısı tuttu — kart gerçekten 260 px sabit bir kutu ve içinde üç satır vardı — ve düzeltildi: artık metni kadar uzun, üç satır için 124 px; genişletilmiş hâli 24 satırlık bir transkripti 460×460'ta taşıyor. İkinci yarısı eskimişti: "boş durum yok" iddiası, metin alanının baştan beri taşıdığı placeholder'dan önceye ait. Kartı doğru boyutlandırmak, sabit yüksekliğin arkasına saklanmış iki kusuru ortaya çıkardı: kart her zaman kendi metninden bir satır kısaydı (uygulama stil sayfasının metin alanlarına verdiği 8 px dolgu, yalnızca kenar boşluklarından yapılan bir sayıma görünmez, bu yüzden son satır kartın hâlâ yeri varken kayıp gidiyordu) ve pasif genişletme oku etkin renginde çiziliyordu (Qt bir QToolButton'ın metnini QStyleSheetStyle üzerinden çözdüğü için palet rengi oraya ulaşmıyor). İkisi de düzeltildi ve korkuluk altında. |
| 3 | **bitti** | Düşünme paneli — pille aynı görsel aile | U11'in ilk yarısı doğru ve bildirilenden kötüydü (hareket göstergesi çizecek bir şeyi olmayan bir QLabel'dı — N6b), ikinci yarısı desteklenemez (referans bir ayarlar referansı, gösterge hakkında hiçbir şey söylemiyor). Dosyayı okumak ayrıca panelin hiç i18n'i olmadığını ve gösterilmesinin arayüz dilini sıfırladığını (N7) buldu. |
| 4 | **bitti** | Tepsi menüsü — ikonlar, ayırıcılar, açık/kapalı durumu | U12 iddia iddia kontrol edildi: 11 aksiyonun hepsi ikon taşıyor ve `tests/test_icon_contracts.py` o adları zaten koruyor; dört ayırıcı menüyü dikte / toplantılar / ayarlar+yeniden başlat / çık olarak grupluyor; durum etikette, ikon vurgusunda ve tooltip'te görünüyor — PAUSED bilerek RECORDING etiketini paylaşıyor, çünkü duraklatma overlay'in düğmesi. Gerçek kusur bildirilmemişti: iki soru tooltip'i sabit bir ajan adı söylüyordu — "recording for Claude", "talking to Claude" — ve bu, doğrusunu zaten bilen bir `display_name(self.conf)`'un hemen altındaydı; yani Codex ve yerel model kullanıcılarına mikrofonu yanlış programın tuttuğu söyleniyordu. Düzeltildi; seçim test edilebilir bir `ask_tray_state()`'e taşındı. |
| 5 | **bitti** | Kontrol paneli (istatistik anlamı, boş durumlar) | U4'ün üç iddiası: Geçmiş'teki kurtarma kartı tuttu **ve daha kötüydü** — her durumda çiziliyordu, sayfanın en iyi yerinde boş bir liste kutusu ve ölü bir Yeniden dene düğmesi (düzeltildi: kurtarılabilir bir şey yokken gizleniyor); Gösterge sayfasının boş durumunu hiç ortalamaması tuttu (düzeltildi: iki stretch arasında duruyor); kontrol panelinin boş grafik kartı **desteklenemedi** — iki grafik kartı bir satırı paylaşıyor ve sağdaki gerçek bir donut taşıyor, boş olan da kendi "Henüz veri yok"unu ortalıyor. Tur artık kurtarılabilir bir iş serpiyor, böylece kart yalnızca boş bir kutu olarak değil iki hâliyle de fotoğraflanıyor. |
| 6 | **bitti** | Dokuz ayar sayfası | Dört iddiadan ikisi ölçümden sağ çıkmadı: **U5** (kontroller "bir kenarı paylaşmıyor") — kontroller tasarım gereği sağa hizalı, yani sağ kenarlar tek çizgiyi paylaşıyor ve sol kenarlar genişliğe göre değişiyor; 976 px'lik "taşma" ise kaydırma çubuğu yokken sayfanın genişliği; **U9** (5'li düzenleme seviyesi sıkışık) — her segment 132×34. **U3** sayılarla kapandı: soluk katman 6.06–6.67:1, pasif düğme 5.54–6.06:1, etkin düğme 12.67–13.26:1; yani pasif ile etkin 2.2 kat farklı ve ikisi de AA üstü. **U2**'nin hiyerarşisi Faz 2'de zaten kapanmıştı (Kaydet `primary`); footer'ı ölçmek taramanın görmediğini buldu — Kaydet her sayfada Promptlar'ın 3–4 px altındaydı, çünkü yüksekliği iki kez bildiriliyordu (`btn()` içinde `setFixedHeight(CONTROL[...])`, sheet'in `min-height` + dolgusuna karşı; sabitleme sessizce kaybediyordu). Düzeltildi ve T2.4 korkuluğu sıkılaştırıldı: yalnızca *literal* yükseklikleri yakalıyordu, token geçiyordu; artık bir kontrolün yüksekliğinin sabitlendiği tek yer sheet. |
| 7 | **bitti** | Native Wayland gösterge yolu ya da belgelenmiş, test edilmiş yedek (X2) | X2'nin sınırı gerçek ve kalıyor: XWayland'siz bir Wayland oturumu göstergeyi yerleştiremez ve layer-shell yolu, `AGENTS.md`'nin kullanıcı kararı olmadan izin vermediği üçüncü taraf bir modül gerektiriyor. Eksik olan, satırın diğer yarısıydı — bunu yapamayan oturumun dürüst hesabı: karar artık `paste.indicator_platform()` (`XCB` / `NATIVE` / `UNPLACED`), `dikte.py` Qt yüklenmeden önce ona soruyor, Gösterge sayfası geçerli olduğunda söylüyor ve README'ler yedeği belgeliyor. Kendi sürecinde doğrulandı, çünkü test anında platform çoktan seçilmiş oluyor |

**Doğrulama:** alınan her kare kilitlenen yöne karşı incelenir; altın-görüntü
manifestosu her commit'te bilinçli güncellenir, asla körlemesine değil.

### Faz 4 — Güvenilirliği kapatma (7–10 g) — *T4.1–T4.9 doğrulandı ya da düzeltildi; T4.8'in temizliği kaldı*

Zaten açık olan turu kendi bağımlılık sırasıyla kapat:

| Görev | Kaynak | Ne |
|---|---|---|
| **T4.1 ✅** | F1/R1 | Dinamik aktivite-oturum kaydı; koordinatör sahipli geometri — *canlı kaynağa karşı doğrulandı; bir kusur düzeltildi (widget'sız bir yuva, collapsed olsun olmasın 72 px'ti, yani collapsed bir yuva komşusunu 44 px yukarı itiyordu)* |
| **T4.2 ✅** | F1/R2 | Bağımsız toplantı/dikte/ajan/sonuç görünümleri; sınırlı detay yüzeyi — *doğrulandı: her tür için bir widget örneği, dört tane; sınırlar da gerçek sayılar (`EXPANDED_MAX_HEIGHT = 180`, `MAX_AREA_FRACTION = 0.6`)* |
| **T4.3 ✅** | F1/R3 | Güvenli eşzamanlı yakalama politikası; "bu cihaz meşgul" için yıkıcı olmayan arayüz — *doğrulandı: iki reddetme, ikisi de bir çıkış yolu gösteriyor ve ikisi de koşanı durdurmuyor* |
| **T4.4 ✅** | F1/R4 | Ses, herhangi bir sınıflandırmadan önce kalıcı yazılır; çökmede bulunabilir kayıt — *doğrulandı: `save_voice_job` transkripsiyon dalından önce, başarısız yazma worker'ı "Could not preserve recording safely" ile durduruyor ve kesilen koşu Tutanak'ta görünür kalıyor* |
| **T4.5 ✅** | F1/R6 | Geçmiş/Tutanak kurtarma detayları, açık silme, yeniden deneme arayüzü — *doğrulandı; kurtarma kartı Faz 3 yüzey 5'te düzeltildi (kurtarılacak bir şey yokken de çiziliyordu)* |
| **T4.6 ✅** | F1/R7 | Düzenleme seviyesi göçünün tamamlanması + EN/TR eşitliği — *doğrulandı: emekli kaydırıcı yalnızca onu silen `pop`'ta yaşıyor, çevrilmemiş küme boş, ve Faz 3 son eşitlik açığını kapattı (düşünme panelinin hiç i18n'i yoktu)* |
| **T4.7 ✅** | F1/R8 | Yukarıdaki her kusur için deterministik regresyon kapsamı — *doğrulandı: Faz 0–3'te eklenen korkulaklar, her biri yeşile güvenilmeden önce kırmızı kanıtlandı* |
| **T4.8 ◐** | F2 | `except Exception` listesini temizle: kalan her yer ya başarısızlığını bildirir ya da gerekçesiyle açıkça listelenir — *ölçüldü: **312 geniş handler, 84'ü bildiriyor, 228'i hiçbir şey söylemiyor** ve 247'sinin tamamı kayıtlı: 225'i **kendi korunan gövdesinden türetilmiş** bir gerekçeyle (87 "opsiyonel widget", 41 "opsiyonel import", 43 "yanlış şekildeki değer", 17 "sonradan tazelenen görünüm", 10 "çözülemeyebilecek sunum", 9 "gitmiş worker", 4 "en iyi çabayla pano geri koyma", 4 "makinenin sunamayabileceği cihaz listesi", 3 "gitmiş dosya ya da satır", 3 "orada olmayan arama", 3 "zaten yapılmış söküm", 2 "ayarlarda olmayabilecek bir hedef", 2 "burada izlenmeyen platform yolu") ve **22'si elle yazılmış, her biri kaynakta sessiz kalan ifadenin üstünde duruyor**. Mandal; bir yerin kodu artık kayıtlı gerekçesini ima etmediğinde, bir gerekçe izinli kümeden olmadığında, bekleyen küme büyüdüğünde ve elle gerekçe gereken bir yerde o gerekçe yoksa kırmızı oluyor — denetçinin kendisi de atılabilir bir ağaçta sınanıyor, çünkü hiç kırmızı olduğu görülmemiş bir korkulak tahminden ibarettir. **Temizlik son turda hakkını verdi**: `meeting.prune_audio` asla silinmemesi gereken kayıtların kümesini `read_meetings()`'ten kuruyordu ve okuma düştüğünde boş kümeye düşüyordu — yani "korunacak bir şey yok" değil, **korkulak kapalı**: elde tutma süresini geçen her kayıt gidiyordu, bitmemiş bir toplantının tek kopyası dahil. Artık soru cevaplanamadığı sürece hiçbir şey silinmiyor ve neden olduğu stderr'e yazılıyor (kırmızı kanıtta `AssertionError: 0 != 1`). İkinci dilim daha ölümcülünü buldu: elle düzenlenmiş ve metin olmayan bir `cleanup_prompt`, `Config.load()` içinde `.strip()`'e ulaşıp **hata fırlattı — uygulama hiç açılmadı**, ne pencere, ne mesaj, ne yapılacak bir şey. Artık metin olmayan istem sesli olarak yok sayılıyor, nesne olmayan bir ayar dosyası bunu söylüyor ve o yolları koruyan iki handler silindi, saklanmadı: sınanamayan bir iddia korkulak değildir. **Ve altıncı dilim eritmenin en iyi kanıtını buldu**: `settings_ui`'nin sekme koruması için yazılan rapor *açılan her ayar penceresinde* basıldı — `Qt.UniqueConnection` PyQt6'da yok, yani o `connect` her seferinde düşüyordu ve `except: pass` onu yutuyordu. Kaydedilmemiş-değişiklik sorusu hiç sorulmamıştı ve bir düzenleme sessizce kaybolabiliyordu. Bir attribute uzakta (`Qt.ConnectionType.UniqueConnection`), ve kirli bir pencereyle sekme değiştirip sorunun sorulduğunu doğrulayan bir testle sabitlendi. Kalan: 206'yı küçültmek*

**On bir dilimden sonra durum (13.09.2026).** 291 -> 228. Dilimlerin sekizi gerçek bir şey buldu —
veri kaybettiren bir temizlik, uygulamanın açılmasını durduran bir ayar dosyası, doğrulanmamış bir
donanım iddiası, sağır kalan bir seçici, sessizce yok olan on iki özellik, yazıldığı günden beri
bir kez çalışmamış bir kaydedilmemiş-değişiklik koruması, kullanıcının saklandığını sandığı bir
istem, ve hiçbir şey yapmayan düğmeler. Bunların ikisi, *bir hatayı konuşturup* bir sonraki
koşunun çıktısını okuyarak bulundu — mandalın aleyhine değil, lehine olan argüman bu.

Kalan 228'in dağılımı: **83** opsiyonel widget (satır görünürlüğü, `polish`, ikonlar — boyama),
**40** opsiyonel import (tkinter ve etiket yedekleri), **39** yanlış şekildeki değer (güvenli
yedekler; okundu ve dokunulmadı), elle `# reason:` yazmış **22** sınıflandırılmamış, **14**
sonradan tazelenen görünüm, **10** sunum, ve yedi başka sınıfa dağılmış 20. Son dört dilim
kendinden öncekinden azını buldu ve en büyük iki sınıf artık boyama: onları yeniden okumak saymak
için saymak olurdu. Sıradaki gerçek adım bir dilim daha değil, bir karar — §5'teki kapılar — ve
mandal, 228'in sessizce büyümemesi için korkulak olarak kalıyor. |
| **T4.9 ◐** | F3 | `OverlayCoordinator.update` tetikleyicisi; `Config.data` okuma yarışını kapat; süreçler arası kilide karar ver — *tetikleyici, üç overlay widget'ı casus bir koordinatöre karşı koşturularak doğrulandı; okuma yarışı **yeniden üretildi ve düzeltildi** (`json.dump` sözlüğü dolaşırken bir worker anahtar ekleyebiliyordu ve kaydetme kayboluyordu — dosya hiç risk altında değildi); kilit kararı aşağıda verildi* |

**Doğrulama:** `docs/ai/TASKS.md` R1–R8 işaretli; son diff üzerinde taze bir
gözden geçiren (V4); yeni regresyon testleri adlarıyla
`docs/ai/VERIFICATION.md`'de anılmış olarak tam takım yeşil.

### 2026-09-12 — Faz 4, T4.1–T4.7 doğrulandı ve T4.8 başladı

`docs/ai/TASKS.md`'deki R listesi 2026-08-30'da yazılmıştı ve o günden beri yeniden
okunmamıştı; R1–R8 arada inmişti. Bu yüzden her biri işaretlenmek yerine canlı
kaynağa karşı doğrulandı ve sekizinin kanıtı yerinde kayıtlı. Buradan bir kusur çıktı
(T4.1'in 72 px'lik yuvası), T4.8'den de ciddi bir tehlike:

**Qt slot'undaki bir istisna süreci düşürüyor.** Ölçüldü: PyQt6, bir slot'tan kaçan
istisnada `qFatal` çağırıyor; yani tek bir bozuk handler Dikte'yi — ve o sırada
kaydedilmekte olanı — götürüyordu. `dikte.py`'de tedavi fazdan önce de vardı: izi basıp
*geri dönen* bir `sys.excepthook`. Yük taşıyan kısmın o dönüş olduğunu hiçbir şey
söylemiyordu. Artık `dikte.report_crash`, gerekçesini söyleyen bir docstring'le, ve
`tests/test_reliability.py` iki yarıyı da kendi süreçlerinde koşuyor: hook yok → yorumlayıcı
hiç iz bırakmadan ölüyor; hook var → `ZeroDivisionError` stderr'de ve uygulama koşmaya
devam ediyor. Test, abort'u bilerek doğruluyor; böylece abort etmeyi bırakan bir PyQt
yorumu çürütmek yerine testi düşürür.

**Yazılan ama uygulanmayan bir kaydetme başarı iddia ediyordu.** `_save` iki sonucu
mantığında ayırıyordu — başarısız yazma uyarıp geri dönüyor — ama uygulama hatası
yalnızca stderr'e ulaşıyordu; yani kullanıcıya, değişmemiş bir pencereye bakarken
"Saved successfully." deniyordu. `i18n.py` tam bu durumun cümlesini baştan beri
taşıyordu ve hiçbir kod onu göstermemişti: *"Settings were saved, but some settings
could not be applied"*. Artık gösteriliyor, başarı diyaloğu gösterilmiyor. Yanındaki
baseline anlık görüntüsünün `except Exception: pass`'i de aynı yoldan gitti — baseline
olmadan pencere düzenlenmiş bir sayfayı dokunulmamıştan ayıramaz, yani
"kaydedilmemiş değişiklik" uyarısı düzenlemeleri sessizce kaçırabilirdi.

T4.8'in bundan sonra ihtiyacı olan, ölçülebilir hâle geldiğine göre: i18n'deki gibi
bir mandal — sessiz küme büyüdüğünde kırmızı olan bir kayıt — ve sonra da temizliğin
kendisi, çünkü yerler türce farklı: hiçbir şey bulmayan bir Qt öznitelik yoklaması ile
gerçekleşmemiş bir kalıcı yazma aynı arıza değil.

**Mandal aynı fazda indi** (`tests/test_except_ratchet.py` +
`tests/except_silent.json`, üstüne `tools/except_audit.py --silent/--write`).
"Hiçbir şey söylemiyor" tanımı korkulakta yaşıyor ve aracı onu import ediyor; yani
ikisi neyi saydıkları konusunda çelişemez. Kayıt, satır yerine `module:function`
anahtarlı: satır numarası, bir handler'ın üstündeki her düzenlemeyi değişiklik gibi
gösterir; çıplak bir sayaç ise bir sessiz handler'ın bir başkasıyla değiştirilmesine
izin verir — sayı hiç kıpırdamadan, ki bu L6'nın i18n sayacında bulduğu delik. Güvenilir
sayılmadan önce iki yön de kırmızı kanıtlandı:

```
yeni bir sessiz handler      zz_probe_new.py:swallow: 1 silent handler(s)
düzelen bir handler          ui/icons.py:_default_color: recorded 2, now 1
```

İkinci yön, bunun bir sayı değil kayıt olmasının sebebi: zemin kıpırdamadan inen bir
temizlik, temizlik değil commit'tir. Henüz yapılmayan, keşfedilmeyi beklemek yerine
açıkça yazılıyor: 293 yer bir **şekille** listeleniyor, her biri için gerekçeyle değil.
Düzeltilen ilk üçü veri yolundaydı (`SettingsWindow._save` içindeki uygulama hatası
bildirimi ve baseline anlık görüntüsü, ve koordinatördeki widget'sız yuva) ve geri
kalanı da bu sırayı izlemeli — bir yazma yolunda yutulan başarısızlık kullanıcıya
söylenmiş bir yalandır, yutulan bir Qt öznitelik yoklaması ise eksik bir incelik.

### Faz 5 — Dağıtım ve platformlar arası (15–20 g)

| Görev | Ne |
|---|---|
| T5.1 ✅ | İşletim sistemi başına PyInstaller spec'i; donmuş uygulama geliştirici Python'u istememeli — *`packaging/dikte.spec` (tek çalıştırılabilir, dört varlık ağacı, ölçülü bir Qt dışlama listesi) ve `packaging/build.py`. **Linux 7.2.2 / Python 3.14.7 / PyInstaller 6.22.3 üzerinde kuruldu ve başlatıldı: 315.3 MB, üç açılış kontrolü de yeşil.** "Geliştirici Python'u" yarısı gerçekti: üç çağıran `sys.executable + script_path()`'i elle kuruyordu; dondurulmuş pakette bu, diskte olmayan bir dosyayı adlandırır. Artık `ipc.launch_command()` üzerinden geçiyorlar ve kısayol dizesi tırnaklanıyor (tırnaklanmıyordu — boşluklu bir yoldaki kopya, `.desktop` dosyasına iki kelime olarak yazılıyordu). macOS ve Windows aynı spec ile kurulur ve **burada doğrulanmadı** — CI işi hiç koşmadı, çünkü hiçbir şey push edilmedi* |
| T5.2 ◐ | Donmuş ürünü **başlatan** ve açılışı doğrulayan işletim sistemi başına CI derleme işleri — mevcut CI yalnızca test çalıştırıyor (X4) — *`.github/workflows/build.yml`: Ubuntu + macOS + Windows, her biri kuruyor ve ardından `packaging/build.py --check`'i koşuyor; yani ürün başlatılıp üç şey doğrulanıyor (`--help`, ayrıştırılmış bir `doctor --json`, ve kendi soketinde dinleyen bir pencere). Yazıldı ve Linux'ta kanıtlandı; **diğer iki platformun hükmü, bir push işi koşturana kadar yok** ve yol haritası bunu varsaymak yerine söylüyor* |
| **T5.3 ◐** | Linux: AppImage + Flatpak (+ `.desktop`, ikonlar, PipeWire/portal izinleri) — *Q4'e bağlı olmayan kısım indi: `install.sh` artık `dist/dikte/` içinde bir paket varsa onu kuruyor, tıpkı `install.ps1` gibi — Python hiç gerekmiyor, `dikte` komutu pakete sembolik bağlantı oluyor (bootloader `_internal/`'i bulmak için gerçek yolu çözüyor; bu, güvenilmeden önce denendi), menü ve otomatik başlangıç girdileri paketi kendi ikonuyla çalıştırıyor. **`Exec` satırı artık tırnaklanıyor**, tırnaklanmıyordu: boşluklu bir yoldaki depo, `.desktop` dosyasına iki argüman olarak yazılıyordu. Atılabilir HOME'larda iki modda doğrulandı; dondurulmuş vaka, dal devre dışı bırakılarak kırmızı kanıtlandı (`tests/test_install_sh.py`, 3 test). **AppImage ve Flatpak'ın kendisi başlamadı** — hangisinin kurulacağı Q4* |
| **T5.4 ◐** | Windows: donmuş uygulamayı mevcut `install.ps1` üzerinden dağıt; isteğe bağlı taşınabilir zip — *spec artık yalnız Windows'ta ikinci, **konsolsuz bir `diktew.exe`** üretiyor (ekranda konsol parlaması bir Windows sorunu; ikinci çalıştırılabilir kendi modül arşivini taşıdığı için diğer platformlar bunun bedelini ödemiyor) ve `install.ps1` `dist\dikte\` içinde duran bir paketi tercih ediyor: Python hiç gerekmiyor, pip ile hiçbir şey kurulmuyor, shim, Başlat menüsü girdisi, başlangıç girdisi ve kısayol kaydı hepsi paketi işaret ediyor. Kurucunun arkada bir arayüz bırakmadan koşabilmesi için `-NoLaunch` eklendi. **Buradaki hiçbir şey Windows'ta çalıştırılmadı** — PowerShell Linux'tan denetlenemiyor ve parantez sayacı parser değil — bu yüzden `.github/workflows/build.yml` `windows-latest` üzerinde `install.ps1 -NoLaunch` koşuyor ve shim'in var olduğunu, `dikte --help`'in onun üzerinden çalıştığını doğruluyor. O hüküm bir push bekliyor. Taşınabilir zip başlamadı* |
| **T5.5 ◐** | macOS: `.app`/`.dmg`, imzalama + notarization, `NSMicrophoneUsageDescription` ve açık bir Erişilebilirlik-izni akışı — kısayol yolu buna ihtiyaç duyuyor ve bugün hiçbir yerde yazılı değil — *spec `.app`'i mikrofon kullanım metniyle zaten kuruyor (T5.1); `packaging/build.py --dmg` artık onu kullanıcıların beklediği `/Applications` sembolik bağlantısıyla bir disk imajına paketliyor ve **inanmadan önce bağlıyor** (`hdiutil attach`, içine bak, ayır). CI işi bunu macOS'ta koşuyor, yani imajı onu üreten iş doğruluyor. İki README artık yol haritasının eksik dediği izin bölümünü taşıyor: mikrofon penceresi ve onaylanacak penceresi olmayan Erişilebilirlik — ilk yapıştırma ayar panosunu bir kez açar ve sonra başarısız olmaya devam eder; "yazıya çeviriyor ama hiçbir şey yapıştırmıyor" tam olarak budur. **İmzalama ve notarization yapılmadı**: bir Apple Developer kimliği ve kimlik bilgileri gerektiriyor; bu bir satın alma kararı (Q4) ve bir yapı makinesinin varsayılan olarak tutmaması gereken bir şey. İmzasız imaj kurulur, sonra Gatekeeper onu üretmeyen bir makinede reddeder; dokümanlar bunu söylüyor* |
| T5.6 ✅ | İşletim sistemi başına yazılı, elle doğrulama protokolü (kontrol listesi); böylece bir macOS/Windows iddiasının arkasında umut değil kanıt olur — *`docs/ai/MANUAL-CHECKS.md` (+ Türkçe eşi): on iki satır, her biri jest → beklenen gözlem → otomasyonun neden yapamadığı ve neyin yazılacağı. 1–10. satırlar Linux'ta dondurulmuş pakete karşı koşuldu; 3, 5, 7, 11 ve 12 masaüstü oturumu, mikrofon ya da bir paket istiyor ve bunu söylüyor* |
| T5.7 ✅ | macOS kod yollarının hiç değilse çalıştırılması için bir macOS CI koşucusu ekle — *zaten iki yerde var: `tests.yml`'in `test-macos` işi tam takımı 3.11–3.14'te koşuyor, `build.yml` de macOS'ta dondurulmuş paketi kurup başlatıyor. İki hüküm de push bekliyor* |

**Doğrulama:** her işletim sisteminden indirilen bir yapı açılır, kaydeder,
yazıya çevirir, yapıştırır ve kapanır; her koşu gözlemlendiği işletim sistemi ve
sürümüyle `docs/ai/VERIFICATION.md`'ye yazılır.

**T5.1'in ilk paketinden çıkan iki bulgu — ikisi de düzeltilecek ve ikisi de kayıtlı:**

- **N8 — ikinci başlatma, çalışan örneğin soketini çalıyordu.** `QLocalServer`, bir
  çökmeden kalan soketi temizlemek için `listen()`'den önce `removeServer()` ister; aynı
  ikili, adı **çalışan** bir örnekten de alır: ilk Dikte kaydetmeye devam eder ama
  erişilemez olur, terminal, kısayol ve tepsi komutlarının hepsi artık ikinciye gider.
  Kâğıt üzerinde paketlemeyle ilgisi yok — ta ki dondurulmuş paket bir masaüstü girdisine
  oturana kadar: orada çift tıklama tek bir jest. Artık önce `ipc.running_instance()`'a
  soruyor ve adı zaten tutan sürece `dashboard` iletiliyor. Dondurulmuş pakette uçtan uca
  kanıtlandı: ikinci başlatma "already running" ile 0 koduyla çıkıyor, birinci canlı
  kalıyor, soketi değişmiyor ve `/tmp`'deki gerçek örneğin soketine dokunulmuyor.
- **N9 — dondurulmuş uygulamanın stdout'u bir boruya ulaşmıyor.** Açılış satırı
  ("no system tray found, running anyway") blok arabellekte kaldı ve `PYTHONUNBUFFERED=1`
  bunu değiştirmedi; yani borudan okuyan bir kontrol, ancak süreç çıkarken gelen bir satırı
  bekledi. Önemi kontrolün ötesinde: paket, terminali olmayan bir masaüstü girdisinden
  başlatılıyor, dolayısıyla **uygulamanın başarısızlıkta bastığı her şey kullanıcının
  bakabileceği bir yere gitmiyor**. *13.09.2026'da cevaplandı:* `dikte.keep_a_log()`,
  **terminal yokken** stdout ve stderr'i `DATA_DIR/dikte.log`'a çift yazıyor (tek dosya,
  1 MB'ı geçince baştan başlar) — "dondurulmuşsa" değil, çünkü `install.sh`'in masaüstü
  girdisi kaynak bir depoyu aynı sorunla çalıştırıyor — ve `dikte doctor` yolu bildiriyor,
  böylece bulunabiliyor. Dondurulmuş pakette, stdout ve stderr `/dev/null`'a giderken
  (tam bir masaüstü girdisi gibi) kanıtlandı: günlük iki satırla birlikte belirdi. Çift
  yazıcı hem akışa hem dosyaya yazıyor, yani terminalden başlatan kişi eskiden gördüğünü
  görmeye devam ediyor.

### Faz 6 — Ürün derinliği (isteğe bağlı, sıralı)

Yalnızca Faz 5'ten sonra. Değere göre sıralı:

1. **İlk çalıştırma deneyimi — indi.** `ui/welcome.py`: üç adım (mikrofon → motor →
   gerçek şey); ilk açılışta, panodaki **Kur** düğmesinden ve `dikte setup` ile erişilebilir.
   Model indirmeyi yeniden yazmak yerine ayarlar sayfasının indirme kutusunu kullanıyor ve
   motoru kendi başına değiştirmiyor — motor adımının bunun için bir düğmesi var, çünkü
   yazıya çeviriciyi sessizce diskte bulunan modeli işaret etmek, ilk çalıştırmayı sonradan
   bir muammaya dönüştürmenin yoludur. Mikrofon adımı, diktenin kullandığı kaydediciyle iki
   buçuk saniye kaydedip tepe seviyeyi bildiriyor; mikrofonu olmayan makineye ölü bir düğme
   gösterilmiyor, durum söyleniyor. Üçüncü adım bir dikteyi **taklit etmiyor**: gerçeğini
   geçmişte bekliyor ve 90 saniye sonra üç olası nedeni sayıyor (hangisi olduğunu
   `dikte doctor` söylüyor). 17 test; her başarısızlık yolu bir şey söylüyor — modül kayda
   hiç sessiz handler eklemiyor. *Kalan: hiçbir macOS ya da Windows koşusu onu görmedi ve
   README turunda bir karesi yok.*
2. **Teşhis paketi — indi.** `dikte doctor --bundle dikte-diagnostics.zip`, bir hata
   raporunun ihtiyacı olanı tek arşive yazıyor: doctor raporu, ortam (platform, Python,
   dondurulmuş mu, Wayland mı X11 mi, dizinler), *adı* key/token/secret diyen her değerin
   maskelendiği ayarlar, ne kadar dikte alındığının sayısı ve günlüğün sonu. Üç söz, her biri
   bir test: hiçbir gizli değer sağ kalmıyor (adla maskeleniyor **ve** gerçek değerlere karşı
   değerce temizleniyor — anahtarı yankılamış bir günlük satırı `***` olarak çıkıyor), ses ve
   transkript metni yok (geçmiş sayılıyor, kopyalanmıyor) ve arşivin kendi `README.txt`'i
   ikisini de yazıyor, böylece gönderen kişi güvenmek yerine kontrol edebiliyor. Kum havuzunda
   gerçek CLI üzerinden uçtan uca doğrulandı (`tests/test_diagnostics.py`, 9 test).
3. `sherpa-onnx` akışlı ara sonuçları, isteğe bağlı ikinci yerel motor olarak (§3.4) —
   **karar bekliyor**: yeni bir üçüncü taraf bağımlılık ve `AGENTS.md` bunu kullanıcının
   kararı sayıyor.
4. Toplantılar için kanal ayrımının ötesinde konuşmacı ayrıştırma kalitesi.

## 6. Doğrulama sözleşmesi

Her faz için pazarlıksız, `ai/workflows.md`'den devralınmış:

- Yeni korkuluk, düzeltmeden önce **kırmızı**, sonrasında **yeşil** olduğu
  kanıtlanır. Hiç kırmızı olmamış bir korkuluk kanıt değildir.
- Hedefli modüller → tam takım → `git diff --check`.
- Her faz gerçek komut çıktısını `docs/ai/VERIFICATION.md`'ye yazar.
  Tahmini PASS yok.
- **Sessiz bir başarısızlık, adlandırılana kadar kusurdur.** `except Exception: pass` yalnızca
  gerekçesi koddan türetilebiliyorsa ya da yanına yazılmışsa kabul edilir; dört sürekli
  korkulak şunlardır: `except` mandalı (`tests/test_except_ratchet.py` +
  `tools/except_audit.py`), i18n açık kümesi (`tools/i18n_gaps.py`), yüzey turu
  (`tools/shoot_ui.py --check`) ve Qt API sözleşmesi (`tests/test_qt_api_contract.py` —
  ürünün andığı her `Qt.<ad>` ve her `Q<Sınıf>.<ad>` koştuğu PyQt6'da var olmalı, takma adlı
  import'lar dahil; `Qt.UniqueConnection`'ı yakalayacak olan korkulak, ki o hata
  `settings_ui`'ye hiç çalışmamış bir kaydedilmemiş-değişiklik korumasına mal oldu). Aynı
  ilke ayarlara da uzanıyor: `Config.__getitem__` bulamadığı anahtarı sessizce `None`
  döndürmek yerine adıyla söylüyor — ürün genelinde 96 literal anahtar okunuyor ve hepsi
  tanımlı, yani o satır bir sonraki yazım hatası için tuzak olarak duruyor.
- Ekran turu yeniden alınır ve incelenir; varsayılmaz.
  - İki README sekiz kare gömüyor — ayar penceresinin sayfaları ve ilk-kurulum
    sihirbazı — ve bunlar **üretiliyor, elle yapılmıyor**:
    `python3.14 tools/shoot_ui.py --readme` onları sevk edilen yapıdan
    `docs/settings-*.webp` ve `docs/setup.webp` içine yeniden çekiyor (koyu, İngilizce,
    1475x1489). Yeniden
    koşmak her arayüz değişikliğinin parçası ve kareler commit edilmeden önce gözle
    incelenir — `--check` bir yüzeyin *çizildiğini* sorar, oysa bir sayfa kusursuz
    çizilip yanlış bir şey söyleyebilir (13.09.2026: API sayfası tek bir model dosyası
    hakkında üç farklı cevap veriyordu ve bunu yalnızca kareyi okumak yakaladı).
- Faz tamam sayılmadan önce grafik tazelenir.
- §7/Q3 açık kararı olmadan yeni üçüncü taraf bağımlılık yok.

## 7. Kararlar

2026-09-12'de kaydedildi. Açık kalan her şey, ona bağlı olan fazı bloke ediyor.

| # | Soru | Cevap |
|---|---|---|
| **Q1 ✅** | **Lisans niyeti**: GPL-3.0'da mı kalınacak (PyQt6 kalır) yoksa GPL dışı bir yapı seçeneği mi korunacak (PySide6'ya geçilir)? | **13.09.2026'da cevaplandı — GPL-3.0-only, PyQt6 kalıyor.** Yanlış olan lisans değil üst veriydi; PySide6 yolu, projenin memnun olduğu copyleft sonucuna karşı kazanılmamış bir göç olarak reddedildi. **T5.5 açıldı**: imzalı ikililer GPL-3.0 yapıları olarak dağıtılır ve §6'daki kaynak yükümlülüğünü taşır. |
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
| `pyproject.toml` | `requires-python` → `>=3.11,<3.15`; lisans `GPL-3.0-only` olarak düzeltildi, yani deponun geri kalanının baştan beri söylediği şey (Q1 cevaplandı) |
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

### 2026-09-12 — Faz 1 uygulandı

Dokunulan dosyalar (9 değişti, 1 eklendi):

| Dosya | Değişiklik |
|---|---|
| `i18n.py` | tarihli bir blokta 105 girdi eklendi; `"Runs on"` yeniden etiketlendi; beş ölü girdi silindi |
| `ui/format.py` | yeni — `decimal_separator`, `number`, `seconds`, `when` |
| `meeting.py` | `format_when` artık saniye taşıyan damgaları da okuyor; geçmiş satırları ve toplantı satırları tek uygulamayı paylaşıyor |
| `settings_ui.py` | geçmiş listesi ve geçmiş detay penceresi `ui/format` üzerinden geçiyor; gösterge sayfasının adı `"Indicator"` |
| `ui/pages/dashboard.py` | alt başlık yeniden İngilizce (bkz. L9); süreler ve damgalar biçimlendirildi; `t("—")` sarmalı kaldırıldı |
| `ui/pages/overlay.py` | sayfa başlığı `"Indicator"` olarak yeniden adlandırıldı |
| `ui/shell.py` | sürüm numarası `"Sürüm"` tooltip'i taşıyor |
| `tests/test_i18n.py` | yeni korkuluk: bir kaynak metin Türkçe harf içeremez |
| `tests/i18n_untranslated.json` | kayıt artık boş |

Ham sonuçlar:

```
$ python3.14 tools/i18n_gaps.py
0 strings reach t() with no Turkish entry:

$ python3.14 tools/shoot_ui.py --out /tmp/dikte-p1 --themes blue --langs tr,en --check
wrote 60 PNGs to /tmp/dikte-p1
surface check OK: 30 surfaces x 2 theme-and-language runs, all drawn
```

Kırmızı kanıt, düzeltme inmeden önce:

```
$ python3.14 -m unittest tests.test_i18n.Table.test_no_source_string_is_already_turkish
AssertionError: Lists differ: [] != ['Genel bakış — son dikte ve toplantılarınız']
```

Korkuluk ilk tam koşusunda hakkını verdi: takım `1478 tests, FAILED (failures=1)`
döndü, çünkü tabloda o Türkçe anahtarın *ikinci* bir kopyası vardı — Türkçe metni
kendine eşleyen ve taramadan çok önce orada olan bir kopya. Yalnızca çağrı yerini
düzeltmek onu bırakırdı. Bir kerelik temizlik yerine korkuluk yazmanın bütün
gerekçesi bu.

Faz sonrası tam takım: `Ran 1478 tests in 90.237s — OK` (önce 1473).

Yeniden çekilen Türkçe karelerden okundu, varsayılmadı:

```
geçmiş satırı     21 Ağu 2026 12:05 (2,0 sn)      öncesi  2026-08-21 12:05:00 (2.0 sn)
panel kartı       3,2 sn ort.  ·  10 dk           öncesi  3.2s avg  ·  10 min
kenar çubuğu      whisper-1 · Yerel · ● Hazır     öncesi  whisper-1 · Local · ● Ready
menü öğesi        Gösterge                        öncesi  Overlay/Indicator
```

O karelerde hâlâ görünen her İngilizce metin arayüz değil veri: `whisper-1` (bir
model kimliği), `openai` / `ask` (halka grafiğin lejantındaki sağlayıcı
kimlikleri) ve fixture'ın kendi `Shot meeting` ile `What is the capital of
Turkey?` metinleri.

### 2026-09-12 — Faz 2, ilk teslim (T2.1, T2.2, T2.3'ün renk yarısı)

| Dosya | Değişiklik |
|---|---|
| `ui/tokens.py` | yeniden yazıldı: sıcak-taş `LIGHT` ve sıcak-kömür `DARK`, `THEMES = {light, dark}`, `DEFAULT_THEME`, `RETIRED_THEMES` ve paletin iddialarını denetlenebilir kılmak için `mix` / `relative_luminance` / `contrast_ratio` |
| `ui/qss.py` | iki gömülü renk gitti (dolgulu düğmelerde `#FFF8F5`, tan çipte `#8A6A14`); `mix` artık `ui/tokens`'tan geliyor |
| `ui/theme.py` | altı oda dışa aktarımı kaldırıldı; `toggle()` iki tema arasında geçiyor |
| `ui/pages/general.py` | seçici açık ve koyu sunuyor; daire kenarı ve seçim halkası paletin mürekkebinden |
| `config.py`, `settings_ui.py`, `dikte.py`, `ui/shell.py` | varsayılan tema `blue` → `dark`, böylece yeni kurulum kilitli yönü alıyor |
| `settings_ui.py` | Kaydet düğmesi artık bir `primary`: stilsizdi, yani hiçbir sayfada birincil eylem yoktu |
| `tools/shoot_ui.py`, `.github/workflows/tests.yml` | tur `light,dark` koşuyor ve sunduğu temayı yapılandırmaya söylüyor |
| `tests/test_theme.py` | sözleşmeye genişletildi: erişilebilirlik, katman sırası, her metin eşleşmesi, motorda çıplak renk yok, dolgulu düğme mürekkep |

Turun ham sonucu — dosya adından değil pikselden okundu:

```
light_tr_page01.png  sha=4d78bde6b7f4  [('#fbfaf6', 37952), ('#f4f1ea', 20645), ('#eee9de', 14204)]
dark_tr_page01.png   sha=f34094f439e7  [('#232019', 35341), ('#1c1a17', 20645), ('#171512', 14204)]
light_tr_page03.png  sha=b8ce7847213e  [('#f4f1ea', 24996), ('#fbfaf6', 17883), ('#eee9de', 14281)]
dark_tr_page03.png   sha=a22a6b35fb0e  [('#1c1a17', 24996), ('#232019', 16135), ('#171512', 14281)]
```

Zemin ve kenar çubuğu piksel sayıları iki temada birebir aynı (20645 / 14204) —
tek düzen, iki palet; renk sözleşmesinin vaat ettiği özellik tam da bu. Ölçülen
palet artık tasarım referansının tarif ettiği palet ve iki tema adıyla değil
SHA'sıyla ayrışıyor.

### 2026-09-12 — Faz 2, ikinci teslim (T2.4 ve paletin yeniden çözülmesi)

| Dosya | Değişiklik |
|---|---|
| `ui/tokens.py` | sıcaklığın ve düzlemlerin gerçekten okunması için palet derinleştirildi; `CONTROL` / `CONTROL_PAD` / `ROW_HEIGHT` / `ROW_PAD` / `CELL` / `INDICATOR`; `CHIP_TINT` / `NOTE_TINT` / `SAGE_CHIP_TINT` |
| `ui/qss.py` | her kontrol yüksekliği ritimden; çip ve not tonları token'lardan; çıplak renk kalmadı |
| `ui/widgets.py`, `ui/components.py` | elle yazılmış beş düğme yüksekliği artık `CONTROL` okuyor |
| `ui/shell.py` | motor kartı bir `QFrame`, böylece `QFrame#card` onu gerçekten biçimlendiriyor |
| `ui/pages/cleanup.py`, `i18n.py` | sayfa alt başlığı sekmenin yardım metnini artık tekrarlamıyor |
| `tests/test_style_contracts.py` | **yeni**: objectName/stil eşleşmesi, muafiyet listeleri ve kontrol ritmi |
| `tests/test_theme.py` | katman başına hedef, arka plan kümesine surface2 ve field, çizgi görünürlüğü, çip ve not tonları |

Saklanmaya değer iki ölçüm:

```
kenar çubuğundaki motor kartı yüzeyi     önce: 0 px        sonra: 19 371 px
tur, light vs dark, aynı yüzey           önce: aynı sha=4d78bde6b7f4
                                         sonra: light 4d78bde6…  dark f34094f4…
```

En net olan kart. "Durum satırı çok soluk" iki palet revizyonu boyunca bir kontrast
sorunu olarak ele alındı ve hiçbir palet bunu çözemez, çünkü ortada kart yoktu:
widget düz bir `QWidget` olarak kuruluyordu, sheet ise kartları `QFrame#card` diye
biçimlendiriyor — Qt hiçbir şeyle eşleştirmedi ve hiçbir şey çizmedi. Yazı soluk
değildi, çıplak kenar çubuğunun üstünde oturuyordu.

### 2026-09-12 — Faz 2, üçüncü teslim (T2.5, T2.6 ve odak halkası)

| Dosya | Değişiklik |
|---|---|
| `ui/pages/agent.py`, `ui/pages/meeting.py` | `Reset to default` ikincildi; referans Reset'i ghost örneği olarak adlandırıyor |
| `ui/local_models.py` | indirilmiş bir modeli silen `Delete` ghost'tu — onaylı yıkıcı bir eylemde yer imi ağırlığı |
| `ui/pages/history.py`, `ui/pages/minutes.py` | yıkıcı düğmeler boşluktan sonraya taşındı ve iki sayfa sıralamada anlaşıyor |
| `ui/pages/cleanup.py` | elle kurulmuş gate yerine paylaşılan `ui.widgets.gate()` |
| `ui/qss.py` | her düğme değişkeninden sonra tek bir odak kuralı; devre dışı sekme grubu soluklaşıyor |
| `tools/shoot_ui.py` | her ayar sayfası, üst 700 px'i yerine tam olarak fotoğraflanıyor |
| `tests/test_style_contracts.py` | üç sözleşme daha: yıkıcı yerleşimi, odağın korunması, ritim (evvelki teslimden) |

Okunan değil ölçülen:

```
Geçmiş sayfası, tur düzeltmesinden önce  silme satırı hiçbir karede yoktu
sonra                                   101 px yıkıcı-kırmızı metin, aynı satırdaki
                                        son güvenli eylemden 250 px uzakta
prompt alanı, anahtar kapalı            arka plan surface2 (#f2ede1) = devre dışı
                                        (açık alan rengi #f7f3e9)
```

### 2026-09-12 — Faz 3, yüzey 1 (kayıt pili)

| Dosya | Değişiklik |
|---|---|
| `overlay.py` | pilin her etkileşimli bölgesi bir tooltip ve erişilebilir açıklama kazandı, widget'ın kendisi de bir ad; adlandırma tek yerde, imlecin üzerinde olduğu şeye göre yapılıyor |
| `i18n.py` | `"Recording indicator"` → `"Kayıt göstergesi"` — i18n korkuluğu yeni metni takımdan önce yakaladı; tam da bunun için var |
| `tests/test_overlay_refinement.py` | bir `RegionNames` sözleşmesi: her bölge adlı, boş durum bayat kalmak yerine temizliyor, duraklatılmışken Duraklat düğmesi Devam diyor, ve kaynakta bölge adı olmadan beliren yeni bir `_hover_*` bayrağı takımı kırmızı yapıyor |

Yeşilden önce kırmızı kanıtlandı: adlandırma yalnızca toplantı hâline döndürülünce
sözleşme boşluğu adıyla söylüyor — `the expand region has no name`, `the live region
has no name`, `the meeting region has no name`.

### 2026-09-12 — Faz 3, yüzey 2 (canlı kart)

| Dosya | Değişiklik |
|---|---|
| `ui/live_popup.py` | kart metni kadar uzun, `MIN_HEIGHT` ile kompakt tavan arasında; genişletilmiş hâl boy zorlamak yerine tavanı yükseltiyor; çevre yüksekliği sayılmıyor ölçülüyor; ok, pasif rengini Qt'nin gerçekten okuyacağı yerden alıyor |
| `tests/test_live_popup.py` | boyutlanma sözleşmesi: üç satır kartı doldurmuyor, kart metinle büyüyor, kompakt kart tavanda durup kaydırıyor, ok yalnızca gösterecek bir şey varken sunuluyor, tavanın altındaki bir kart hiç kaydırmıyor, boş durum var, pasif ok farklı renkte |
| `tools/shoot_ui.py` | canlı popup beslenmeden önce gösteriliyor (kendini boyutlandırıyor ve gizli bir popup'ın ölçecek viewport'u yok); genişletilmiş kare, durumun anlam taşıması için yeterince uzun bir transkript taşıyor |

Kareler üzerinde ölçülen:

```
canlı kart, üç satır   önce  460x260, tek satır görünüyor, gerisi ölü
                       sonra 460x124, üç satırın hepsi, kaydırma çubuğu yok
canlı kart, genişletilmiş  önce  460x260, aynı üç satır
                           sonra 460x460, 24 satır (fixture'ın artık metni var)
pasif genişletme oku          #585953 (fg3); eskiden fg ile çiziliyordu
ok pasif / etkin              üç satırda etkin değil (gösterecek bir şey yok)
```

### 2026-09-12 — Faz 3, yüzey 3 (düşünme paneli)

| Dosya | Değişiklik |
|---|---|
| `ui/thinking.py` | hareket göstergesi artık her tick'te yeniden boyanan boş bir 14×14 QLabel değil, paletten kendi yayını çizen bir widget; on iki kullanıcı-görünür dizi `t()` üzerinden geçiyor; spinner'a koşunun duraklatıldığı söyleniyor |
| `tests/test_thinking.py` | yeni. Gösterge (çiziyor, dönüyor, duraklatılmış olan duruyor, panelin kendi tick'i onu döndürüyor) ve dil (her etiket dille değişiyor, duraklatılmış panel de çevrili, varsayılan aşama çevrili) |
| `tests/test_style_contracts.py` | `Spinner` `SELF_PAINTED`'a katıldı — sheet'in onun için kuralı yok, çünkü kendi yayını çiziyor |
| `tools/shoot_ui.py` | panele aşaması, boru hattının yaptığı gibi `t()` üzerinden veriliyor; Türkçe kare artık İngilizce aşama metni göstermiyor |

U11, iddia iddia:

| U11 iddiası | Karar |
|---|---|
| "metni 'Temizleniyor…' derken hiç hareket göstergesi yok" | **Doğru ve daha kötüsü**: gösterge çıplak bir `QLabel`'dı — 14×14, boş, 33 ms'de bir `update()` ediliyor, hiçbir şey çizilmiyordu |
| "aynı üründen gelmiyor — farklı yarıçaplar, yazı boyutları" | **Desteklenemez.** `docs/design-reference.md` bir ayarlar referansı ve gösterge hakkında hiçbir şey söylemiyor; 72 px'lik bir pil ile 380 px'lik bir panelin yazıyı *farklı* boyutlandırması gerekir. Daha dar ve savunulabilir olan: pilin 24 px köşesi token'ların dört yarıçapından (4/6/8/12) biri değil — ölçek onu kapsamıyor. Kaydedildi, değiştirilmedi |

Kontrol ederken bulunan, ikisi de bildirilmemiş iki kusur:

- **Panelin hiç i18n'i yoktu.** `ui/thinking.py` `t`'yi hiç import etmiyordu, yani İngilizce
  arayüz "Dusunuyor…" ve altında "Duraklat / Durdur / Kapat" gösteriyordu — her dilde,
  ASCII'ye katlanmış Türkçe. Düzeltildi; doğru yazım da beraberinde geldi.
- **N7 — paneli göstermek arayüz dilini sıfırlıyor.** `_reposition()` tek bir değer okumak
  için `cfg.Config` kuruyor ve `Config.__init__` kayıtlı `ui_language`'ı tüm sürece yeniden
  uyguluyor. Çalışan uygulamada ikisi aynı olduğu için zararsız; bir test dili kaydetmeden
  ayarlayana kadar görünmez kaldı: panel göründüğü anda dil geri döndü. Düzeltilmedi —
  `Config`'ten bir yan etkiyi kaldırmak onun bütün çağıranlarına ulaşır.

Tur da panele artık İngilizce aşama literali vermiyor, böylece Türkçe kare bir Türkçe
kullanıcının gördüğünü gösteriyor.

### 2026-09-12 — Faz 3, yüzey 4 (tepsi menüsü)

| Dosya | Değişiklik |
|---|---|
| `dikte.py` | `ask_tray_state(state, agent)` — ajanın mikrofonu tuttuğu sırada tepsi için (ikon, tooltip) seçimi. İki tooltip de sabit bir ajan yerine yapılandırılmış olanı adıyla söylüyor |
| `i18n.py` | `"Dikte: recording for {name}"` ve `"Dikte: talking to {name}"`, kaynak dizisine "Claude" gömülü iki girdinin yerini aldı |
| `tests/test_tray_menu.py` | tooltip yapılandırılmış olanı adıyla söylüyor (beş sağlayıcı), duraklatılmış ajan duraklatıldığını söylüyor, çalışan ajan çalışma ikonunu taşıyor, iki durum aynı ipucunu paylaşmıyor ve tooltipler ad korunarak çevriliyor |

Bu dosya, menünün kendi içeriği için daha önce hiç teste sahip değildi — `tests/test_tray_menu.py`
toplantı zaman damgalarını ve ipucu boyamasını kapsıyordu, menüyü değil.

U12, iddia iddia:

| U12 iddiası | Karar |
|---|---|
| ikonlar | 11 aksiyon, her birine bir ikon verilmiş; `tests/test_icon_contracts.py` ikon setinde olmayan bir adda zaten kırmızı oluyor |
| ayırıcılar | 4 tane; menüyü dikte / toplantılar / ayarlar+yeniden başlat / çık olarak grupluyor |
| açık/kapalı durumu | var ve katmanlı: etiket ("Start recording" → "Stop and transcribe" → "Working…"), ikon vurgusu (kaydederken yeşil kayıt noktası, ajan çalışırken kırmızı durdur, kayıp gidecek bir kayıt varken kırmızı çöp) ve tooltip. PAUSED bilerek RECORDING etiketini paylaşıyor — `dikte.py` duraklatmanın overlay'in düğmesi olduğunu ve ana anahtarın durdur olarak kaldığını söylüyor — yani menü ikisini ayırmıyor, tooltip ayırıyor. Kontrol edildi, dokunulmadı |
| **kimsenin bildirmediği kusur** | iki soru tooltip'i **sabit** bir ajan söylüyordu: "Dikte: recording for Claude", "Dikte: talking to Claude"; bu, doğrusunu zaten hesaplamış ve üstte aksiyon etiketlerinde kullanılan bir `agent = assistant.display_name(self.conf)`'un iki satır altındaydı. Codex, Antigravity ya da yerel model kullanıcısına mikrofonu yanlış programın tuttuğu söyleniyordu. Türkçe girdiler adı sessizce bırakmıştı — "Dikte: ajan için kaydediyor" — ipucu da bu |

Doğrulanamayan: menünün masaüstü tepsisinde çizildiği hali. Turda tepsi yok ve
`QSystemTrayIcon`'un offscreen'de bağlanacağı bir şey yok; yani menünün boyaması ile
içeriği ayrı ayrı kapsanıyor ama hiç birlikte değil.

### 2026-09-12 — Faz 3, yüzey 5 (boş durumlar)

| Dosya | Değişiklik |
|---|---|
| `settings_ui.py` | `_load_voice_jobs`, kurtarılabilir bir iş yokken kurtarma kartını gizliyor — eskiden her durumda çiziliyordu: Geçmiş sayfasının en iyi yerinde boş bir liste kutusu ve ölü bir Yeniden dene düğmesi |
| `ui/pages/overlay.py` | Gösterge sayfasının boş durumu, başlığın altında altı boş bir boşluk bırakmak yerine iki stretch arasında duruyor |
| `tools/shoot_ui.py` | bir retryable ses işi serpiliyor, böylece kurtarma kartı yalnızca boş bir kutu olarak değil dolu ve etkin hâliyle fotoğraflanıyor |
| `tests/test_empty_states.py` | yeni. Kart iş yokken gizleniyor, retryable bir işle görünüyor, tamamlanmış bir iş için gizli kalıyor; boş durumun üstünde ve altında boşluk var ve sayfa söylediğini söylemeye devam ediyor |

U4, iddia iddia:

| U4 iddiası | Karar |
|---|---|
| "Geçmiş'teki 'kurtarılabilir' kartı büyük boş bir kutu" | **Doğru ve daha kötüsü.** Kart, boş kalması tesadüf olan bir kutu değildi; *her* durumda çizilen, yani her zaman kurtarılacak bir şey olduğunu iddia eden bir karttı. Düzeltildi. Turda başarısız bir iş serpili olmadığı için her karede boş görünüyordu ve bulgu bu yüzden bir boyut sorunu olarak kaydedilmişti |
| "kontrol panelinin boş grafik kartı tam kart yüksekliğinde" | **Desteklenemez.** İki grafik kartı bir satırı paylaşıyor ve sağdaki gerçek bir donut taşıyor, yani satırın yüksekliği içinde içerik olan bir şeyden geliyor; boş kart da kendi "Henüz veri yok"unu ortalıyor — U4'ün başka yerde istediği muamele |
| "Kaplama sayfası boş durumunu hiç ortalamıyor" | **Doğru.** `EmptyState` kendi içeriğini ortalıyor ama `EmptyState`'i ortalayan yoktu; sayfa sonuna bir stretch koyup onu yukarı itiyordu. Düzeltildi ve karede ortalanmış olarak ölçüldü |

Bilerek dokunulmayan: *dolu* bir kartın içindeki iş listesi sabit 110 px tavanını koruyor,
yani tek iş altında boşluk bırakıyor. Satırlar word-wrap yapıyor, dolayısıyla içeriğe göre
boyutlandırma satır başına `sizeHintForRow` gerektirir ve ilk yerleşim geçişinden önce
kurulduğunda kendini yanlış ölçer — canlı popup'ın ilk boyutlandırma denemesini kaydıran
arıza.

### 2026-09-12 — Faz 3, yüzey 6 (dokuz ayar sayfası)

| Dosya | Değişiklik |
|---|---|
| `settings_ui.py` | Kaydet artık footer satırında sıradan bir `btn(..., "primary")`; bir `QDialogButtonBox`'ın düğmesi değil, böylece iki footer düğmesi tek layout'tan geliyor |
| `ui/widgets.py` | `btn()` ve segment kontrolü yükseklik sabitlemeyi bıraktı: kontrol yüksekliklerini sheet bildiriyor ve `setFixedHeight(CONTROL[...])` ona karşı kaybeden ikinci bir bildirimdi |
| `ui/components.py` | H6'da not edilen ölü kopyadaki aynı sabitleme — o da düzeltildi, çünkü canlandırılmış bir kopya sheet'e aynı şekilde karşı koyardı |
| `tests/test_style_contracts.py` | `TheRhythmIsDeclaredOnce` yeni bir test kazandı: `test_the_sheet_is_the_only_place_a_control_height_is_fixed` — token da ikinci bir bildirimdir |

Dört iddia, kareden okunmak yerine ölçülerek:

| İddia | Karar |
|---|---|
| **U2** birincil/ikincil hiyerarşi yok | Yarısı Faz 2'de kapanmıştı (Kaydet `variant="primary"`). Footer'ı ölçmek kimsenin bildirmediği kusuru buldu: **Kaydet her sayfada Promptlar'ın 3–4 px altındaydı**. Kök neden: kontrol yüksekliği iki kez bildiriliyordu — `btn()` sabitliyordu, sheet ise `min-height` + dolgu bildiriyor ve 32 (md) / 26 (sm) sabitlemeye karşı 34 px'lik bir içerik minimumu oluşuyordu; sabitleme tartışmayı sessizce kaybediyor, iki düğme yüksekliğini farklı kurallardan alıyordu. Düzeltildi; pencerede ve karede önce/sonra ölçüldü |
| **U3** soluk katman ve pasif kontroller fazla silik | **Sayılarla desteklenemez.** Soluk katman kart üzerinde 6.06–6.67:1, pasif düğme 5.54–6.06:1, etkin düğme 12.67–13.26:1 — 2.2 kat ayrı ve ikisi de AA üstü. Faz 2'nin palet çalışması bunu zaten yanıtlamıştı |
| **U5** form kolonları kayıyor; kısayol satırı etiket kolonuna taşıyor | **Desteklenemez.** Kontroller tasarım gereği sağa hizalı: sağ kenarlar tek çizgiyi paylaşıyor (karede doğrulandı), sol kenarlar her kontrolün genişliğine göre değişiyor ve 80 px'lik "kayma" bir geniş combo ile iki dar kombo arasındaki fark. 976 px'lik "taşma" ise kaydırma çubuğu yokken sayfanın genişliği — o sayfadaki kartlar 712 değil 726 geniş |
| **U9** 5'li düzenleme seviyesi sıkışık | **Desteklenemez.** Her segment **132×34** |

Sabitleme T2.4'ten sağ çıkmıştı, çünkü o korkulak yalnızca *literal* yüksekliklerde kırmızı
oluyordu; token literal değil. Bu benim kaçırmamdı ve korkulak artık ne demek istediğini
söylüyor: bir kontrolün yüksekliğinin sabitlendiği tek yer sheet. Konteynerler kendi
yüksekliklerini sınırlayabilir (140 px'lik grafik, 110 px'lik liste) — kontrol konteyner
değildir, bu yüzden yalnızca `setFixedHeight` sayılıyor.

### 2026-09-12 — Faz 3, yüzey 7 (Wayland göstergesi) ve fazın kapanışı

| Dosya | Değişiklik |
|---|---|
| `paste.py` | kararı `indicator_platform()` veriyor, aynı oturumu okuyan `desktop()`'ın yanında: `XCB` (XWayland'li Wayland — belgelenen yol), `NATIVE` (X11, Windows, macOS) ve `UNPLACED` (XWayland'siz Wayland). Bilerek Qt'siz: `dikte.py` ona Qt yüklenmeden önce danışıyor |
| `dikte.py` | koşulun özel bir kopyasını tutmak yerine `paste.indicator_platform()`'a soruyor |
| `ui/pages/overlay.py` | Gösterge sayfası — köşenin seçildiği ve "burada ayarlayacağın bir şey yok" diyen sayfa — oturum `UNPLACED` olduğunda bunu söylüyor |
| `README.md`, `README.tr.md` | yalnızca XWayland yolu değil, yedek de belgeleniyor |
| `tests/test_paste.py` | üç cevap, iki işletim sistemi durumu, "her seferinde okunur" ve import anındaki davranış **kendi sürecinde** (test anında platform çoktan seçilmiş oluyor) |
| `tests/test_empty_states.py` | sayfa geçerli olduğunda söylüyor, olmadığında susuyor |

X2 ya native bir yol ya da belgelenmiş, test edilmiş bir yedek istiyordu. Native yol,
`AGENTS.md`'nin senin kararın olmadan izin vermediği üçüncü taraf bir modüle
(layer-shell) takılıyor; yani bu, yedek yarısı — ve gerçekte eksik olan yarısıydı:
sınır hiçbir yerde belgelenmiyordu ve uygulama hiçbir şey söylemiyordu.

```
wayland + DISPLAY      QT_QPA_PLATFORM=xcb    (XWayland pencereyi yerleştirebilir)
wayland, DISPLAY yok   QT_QPA_PLATFORM unset  (Qt başlar; besteci karar verir)
x11 / hiçbir şey demez QT_QPA_PLATFORM unset
```

### Faz 3 kapandı

Yedi yüzeyin hepsi. Fazın buldukları, tek yerde:

| Yüzey | Tarama ne dedi | Ölçüm ne buldu |
|---|---|---|
| 1 pil | 3 kusur | 1 gerçek (üç kontrolün **hiçbir biçimde adı yoktu**); sürükleme şikâyeti `i18n.py:887` ile çelişiyor — orası kullanıcıya göstergenin sürüklenemeyeceğini söylüyor |
| 2 canlı kart | 2 | 1 gerçek, 1 eskimiş — ve düzeltmek **kimsenin bildirmediği iki kusuru** çıkardı: kart kendi metninden bir satır kısaydı ve pasif ok etkin renkte çiziliyordu |
| 3 düşünme paneli | 2 | 1 doğru ve daha kötüsü (gösterge 33 ms'de bir yeniden boyanan boş bir QLabel'dı); diğeri desteklenemez. Dosyayı okumak **iki tane daha** buldu: panelin hiç i18n'i yoktu ve gösterilmesi arayüz dilini sıfırlıyordu (N7) |
| 4 tepsi menüsü | 3 | üçü de tuttu; kusur kimsenin bildirmediğiydi — iki tooltip **sabit** bir ajan adı söylüyordu |
| 5 boş durumlar | 3 | 2 gerçek (biri bildirilenden kötü), 1 desteklenemez |
| 6 ayar sayfaları | 4 | 1 gerçek ve bildirilmemiş (footer'da Kaydet Promptlar'ın 3–4 px altındaydı — iki kez bildirilen kontrol yüksekliği), 1 zaten Faz 2'de kapanmış, 2 desteklenemez |
| 7 Wayland | 1 | gerçek, ve eksik yarısı dürüst yedekti |

Deseni açıkça yazmakta fayda var, çünkü bütün faz boyunca geçerli oldu: **taramanın
*ekranda olan* hakkındaki iddiaları çoğunlukla iyiydi, *olmayan* hakkındaki iddiaları
çoğunlukla yanlıştı** — beşi (X3, `Promtlar`, U10'un sürükleme beklentisi, U6'nın boş
durumu, U11'in yarıçap karşılaştırması) dolu olan bir durumun ekran görüntüsünü
okumaktan geldi. Buna karşılık ölçümün ve dosyayı okumanın ortaya çıkardığı her kusuru
— adsız kontroller, eksik satır, pasif renk, boş spinner, eksik i18n, dil sıfırlaması,
sabit ajan adı, her durumda çizilen kurtarma kartı, ikiye katlanmış yükseklik
bildirimi — **kimse bildirmemişti.**

### 2026-09-12 — Faz 4, T4.9

**Tetikleyici var ve artık koşturularak test ediliyor.** Koordinatör geometriyi
sahipleniyor ama bir widget'ın kendi boyutunu değiştirdiğini göremez; bu yüzden her
overlay ailesi widget'ı kendi `_reposition()`'ını `coordinator.recompute_geometry()`
üzerinden geçiriyor — aynı üç satırın üç kopyası (`overlay.py`, `ui/live_popup.py`,
`ui/result_overlay.py`). Dördüncüsü unutursa komşusu eski konumunda kalır, kartlar üst
üste biner ve hiçbir şey hata vermez. Test, üç sınıfın her birine casus bir koordinatör
bağlayıp gerçek `_reposition()`'ı çağırıyor, sonra diğer yarıyı da kontrol ediyor:
bağlı bir widget kendini **yerleştirmemeli** (koordinatörle çekişen bir widget,
unutandan kötüdür) ve serbest bırakılan biri yeniden kendi yerleştirmelidir.

**`Config.data` okuma yarışı yeniden üretildi ve kaydetmeye mal oldu.** `save()` geçici
bir dosya yazıp atomik olarak yerine koyuyor, yani dosya hiç risk altında değildi —
ama `json.dump` `self.data`'yı saf Python kodlayıcıyla dolaşır (`indent` ile
çağrılıyor) ve bu dolaşma sırasında bir worker iş parçacığının tek anahtar eklemesi
`RuntimeError: dictionary changed size during iteration` veriyor. Kullanıcının az önce
değiştirdiği ayarlar o zaman hiç yazılmıyordu ve hata ona yalnızca "Could not save the
settings" olarak ulaşıyordu. Önce anlık görüntü alınarak düzeltildi; test yarışı
dolaşılırken büyüyen bir sözlükle deterministik olarak simüle ediyor, yani zamanlamaya
bağlı kalmak yerine her makinede aynı şeyi söylüyor. Kırmızı kanıt:

```
önce    RuntimeError: dictionary changed size during iteration
          File "json/encoder.py", line 361, in _iterencode_dict
sonra   ok   (ve geride hiç `.tmp` kalmıyor)
```

**Süreçler arası kilit kararı: kilit yok.** Yazarlar çalışan uygulama ve CLI, ve
böyle bırakılmasının gerekçesi:

- **Yazmalar zaten atomik** (geçici dosya + `os.replace`), yani bir kilit hâlihazırda
  bozuk olan hiçbir şeyi engellemez. Kilitlerin genelde arandığı arıza — yarım yazılmış
  bir config — burada olamaz.
- **Kilit, olabilen arızayı düzeltemez.** İki süreç de config'in tam bir bellek içi
  kopyasını tutuyor, yani risk bir *kayıp güncelleme*; yazmaları sıraya dizmek son
  yazanın kazanmasını aynen bırakır. Kayıp güncellemenin tek ilacı yazmadan önce
  okumaktır.
- **Bu ilaç iki yönde de zaten var.** Her CLI çağrısı diskten taze bir `Config()`
  kuruyor, ve CLI ardından `reload` gönderiyor ki çalışan uygulama yeniden okusun
  (`cli.py:585-588` bunu açıkça söylüyor: *"değiştirilmediği pencerenin onun üzerine
  yazacağı"*), `reload_settings` de `self.conf.load()` yapıyor.

Geriye kalan, saklanmak yerine adlandırılıyor: CLI, açık ayar penceresinin de gösterdiği
bir anahtarı değiştirdiğinde ve pencerede **kaydedilmemiş düzenlemeler** varsa, pencerenin
bir sonraki Kaydet'i kendi widget değerini CLI'ınkinin üzerine yazar. Yeniden yüklemede
pencerenin widget'larını tazelemek bunu düzeltirdi ve yanlış olurdu — kullanıcının
kaydedilmemiş düzenlemelerini sessizce atardı. Dürüst çözüm bir arayüz imkânı ("bu
ayarlar bu pencerenin dışında değişti"), ki bu bir güvenilirlik değil ürün kararı; bu
yüzden bir güvenilirlik görevinde icat edilmek yerine buraya kaydedildi.

### 2026-09-12 — Faz 4, T4.8 temizliği, iki dilim

İki dilim de veri yolundan dışa doğru alındı. Doğru sıra bu: bir yazma yolunda yutulan
başarısızlık kullanıcıya söylenmiş bir yalan, opsiyonel bir widget'ı yoklarken yutulan
başarısızlık ise eksik bir incelik. İkisinin değeri ayrı ve sıra bunu söylemeli.

**`config.py` — kilitler kilit, opsiyonel ek değil (293 → 291).** `_history_lock` ve
`_meetings_lock`, başarısız olduğunda onları `None` bırakan bir `try` içinde kuruluyordu
ve her yazma yeri o durum için **kendi gövdesinin kilitli olmayan ikinci bir kopyasını**
taşıyordu — sekiz yer, sekiz kopya gövde. `threading` çalışan bir yorumlayıcıdan eksik
olamaz; yani koruma hiçbir zaman yardımcı olamazdı. Yapabildiği şey güvenlik ağını
sessizce buharlaştırmak ve kilitli olmayan kopyanın test edilen kopyadan sapmasına izin
vermekti.

**Kontrol paneli — okunamayan geçmiş, boş geçmiş değildir.** `ui/stats.py`'deki dört
okuma-hatası handler'ının hepsi "satır yok"a düşüyordu, yani kartlar okunamayan bir
geçmiş için `0 dikte` basıyordu. Kartları besleyen ikisi artık `unreadable` diyor ve
kartlar, kullanıcının verisi hakkında bir olgu gibi okunan sıfır yerine `—` ve "geçmiş
okunamadı" gösteriyor. Grafiği ve sağlayıcı listesini besleyen ikisi bayrak taşıyamaz
(boş bir grafik, çubuğu olmayan grafiğin dürüst çizimidir; sayım haritasındaki
`unreadable` anahtarı "unreadable" adlı bir sağlayıcı olarak gelirdi), bu yüzden yalnız
terminale bildiriyorlar — bilinçli bir fark, yapıldığı yerde yazılı.

**Sayacın bir kör noktası vardı ve onu bulmak sonucun parçası.** `_reports` handler
gövdesinde yalnızca `print`/`warn` arıyordu, bu yüzden mesajını bir yardımcıya devreden
handler sessiz sayılıyordu — yukarıdaki yerlerin dördü zaten raporluyordu ve temizlik
dört yeri fazla ölçüyordu. Bu, statik i18n taramasının 182 yanlış pozitifiyle aynı
arıza: yalnızca yazıldığı şekli gören bir denetim. `_reports` artık modülün kendi
raporlama yardımcılarını çözüyor; araç test modülünün `silent_handlers()`'ını çağırdığı
için ikisi birlikte hareket etti ve sonrasındaki kayıt dürüst 286.

Sayıyı işten ayrı tutmak gerek: **293 → 291 işti, 291 → 286 hiç sessiz olmamış yerlerdi.**
Düzeltme, kayıt yeniden yazılmadan önce indi; yani bundan sonraki her fark, bir yardımcıyı
görebilen bir sayaca göre ölçülüyor.

**Hâlâ borçlu olunan, tam olarak şu.** Kalan 286, *şekille listeli ama yer başına
gerekçeyle değil*. Çoğu iki kalıba düşüyor — "opsiyonel widget'ı oku, yoksa yedeğe düş" ve
"varlığı zaten normal olan yerde elden geldiğince temizle" — ve satırı kapatmanın dürüst
yolu, her yerin atandığı küçük bir gözden geçirilmiş gerekçe kümesi; 286 elle yazılmış
yorum değil. O gelene kadar satır `◐` ve bu paragraf nedenini söylüyor.

### Bu belgede uygulama sırasında düzeltilenler

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

- **N1 — ekran görüntüsü turu, yakaladığı tema hakkında yalan söylüyordu.**
  `tools/shoot_ui.py` içindeki `theme.apply(thm)` uygulama stil sayfasını kuruyordu,
  ama ayar penceresi açılırken *kayıtlı* temayı uyguluyor (`settings_ui.py:558`), yani
  her kare yapılandırmanın varsayılanıyla çiziliyordu. Aracın varsayılanı
  (`blue,orange`) yapılandırmanın varsayılanıyla (`blue`) ilk girdiyi paylaştığı
  sürece görünmez kaldı: `orange` koşusu mavi çiziyordu ve bunu söyleyen hiçbir şey
  yoktu. Ancak varsayılan `dark`'a taşınınca ve "light" kareleri koyu çıkınca
  bulundu — sonra varsayılmadı, kanıtlandı: `light_tr_page01.png` ile
  `dark_tr_page01.png` bayt bayt aynıydı (ikisi de `sha=4d78bde6b7f4`) ve düzeltmeden
  sonra ayrıştılar. Turun yapılandırmasına sunduğu temayı vermekle düzeltildi.
  **Yüksek sesle başarısız olamayan bir doğrulama aracı, doğrulama değildir** — ve bu
  araç ömrü boyunca sessizce "geçiyordu".

- **N2 — terrakota düğme metnini taşıyamıyor.** `docs/design-reference.md` birincil
  eylemin "mürekkep kömürü, bg #242628, turuncu DEĞİL" olduğunu söylüyor ve bunun bir
  tercih değil bir kısıt olduğu çıktı: düğme etiketi açık temanın `accent`'inde
  3,51:1, koyu temanınkinde 2,58:1 ölçülüyor, ikisi de AA'nın altında; `accentDeep`
  ise eşiği ancak geçiyor (4,72 / 4,61) — dolgulu bir kontrol için harcanamayacak
  kadar yakın. Bu yüzden dolgulu düğme mürekkep (14,5 / 16,6:1) ve terrakota
  referansın söylediği şey: kayıt sinyali. Kayda değer iki sonuç: QSS, **hiçbir
  çağrı yerinin kullanmadığı** bir terrakota `variant="primary"` taşıyordu, yani
  stil vardı ve onu giyen yoktu; ve gerçek Kaydet düğmesi stilsizdi — U2'nin (buton
  hiyerarşisi yok) somut hâli bu, burada Kaydet'i birincil yaparak onarıldı.

- **N3 — hiçbir şeyle eşleşmeyen bir stil kuralı sessizce başarısız oluyor, üç
  biçimde.** Plan "sheet'in etkisi yok"u tek bir kusur sınıfı sayıyordu; işi
  yaparken üç biçimi çıktı ve her biri varsayılan görünümlü bir widget çizip hiçbir
  şey fırlatmıyor. (1) **Yanlış widget sınıfı:** kenar çubuğunun motor kartı bir
  `QWidget`'tı, sheet ise kartları `QFrame#card` diye biçimlendiriyor — kartın ne
  yüzeyi ne kenarlığı vardı; 0 px, düzeltmeyle 19 371 px. "Durum satırı çok soluk"
  iki palet revizyonu boyunca kontrast sorunu olarak ele alınmıştı; hiçbir palet
  olmayan bir kartı düzeltemez. `tests/test_style_contracts.py` artık her
  objectName'i hangi widget sınıfının aldığını ve ona bir kuralın ulaşıp
  ulaşmadığını soruyor. (2) **Kaskad sırası:** `ghost` ve `danger`,
  `border-color: transparent`'ı `QPushButton:focus`'un altında bildiriyor ve QSS
  eşit özgüllüğü belge sırasıyla çözüyor — o iki değişkenin hiç odak halkası yoktu.
  Değişken başına korkuluk altına alındı; o testin bariz versiyonu onlar bozukken
  geçiyor, çünkü `seg:focus` altlarında durup bütün aile adına cevap veriyor.
  (3) **Qt'nin desteklemediği bir seçici:** `QTabBar:disabled::tab` kabul ediliyor
  ve hiçbir şey yapmıyor; `QTabBar::tab:disabled` çalışıyor. İkisini ayıran tek şey
  ölçüm oldu. Ders şu: bir stil değişikliğinin yanına bir ölçüm iliştirilmeli,
  çünkü "iyi görünüyor" ile "kural hiç uygulanmadı" aynı şeye benziyor.

- **N4 — tur her sayfanın üstünü fotoğraflıyordu.** Her ayar sayfası bir kaydırma
  alanında yaşıyor ve çekim sabit 1000×700'dü; yani Geçmiş sayfasının silme satırı
  ile Tutanak sayfasının eylem satırı hiçbir koşunun hiçbir karesinde görünmedi. Bu
  küçük bir kör nokta değil: dört sayfanın alt yarısı demek, ve düğme hiyerarşisi
  işinin önce inançla yeniden sıralanıp ancak sonra kontrol edilebilmesinin sebebi.
  `tools/shoot_ui.py` artık her sayfayı ölçüp pencereyi ona göre büyütüyor — kendi
  yüksekliğinde 700 ile 2040 px arası — ve sıralama sonra kare üzerinde doğrulandı.

- **N5 — U10 büyük ölçüde eskimişti ve bir maddesi ürünün kendi belgesiyle
  çelişiyordu.** Tarama, kayıt pilinde dört kusur saymıştı; hepsi tasarım işinden
  önceki nesle ait `blue_tr_overlay_rec.png` karesinden yazılmış. Koda ve güncel bir
  kareye karşı yeniden kontrol edildi: zamanlayıcı kayıt bağlamını **taşıyor**
  (kırmızı nokta, eşaralıklı zamanlayıcı ve Duraklat/Durdur tek bir kontrol olarak
  okunuyor); Duraklat ile Durdur **sıkışık değil**, aralarında görünür bir boşluk
  olan ayrı daireler; ve "sürükleme tutamacı yok" ürünün karşı çıktığı bir davranışı
  istiyor — `i18n.py:887` kullanıcıya göstergenin "sürüklenemez" olduğunu söylüyor ve
  Ayarlar onu köşeye göre yerleştiriyor, yani bir tutamaç gönderilmiş metinle
  çelişirdi. Dördüncü iddia, "ortadaki glif etiketsiz ve düşük kontrastlı", yarı yarıya
  doğruydu ve önemli olan yarısı kontrast değildi: glif `fg3` ile 5.6:1'de çiziliyor
  ve hover'da parlıyor — bu bilinçli — ama **hiçbir biçimde adı yoktu**: ne tooltip,
  ne erişilebilir açıklama, ne de arayüzün herhangi bir yerinde görünür metin.
  Duraklat ve Durdur aynı durumdaydı. Bu artık düzeltildi ve korkuluk altında.
  **Üst üste üçüncü arayüz bulgusu güncel ürün hakkında büyük ölçüde yanlış**;
  taramanın ekran görüntüleri eski bir nesle ait ve bu plan kaynağa karşı yeniden
  kontrol edilmemiş hiçbir bulguya güvenmeyi bırakmalı.

- **N6 — U6 yarı yarıya doğruydu ve yanlış olan yarısı kayda değer bir sebepten
  yanlıştı.** "Canlı kart içeriğine göre boyutlanmıyor" tuttu: içinde üç satır olan
  260 px sabit kart. "Boş durumu yok" tutmadı — metin alanı yazıldığından beri bir
  placeholder taşıyor ve tarama, boş *görünen* bir kare olmadığı için boş durumun
  olmadığı sonucuna vardı; çünkü bakacak boş bir kart karesi yoktu. Mekanizma N5'le
  aynı: dolu olan bir durumun ekran görüntüsünden, neyin eksik olduğuna dair bir
  iddia. **Üst üste dört arayüz bulgusu artık kısmen ya da tamamen yanlış** ve
  hepsi bir ekran görüntüsünden. Boyutlandırmayı düzeltmek sonra *kimsenin
  bildirmediği* iki kusur buldu; ikisi de tam da kart sabit yükseklikte olduğu için
  görünmezdi: kart her zaman kendi metninden bir satır kısaydı (stil sayfasının
  metin alanlarına verdiği 8 px dolgu, kenar boşluklarından yapılan bir sayıma
  görünmez) ve pasif genişletme oku etkin renginde çiziliyordu (Qt bir
  QToolButton'ın metnini QStyleSheetStyle üzerinden çözdüğünde palet rengi oraya
  hiç ulaşmıyor). Ders N4'ün tersi: yanlış bir boy başka kusurları saklıyor, yani
  birini düzeltmek onun üzerinden çizilen her şeye yeniden bakmaya değer.

- **N7 — bir ayar değerini okumak, arayüz dilini tüm sürece yeniden uyguluyor.
  Düzeltildi (13.09.2026).** `Config.__init__` sonunda
  `i18n.set_language(self.data["ui_language"])` çağırıyor, yani bir `Config` *kurmak* okuma
  değil: global bir yan etki. `ThinkingPopup._reposition()` `overlay_corner`'a bakmak için
  bir tane kuruyordu. Bu not eskiden bunu "çalışan uygulamada zararsız, çünkü kayıtlı dil ile
  uygulanan dil zaten aynı" diye geçiştiriyordu; değil: ayar penceresi açıkken seçilmiş ama
  henüz kaydedilmemiş bir dil varken panelin görünmesi kayıtlı olanı geri koyuyor.
  Düzeltme `Config`'e dokunmuyor — yan etkisine bütün çağıranlar (testler ve CLI dahil)
  dayanıyor: panel, sürecin zaten tuttuğu `conf`'u alıyor ve köşeyi oradan okuyor.
  `tests/test_thinking.py`'de iki test: biri koruma için, diğeri onu gerekli kılan
  mekanizmayı çiviliyor — bir okuma dili uygulamayı bırakırsa ikincisi bunu söyler.

- **"`t()`'ye hiç ulaşmayan diziler" için statik bir denetim burada çalışmıyor ve ilk
  çıktısı 182 yanlış pozitifti.** Tepsi tooltipleri çevrilmemiş literal gibi görünüyordu ve
  değildi: çıkış noktası `self.tray.setToolTip(t(tip))`, yani `tip`'e atanan bir literal
  orada çevriliyor. Tarama 182 dizi işaretledi; hepsi gezinme etiketleri, sağlayıcı adları,
  köşe adları gibi **tablo girdileri** ve `t(<değişken>)` üzerinden ulaşılıyor — literal
  taraması bunu takip edemiyor. Kayda değer, çünkü cazibe hiç bozuk olmayan 182 diziyi
  "düzeltmek"ti; ve dürüst alternatif zaten var, maliyeti de az: yüzeyi iki dilde kur ve
  gösterdiğini etiket etiket karşılaştır. Düşünme panelinin çevrilmemiş literallerini
  yakalayan buydu ve tablo dolaylamasını, değişkene atamayı, statik taramanın göremediği
  her şeyi yakalıyor.

  Aynı tarama bir sonraki çıkışında ikinci kez yanıldı ve bu kez hata Türkçeye özgü:
  çevirilerde ASCII'ye katlanmış sözcükleri ararken 63 tane buldu — hepsi `re.IGNORECASE`
  yüzünden yanlış pozitif, çünkü onun altında Türkçe `ı` ile `i` aynı harfe katlanıyor ve
  `toplanti` deseni doğru yazılmış `Toplantı` ile eşleşiyor. İki yazımı da birebir eşlemek
  yerine **sıfır** buluyor; ve başladığım dizi (kareden "son 30 gun" diye okunan) tabloda
  `"son 30 gün"`. İki ders: Türkçe metin üzerinde bir tarama büyük/küçük harf duyarsız
  eşleme kullanmamalı, ve küçük bir çizimden okunan diakritik, diakritiğin eksik olduğunun
  kanıtı değil.

Faz 1 sırasında:

- **X3 büyük ölçüde yanlıştı** ve yanlışlığı taramanın kendi yönteminden
  geliyordu. Arayüzün her platformda `Meta+A` önerdiğini iddia ediyordu; kısayol
  alanı baştan beri listesini platforma göre seçiyor, iki varsayılan da boş ve
  KDE'ye özel metin koşullu. `Meta+A`, `tools/shoot_ui.py`'nin fixture sözlüğünden
  geliyordu; yani aracın kendisi bir ürün bulgusu uydurdu. Düzeltildi. Ders:
  bir ekran görüntüsü, *fixture'ın* ne çizdiğini kanıtlar, kullanıcının ne
  gördüğünü değil.
- **L5'in `Promtlar` yarısı yanlış okumaydı.** `Promtlar` depoda hiçbir yerde
  geçmiyor. Görüntü analizi `Promptlar`ı yanlış okudu ve tarama bunu bir kusur
  olarak tekrarladı. Düzeltildi.
- **T1.4'ün *prompt* alt maddesi yanlış bir öncüldü** — aynı sebeple: tablo
  baştan beri `Promptlar` diyordu. Hiçbir şey standartlaştırılmadı, çünkü hiçbir
  şey tutarsız değildi.
- **T1.6 incelemede buharlaştı** — bkz. X3.
- **Planın L1 çerçevelemesi doğruydu, sayısı düşüktü**: `_t` takma adı izlenince
  103 değil 104.

---

*2026-09-12'de `master @ ffe8a5c` üzerinde salt-okunur bir incelemeyle
başlandı; Faz 0, 1 ve 2 aynı gün uygulandı. İngilizce aslı:
[`ROADMAP.md`](ROADMAP.md).*
