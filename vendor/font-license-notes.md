# Font + ikon paketi — kaynak / sha256 / lisans notları

Tarih: 2026-09-03. Kapsam: SADECE yeni dosyalar (`assets/fonts/`, `vendor/font-license-notes.md`).
Mevcut hiçbir dosya değiştirilmedi (`docs/fonts/*`, `ui/icons.py`, `vendor/manifest.json` dahil).
Yürütülebilir kod yok — sadece `.ttf` + `.svg`. Toplam boyut: **1.032.677 bayt (~0,98 MB) < 5 MB** sınırı.

## 1. Fontlar (`assets/fonts/`)

Karar: **display = Space Grotesk**, **body = Inter**, **mono = JetBrainsMono (mevcut, korundu)**.
`google/fonts` reposunda artık statik Regular/Medium/SemiBold TTF yok — sadece variable
font var; aşağıdaki tek dosya ailenin TÜM ağırlıklarını (400/500/600 dahil) kapsar.
Değerlendirilen alternatifler: `Manrope[wght].ttf` (165.420 B), `InterTight[wght].ttf`
(581.588 B) — Space Grotesk hem en küçük hem Inter ile en belirgin display eşleşmesi.

| Dosya | Kaynak URL | Boyut | sha256 | Lisans |
|---|---|---|---|---|
| `assets/fonts/SpaceGrotesk-Variable.ttf` | https://raw.githubusercontent.com/google/fonts/main/ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf | 136676 | `acad6de1fc93436f5c0f1f4137751ef04f1aea3063e7036535970ffcfbd79f72` | OFL-1.1 |
| `assets/fonts/Inter-Variable.ttf` | https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf | 876576 | `29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031` | OFL-1.1 |

OFL metinleri: https://raw.githubusercontent.com/google/fonts/main/ofl/spacegrotesk/OFL.txt
ve `.../ofl/inter/OFL.txt` (SIL Open Font License 1.1). `docs/fonts/` içindeki mevcut
Inter statikleri (400/500/600/700) ve JetBrainsMono (400/500) aynen duruyor.

## 2. İkonlar — Dikte → Lucide eşleşmesi (`assets/fonts/icons/`, 56 SVG, 19.425 bayt)

Kaynak repo: https://github.com/lucide-icons/lucide (`icons/<ad>.svg`, `main` dalı, ISC).
`ui/icons.py` ICONS tablosundaki **56 anahtarın 56'sı** + `settings_ui.py` içindeki `pip`
karşılığı indirildi. `history` için upstream'de dosya YOK (aşağıya bak).

| Dikte anahtarı | Lucide dosyası | sha256 | Not |
|---|---|---|---|
| mic | mic.svg | `9b940cd735d1ffa270ba670c4e677d9a09400f3fa81d6b3f405b12a3b67a59a8` | |
| micOff | mic-off.svg | `bcb5a033b4ecd182ec8d0d0945810ccc5147219b1a21c017b47fd4d5ae3a8320` | ekstra indirildi |
| sliders | sliders-horizontal.svg | `e43a00e5eb684e6cbb61083bed2528d7a3fa5f265693eb2b5f314cd432aa65f4` | NAV: General |
| plug | plug.svg | `11ba780e4b6f15d37906a8a73537144b59720333d7a9fc8048a437d0389422f8` | NAV: API and models |
| eraser | eraser.svg | `838d4355dd49340523c38a22a2d23f1aca72ef42f8eba79f6a0c84bf6e27b929` | NAV: Cleanup |
| terminal | terminal.svg | `4f9b6488b237757d5cb615ccd07502fa99774826839e2a99017784bdb2596f1a` | NAV: Agent |
| users | users.svg | `eeed488a1ec95ba730dd69996536fb65061d6ea273afb2429ae47e65eebf401c` | NAV: Meeting |
| fileText | file-text.svg | `52ca55846c202335fb870c8aa23e9345630ec10489303756d62e750f7109605c` | NAV: Minutes |
| fileAudio | file-volume.svg | `d253d61a29727e67e19be75c0754a97bed3a6e2fa3ab8cbeb05c10f70f4ffa2f` | `file-audio.svg` 404; `file-music.svg` alternatifi not edildi |
| keyboard | keyboard.svg | `f509925ca81964ed06251ad4702e989bb81a566ffc74d15c2226b4f07ded67be` | NAV: Shortcuts |
| history | — (YOK) | — | `history.svg` upstream'de 404 (2026-09-03). En yakın: `rotate-ccw.svg` / `clock.svg` (indirildi). NAV History sayfası inline SVG ile devam. |
| pip | picture-in-picture-2.svg | `eccce9ef362520bbb8904fbc1fc89f5d02fb0fbb7c6704cdd3b761dd4fc102b0` | Overlay/Indicator sayfası |
| search | search.svg | `283d371c2e433817bb9c0c8310caa6c77fa4177c0f4f1168d9c83b97af7389dc` | |
| dashboard | layout-dashboard.svg | `281ab865b4c04dab32a04023473e448f58be6a7ad90769450ac3349d79dc4aed` | |
| plus | plus.svg | `7f6af73bf1ff6c4bca3f18351c8d1bdec6749c0c2530c4de5da85d520c21df17` | |
| x | x.svg | `4a9cdab38fbb96162e7dace28e33f4ca0e49d8963a6162abc3d4691b7d675117` | |
| chevD | chevron-down.svg | `66ea878e72ed3488bb3b464c39dfdccee8d1f78e560dccea40e5e12da0e87e87` | |
| chevR | chevron-right.svg | `2758143d7b2434e4aa7307dfd34405c87909ff4052f21b5f3f40d45224b4f19b` | |
| chevL | chevron-left.svg | `83b0681aa38bf55e9d52a1e4b4cced624abe1fe7678ecafda133a574f1161d93` | |
| check | check.svg | `7f33acc9a77a61659531044525fc008edebe215bf4dcf1c789c8674ad3277db0` | |
| checkC | circle-check-big.svg | `25f075fd621df48282ace8326680a4cd165965e61458d2fd0cc1303cefc179ac` | güncel kanonik ad (`circle-check` eski takma ad) |
| xC | circle-x.svg | `bcd8788901e6f29e1b231a81ba5e707d083d06cb4848a28f29407fab4f8e0b64` | |
| alert | triangle-alert.svg | `4866f38b8560d410f21e3226413e0b77997b6dfbb6931fadfe0a0d5aef9ffeb4` | `alert-triangle.svg` 404 (yeniden adlandırılmış) |
| info | info.svg | `bc977a64eb96f3e9a3fceb70e3e65c02b571f76064062ed31f3cb9` | |
| help | circle-question-mark.svg | `975db087da041530dbf59ba1e61a7b99c3519fad43dae6375e42ccc74ba63924` | `circle-help.svg` 404 (yeniden adlandırılmış) |
| dots | ellipsis.svg | `4f495cc72013ffdfec677f03b33a150f7b4dd741979283fd6853a09024bca112` | |
| copy | copy.svg | `ea80e566c7a12628a447cb53179b19aea4f60b9143e2becd0d0f20bf260e5718` | |
| trash | trash-2.svg | `27299f69ad7c6272be64b1b8e2d48cbd6dcf0ef0d4f92827a1affa945c91700e` | |
| folder | folder.svg | `f0d92b94b797a8ab7d4c4ae33c3236c47f64068351b4e14bdb5014ee42898a39` | |
| refresh | refresh-cw.svg | `2e10dd403c85a24f163d59fc6151aa21147fe9402e1305dfc8979208caee8944` | |
| download | download.svg | `3daeee13ded5a3afa2198b1bb4e2262d163922f97d96ac6ff9953e8ed4fe039d` | |
| upload | upload.svg | `42816ee1fa0e9d3b82272a97615c1e562b0e9de64780ebf21963bc1db0ceffd1` | |
| stop | square.svg | `bd979354f0ab184b95cecf03eedefe40c2dc65830ac6d7e60017b2b25a354acb` | Lucide'de `stop` yok; kare = stop glifi |
| play | play.svg | `d7c34786135922a92b6896f6c2384ceeb0346afbf6041dc79982011411409833` | |
| pause | pause.svg | `f122ec4ea7f5693a0b1baafa9c708b53980dc87b4aacb297c6e6f71c1a4c115c` | |
| eye | eye.svg | `5bf90197dd7629cad64a2e48d1186a71559deb6121207d10e3dc5b19ebaffdcf` | |
| eyeOff | eye-off.svg | `774bcd975c5de781a4ee778c76e5591bcdeb409955f7054847e7e6003da0a520` | ekstra indirildi |
| pencil | pencil.svg | `7e1ca7a6f5c1eb949671df762f2baadd32f5bd841d43153c3a15279af7d78d0c` | |
| key | key-round.svg | `f8cdea843754ed360e36b04bf6aa2c2b3610935dd39ffc685a36c4d0a05be248` | |
| globe | globe.svg | `82c6b8fa0b8e8d775ec9becd86f74a4e50bff7bee4c81f7362de45348504f14d` | |
| cpu | cpu.svg | `ec83bb69ec029d367d749afc445b39c8e95891ebf99b0400652677c2b149b99c` | |
| bell | bell.svg | `394889e9631fe3a9a63be9a479a95b451b708e432d895978d21d9130b5ee5dbe` | |
| wave | audio-waveform.svg | `d4b6f62b0d72b7ad223f9abeb51e64875e4533123d7898d07acfa74154eb14b3` | |
| headphones | headphones.svg | `7719585dafa921805aefc21fc3262bbcc621507610a653b84e1632236650b35a` | |
| monitor | monitor.svg | `d1a443233345724859de8e4fb48968ba91e885e12ddbd710701548bd91b39428` | |
| power | power.svg | `1e6b84a659aa43f826cdd8df0a63d349720004e2ccb10c33e415a990a311aa05` | |
| restart | rotate-ccw.svg | `622685386ab4017eabfde01cd74550a20b1924df233b353f73b6b155371f2afd` | |
| filter | funnel.svg | `288f869330602e29a640099ffc5d6ac01caadad2ef6f8aac1138b8bf91ccd752` | `filter.svg` 404 (`filter`→`funnel` yeniden adlandırma; `list-filter` takma ad) |
| calendar | calendar.svg | `312ac8e715ac2b71bcc942dec2e8de9c1929085474f08885af35b563f6aa7a0b` | |
| tag | tag.svg | `85e11c07b29f5b67410e0f14c84799d9406320cd4575b7c8322f31910e0582cc` | |
| type | type.svg | `82c514732330f9c36c0f1f7fd1034634fa6ad21ba2016ffa76cf5d9608c3d6b1` | |
| clock | clock.svg | `e9d3e3acf4d1c280fcf8092293439dc0a4756a908ceb859de144b12451cd1cb9` | |
| arrowUR | arrow-up-right.svg | `50b2503b9d11881142255466b7e3461d022b919735841c321d72003ac9959fe1` | |
| minus | minus.svg | `a0c743ab6dbf545d8a6e19ef3874f48ede686ce68d25e231bd81f540d97b1f19` | |
| square | square.svg | `bd979354f0ab184b95cecf03eedefe40c2dc65830ac6d7e60017b2b25a354acb` | `stop` ile aynı dosya (kare = stop glifi) |
| save | save.svg | `ee9d56a7fec4b20dd6689546d41f68219ea8cbd67f99bd17a1bdaff5be6edb53` | |
| sun | sun.svg | `a3955c8b0425fcc5c9ba12d2bdd77fe53b2cd5dd05e7742a56f342e996fb2ef8` | |
| moon | moon.svg | `205b959e940d5841f0ce1d09c933153da9d9c94130a54d5cc0c68c2af1d403da` | |

Tüm ikon dosyaları ISC lisansıdır (https://raw.githubusercontent.com/lucide-icons/lucide/main/LICENSE):
"Copyright (c) 2026 Lucide Icons and Contributors". Kaynak URL kalıbı:
`https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/<ad>.svg`.

## 3. `vendor/manifest.json` için ÖNERİ (dosya yazılmadı — sadece öneri metni)

```json
{
  "fonts": [
    {"file": "assets/fonts/SpaceGrotesk-Variable.ttf", "family": "Space Grotesk",
     "role": "display", "source": "google/fonts@main:ofl/spacegrotesk",
     "license": "OFL-1.1",
     "sha256": "acad6de1fc93436f5c0f1f4137751ef04f1aea3063e7036535970ffcfbd79f72"},
    {"file": "assets/fonts/Inter-Variable.ttf", "family": "Inter",
     "role": "body", "source": "google/fonts@main:ofl/inter",
     "license": "OFL-1.1",
     "sha256": "29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031"}
  ],
  "icons": {"set": "lucide", "license": "ISC",
            "dir": "assets/fonts/icons", "count": 56,
            "map": "bkz. bölüm 2 tablosu"}
}
```

## 4. Fallback durumu

Fallback GEREKMEDİ — internet erişimi vardı, 58/58 dosya indirildi ve
`sha256sum -c` ile doğrulandı. Mevcut `docs/fonts/` + `ui/icons.py` inline SVG
akışı aynen korunduğu için uygulama bu paket olmadan da çalışır; entegrasyon
(QFontDatabase / icons.py eşleşmesi) ayrı bir görevde, mevcut dosyalara
dokunmadan yapılmalıdır.

Doğrulama:
`ls assets/fonts assets/fonts/icons | wc -l` → 2 TTF + 56 SVG;
`du -cb assets vendor | tail -1` → 1032677;
`sha256sum assets/fonts/*.ttf assets/fonts/icons/*.svg` → yukarıdaki hashler;
`sha256sum -c` → 58/58 OK.
