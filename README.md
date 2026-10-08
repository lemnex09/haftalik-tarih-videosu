# Haftalık Tarih Videosu Otomasyonu

"Eğer X yılında Y olsaydın?" formatında, 2. tekil şahısla anlatılan, yuvarlak beyaz kafalı karakterlerin olduğu çizgi film tarzında 7–8 dakikalık videolar üretir.

## Akış
```
Her hafta (Claude zamanlanmış görevi)
  └─ topics.yaml → sıradaki konu → web araştırması → episodes/<slug>/script.yaml → push
GitHub Actions ("Videoyu üret")
  └─ FLUX görselleri (~160 adet, Cloudflare ücretsiz kota → Pollinations yedek)
  └─ Seslendirme: kendi kaydın (kayit.mp3) ya da ücretsiz Microsoft Türkçe sesi
  └─ ffmpeg: Ken Burns hareketi + ekran yazıları + ses normalize → 1080p mp4
  └─ kapak, YouTube başlık/açıklama/bölümler → GitHub Release
Claude → videoyu, kapağı ve metinleri sana gönderir → sen onaylayıp yüklersin
```

## Bir kerelik kurulum (ücretsiz)
1. **Görseller — Cloudflare Workers AI (önerilen, bedava):** dash.cloudflare.com'da ücretsiz hesap aç. Sol menü → AI → Workers AI → "Use REST API" → **Create a Workers AI API Token**. Token'ı ve sayfadaki **Account ID**'yi GitHub Secrets'a ekle: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`. Günde ~170 görsel bedava; kota dolarsa sistem otomatik olarak Pollinations'a geçer.
   - Cloudflare eklemezsen her şey **Pollinations** (anahtarsız, bedava) ile çalışır ama daha yavaştır (~15 sn/görsel).
2. **Ses:** varsayılan bedava Microsoft Türkçe sesi (tr-TR-AhmetNeural). Kendi sesin için senaryoyu tek seferde oku, `episodes/<slug>/kayit.mp3` olarak repoya yükle; sistem kaydını otomatik böler ve görselleri sözlerine senkronlar.
3. Ücretli seçenekler (isteğe bağlı): `config.yaml` → `images.provider: openai` (+ `OPENAI_API_KEY`), `voice.provider: elevenlabs` (+ `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`).
4. `config.yaml` içindeki `channel.name` ve `instagram` alanlarını doldur.

## Elle çalıştırma
- GitHub → Actions → "Videoyu üret" → Run workflow → slug: `1938-turkiyede-dogmak`
- Ucuz deneme: `images_quality` alanına `low` yaz.
- Yerelde: `IMAGES_PROVIDER=placeholder VOICE_PROVIDER=dummy python -m pipeline all <slug>` hiç para harcamadan zamanlamayı ve kurguyu test eder.

## Maliyet
Varsayılan kurulum **0 TL**: Cloudflare ücretsiz kotası / Pollinations + Microsoft Edge sesi + GitHub Actions ücretsiz dakikaları (özel repoda ayda 2.000 dk; video başına ~40–70 dk).

## Düzeltme
- Tek sahneyi yeniden üretmek için `script.yaml` içindeki `image` metnini değiştir. Yalnızca değişen sahneler yeniden üretilir, gerisi önbellekten gelir.
- Seslendirmede telaffuz hatası varsa ilgili cümleyi okunuşuna göre yaz ("Bin dokuz yüz…").
- Senaryo kuralları: `docs/SENARYO_REHBERI.md` · Haftalık görev: `docs/HAFTALIK_GOREV.md`
