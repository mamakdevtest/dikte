# ELLE KONTROLLER — bir kişinin işletim sistemi başına koştuğu protokol

Faz 5'in doğrulama satırı şöyle diyor: *her işletim sisteminden indirilen bir yapı açılır,
kaydeder, yazıya çevirir, yapıştırır ve kapanır; her koşu gözlemlendiği işletim sistemi ve
sürümüyle `VERIFICATION.md`'ye yazılır.* Bu dosya o kaydın nasıl üretileceğini ve değerli
olması için ne içermesi gerektiğini anlatıyor.

**Neden bir kişi, neden CI işi değil.** `packaging/build.py` paketin açıldığını,
içe aktarmaların çalıştığını, uygulamanın kendini teşhis ettiğini ve kendi soketinde
dinlediğini kanıtlıyor. Aşağıdaki her satır ise koşucularda olmayan donanım istiyor: bir
mikrofon, bir masaüstü oturumu, bir izin penceresi, yapıştırılacak başka bir uygulama ve
metnin yanlış pencereye düştüğünü fark edecek bir insan. Faz 5'in şu ana kadar çıkardığı üç
kusurun (N8'in soket hırsızlığı, N9'un görünmez çıktısı, T5.1'in `NameError`'ı) hepsi
*şeyi başlatmakla* bulundu; hiçbiri spec okunarak bulunmazdı.

## Bir koşu nasıl kaydedilir

`docs/ai/VERIFICATION.md`'ye işletim sistemi başına bir bölüm, şu biçimde:

    ## <İŞLETİM SİSTEMİ> <sürüm> — <yapı> (<commit>)
    Tarih, koşan kişi, yapının nereden geldiği (CI artefakt adı ya da onu kuran komut).
    Sonra aşağıdaki her satır için gözlem; "çalışıyor" değil.

Tek başına `✓` kayıt değildir. `✓ Kate'te Ctrl+Space "merhaba dünya" yazdırdı` kayıttır.
Bir adım başarısız olduysa, bastığı çıktıyla birlikte tabloda kalır — bu projenin kuralı
şu: sessizce kendini düzelten bir plan, nerede yanıldığını gösterenden daha kötüdür.

## Satırlar

| # | Jest | Beklenen | Otomasyon neden yapamaz |
|---|---|---|---|
| 1 | Yapıdan kur (depo yok, `pip install PyQt6` yok) | Uygulama açılır ve tepsi simgesi görünür | T5.1'in bütün amacı bu; `build.py` paketi geliştiricinin ortamında başlatıyor, ki bu aynı şey değil |
| 2 | Terminalden `dikte doctor` | Eksik her araç eksik olarak listelenir; çıkış kodu 0 | Dürüstçe bir şeyi eksik olan bir makine gerekir |
| 3 | İşletim sistemi sorunca mikrofona izin ver (macOS: TCC penceresi; Windows: Ayarlar → Gizlilik → Mikrofon) | İzinden *sonra* kayıt çalışır ve pencere Python'u değil Dikte'yi adlandırır | İzin, yorumlayıcıya değil paketin kimliğine ait (T5.5) |
| 4 | Erişilebilirlik izni ver (yalnız macOS, yapıştırma yolu için) | Dikte, Sistem Ayarları → Gizlilik → Erişilebilirlik'te görünür | Linux'ta böyle bir adım yok; eksik izin "yapıştırma hiçbir şey yapmıyor" gibi görünür |
| 5 | Başka bir uygulamadayken genel kısayola bas (Kate/Notepad/TextEdit'te başla) | Dikte'ye odaklanmadan kayıt başlar; ikinci basış o pencereye yapıştırır | İkinci bir uygulama ve bir pencere yöneticisi gerekir |
| 6 | Gerçek bir cümle dikte et | Metin odaklı pencereye düşer, ayarlara göre çevrilip temizlenmiş olarak | Mikrofon gerekir; testlerde yazıya çevirme yolu yalnızca taklit ediliyor |
| 7 | Toplantı başlat (macOS'ta BlackHole ya da Loopback gerekir) | Tutanak yazılır; toplantı Toplantılar listesinde görünür | Bir loopback ses aygıtı gerekir (T5.5'in notu) |
| 8 | Bir ayarı değiştir, çık, yeniden başlat; sonra terminalde `dikte config` | Ayar yerinde ve ikisi uyuşuyor | İki süreç, tek dosya (T4.9'un kilit kararı) |
| 9 | Uygulamayı iki kez başlat (çalışırken simgeye çift tıkla) | İkinci başlatma birincinin panosunu açar ve 0 ile çıkar | N8'in düzeltmesi Linux'ta kum havuzunda kanıtlandı; işletim sistemi başına değişen şey masaüstü girdisi yolu |
| 10 | Tepsiden yeniden başlat ve tepsiden çık | Dondurulmuş uygulama olarak geri gelir (Python betiği olarak değil); çıkış süreç bırakmaz | T5.1'e kadar pakette sessizce kırılan `launch_command` yolları |
| 11 | Yanlış API anahtarıyla bir arıza zorla, sonra mesajı ara | Mesaj, *bir kişinin bulabileceği* bir yerde: pencerede ve terminal yokken `DATA_DIR/dikte.log`'da | N9 cevaplandı: `dikte.keep_a_log()` çıktıyı o dosyaya çift yazıyor ve `dikte doctor` yolunu basıyor. Bu satırın kontrol ettiği şey otomasyonun yapamayacağı kısım: dosyanın, bir kişinin gerçekten bakmayı düşüneceği yer olup olmadığı |
| 12 | İşletim sisteminin kendi yoluyla kaldır (Windows: Ayarlar → Uygulamalar; Linux: paketi kaldır; macOS: Çöp'e sürükle) | Ne artık süreç kalır, ne artık başlangıç girdisi | Yalnızca işletim sisteminin kurucusu ne kurduğunu bilir |
| 13 | `~/.config/dikte/config.json`'ı sil, sonra uygulamayı başlat | İlk-kurulum sihirbazı çıkıyor; ikinci başlatmada bir daha görünmüyor; panodaki **Kur** düğmesi ve `dikte setup` onu geri getiriyor | Sihirbazın kendi adımları elle koşulacak kısım: 1. adım mikrofon istiyor, 3. adım gerçek bir dikteyi bekliyor, 2. adım bir model indiriyor — CI'da hiçbiri yok |

## Henüz cevap olmayan işletim sistemi notları

- **Linux**: 1–10. satırlar 13.09.2026'da dondurulmuş pakete karşı bir kum havuzunda
  koşuldu (`probe_double_start.py`, `packaging/build.py`); 3, 5, 7, 11, 12 ve 13 hariç — onlar
  masaüstü oturumu, mikrofon ya da bir paket istiyor. Gösterge sayfasının XWayland yedeği
  (X2) bir Wayland oturumu olduğunda buraya giren Linux'a özel bir satırdır.
- **macOS**: hiçbir şey koşulmadı. `.app` paketi spec ile kuruluyor ve içinde mikrofon
  kullanım metni var (`NSMicrophoneUsageDescription`), ama hiçbir izin penceresi
  görülmedi. İmzalama ve notarization başlamadı ve bir Apple Developer hesabı istiyor (Q4).
- **Windows**: hiçbir şey koşulmadı. T5.4 indi: `packaging/dikte.spec` `dikte.exe`'nin
  yanında konsolsuz bir `diktew.exe` ikizi üretiyor ve `install.ps1`, `dist\dikte\` içinde
  dondurulmuş bir paket varsa onu tercih ediyor (yorumlayıcı keşfini, sürüm kontrolünü ve
  PyQt6 kurulumunu tek blokta atlıyor), CI için `-NoLaunch` ile. Hiç koşulmamış olan
  kurucunun kendisi — geliştirme makinesinde `pwsh` yok, yani yukarıdaki satır onun ilk
  gerçek testi ve `build.yml`'in `windows-latest` adımı ilk otomatik olanı.

## Bu satırlar hiç koşulmazsa ne doğrulanmamış kalır

Yukarıdaki satırların tamamı — ve onlarla birlikte README'nin bir platform için verdiği her
söz. Bu dosyanın bir commit mesajındaki iddia yerine var olmasının sebebi tam olarak bu.
