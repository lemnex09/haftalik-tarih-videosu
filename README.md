# Haftalık Tarih Videosu Otomasyonu

"Eğer X yılında Y olsaydın?" formatında, 2. tekil şahısla anlatılan, yuvarlak beyaz kafalı karakterlerin olduğu çizgi film tarzında 7–8 dakikalık videolar üretir.

## Akış
```
Her hafta (Claude zamanlanmış görevi)
  └─ topics.yaml → sıradaki konu → web araştırması → episodes/<slug>/script.yaml → push
GitHub Actions ("Videoyu üret")
  └─ OpenAI gpt-image (~160 görsel, stil referanslı)
  └─ ElevenLabs (klon sesin, bölüm başına 1 çağrı, kelime zamanlamalı)
  └─ ffmpeg: Ken Burns hareketi + ekran yazıları + ses normalize → 1080p mp4
  └─ kapak, YouTube başlık/açıklama/bölümler → GitHub Release
Claude → videoyu, kapağı ve metinleri sana gönderir → sen onaylayıp yüklersin
```

## Bir kerelik kurulum
1. **GitHub Secrets** (Repo → Settings → Secrets and variables → Actions → New repository secret):
   - `OPENAI_API_KEY`: platform.openai.com → API keys. Görsel modeline erişim için kuruluş doğrulaması gerekebilir.
   - `ELEVENLABS_API_KEY`: elevenlabs.io → Profile → API Keys.
   - `ELEVENLABS_VOICE_ID`: ElevenLabs → Voices → Add Voice → **Instant Voice Clone**. 1–3 dakikalık temiz kaydını yükle, sonra sesin ID'sini kopyala. Ses klonu için en az Starter planı gerekir. Video başına ~8.500 karakter harcanır.
2. `config.yaml` içindeki `channel.name` ve `instagram` alanlarını doldur.
3. İlk çalıştırmada `assets/style/style_ref.png` otomatik üretilir ve repoya eklenir. Beğenmezsen silip yeniden çalıştır ya da kendi referans görselini koy. Tüm bölümler bu görselin stilini izler.

## Elle çalıştırma
- GitHub → Actions → "Videoyu üret" → Run workflow → slug: `1938-turkiyede-dogmak`
- Ucuz deneme: `images_quality` alanına `low` yaz.
- Yerelde: `IMAGES_PROVIDER=placeholder VOICE_PROVIDER=dummy python -m pipeline all <slug>` hiç para harcamadan zamanlamayı ve kurguyu test eder.

## Tahmini maliyet (video başına)
| Kalem | Yaklaşık |
|---|---|
| ~160 görsel, gpt-image orta kalite, 1536×1024 | 7–11 $ (düşük kalite: 2–3 $) |
| Kapak (yüksek kalite) | ~0,25 $ |
| ElevenLabs ~8.500 karakter | Starter (5 $/ay, 30 bin karakter) ayda 3 videoya yeter. Haftalık tempo için Creator (22 $/ay) gerekir |
| GitHub Actions | Ücretsiz kotada (~30–40 dk) |

## Düzeltme
- Tek sahneyi yeniden üretmek için `script.yaml` içindeki `image` metnini değiştir. Yalnızca değişen sahneler yeniden üretilir, gerisi önbellekten gelir.
- Seslendirmede telaffuz hatası varsa ilgili cümleyi okunuşuna göre yaz ("Bin dokuz yüz…").
- Senaryo kuralları: `docs/SENARYO_REHBERI.md` · Haftalık görev: `docs/HAFTALIK_GOREV.md`
