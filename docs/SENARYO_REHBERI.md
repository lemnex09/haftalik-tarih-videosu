# Senaryo Rehberi — "Eğer X yılında Y olsaydın" formatı

Haftalık oturum her bölümü bu rehbere göre yazar. Format, referans videonun (1964 Almanya, 7:48) çözümlemesinden çıkarıldı. **Hiçbir kanalın cümlesi kopyalanmaz**; sadece formül uygulanır.

## Hedef ölçüler
| Ölçü | Hedef |
|---|---|
| Süre | 7:30 – 8:30 dk |
| Kelime | 1.100 – 1.250 (≈150 kelime/dk) |
| Bölüm (chapter) | 12 – 16 |
| Sahne (görsel) | 170 – 210, sahne başı ~2–3 sn |
| Yeni görsel | sahnelerin ~%85'i, kalanı `reuse` ile tekrar (maliyet düşer) |
| Ekran yazısı | 25 – 40 adet, ≤18 karakter, BÜYÜK HARF |

## Anlatım kuralları
1. **2. tekil şahıs, şimdiki zaman.** "Kahvede oturuyorsun." Asla "siz" ya da "o".
2. **Kısa cümleler.** Çoğu 3–12 kelime. Bir sahnenin `say` alanı = 1 kısa cümle ya da uzun cümlenin yarısı.
3. **Kuru mizah + gerçek dram.** Her bölümde en az bir küçük espri, her 2–3 bölümde bir duygusal an.
4. **Somut duyusal detay.** Koku, ses, eşya, yemek. "Tahta bavul, iki gömlek, bir kalıp peynir."
5. **Her bölümde en az bir şaşırtıcı ve doğrulanmış rakam.** Kaynağı `sources` listesine yaz. Emin olmadığın bilgiyi yumuşat ("yaklaşık", "kimi kaynağa göre") ya da hiç kullanma.
6. **Rakamları okunuşuyla yaz** (TTS doğru okusun): "bin dokuz yüz otuz sekiz", "yüzde seksen". Ekran yazısında (`overlay`) rakam kullanılabilir: "1938".
7. **Tekrar eden şaka (callback).** Başta bir nesne/şaka koy, 2–3 kez geri getir (referansta: peynir).
8. **Ana motif kelimesi.** Başta "Bu kelimeyi aklında tut." de, finalde motife dön.

## İskelet
1. **Soğuk açılış (0:00–0:30):** "Yıl …" + çok somut bir mikro sahne → küçük bir dönüm anı → "Tebrikler…" tarzı ters köşe → gelecekte olacak 3 çarpıcı şeyin teaser'ı → emir kipiyle kapanış ("Hadi bavulu hazırla.").
2. **"Önce biraz arka plan":** 4–6 cümlede dönemin büyük resmi, karşıtlıklarla.
3. **Hayat evreleri:** kronolojik bölümler. Her biri: sahne kur → detay → rakam → espri ya da duygu.
4. **Liste cihazı:** "Bu yolculukta üç düşmanın var: …" gibi bir sayım.
5. **Yan not:** "… ayrı bir video konusu." (gelecek bölüme kanca)
6. **Ters köşe:** "Planı hatırlıyor musun?" Beklenenle gerçek arasındaki fark.
7. **Bugüne zoom:** bugünkü büyük rakam, motife dönüş, duygusal kapanış.
8. **Yorum çağrısı:** "Senin ailende … var mı? Yorumlara yaz." + motife bağlı abone esprisi.

## Görsel kuralları (`image` alanı, İngilizce)
- Stil metni otomatik eklenir. Sen sadece **sahneyi** tarif et: kim, ne yapıyor, nerede, dönem detayları, çekim ölçeği (wide / medium / close-up), ışık ve duygu.
- Tekrarlayan karakterleri `characters` içinde tanımla ve `{SEN_COCUK}` gibi etiketle kullan. Yaşlandıkça ayrı karakter aç: `SEN_COCUK`, `SEN_GENC`, `SEN_YASLI`.
- Görselde yazı istemeyiz. Gerekirse (tabela, damga) metni tırnakla açıkça yaz: `a stamp that reads "SAĞLAM"`.
- Aynı mekânda art arda sahneler için `reuse` + farklı `move` (in, out, left, right, up) kullan.
- Hassas konular (savaş, deprem, ölüm): sembolik ve aile dostu anlat. Kan, ceset, şiddet yok.

## script.json şeması
```json
{
  "title": "Eğer 1938'de Türkiye'de Doğsaydın?",
  "motif": "…",
  "characters": {"SEN_COCUK": "a 7-year-old village boy, white round head, …"},
  "youtube": {"title": "…", "description": "…", "tags": ["…"], "hashtags": ["#…"], "pinned_comment": "…"},
  "thumbnail": {"image": "…", "text": "1938'DE\nDOĞSAYDIN?"},
  "sources": ["Açıklama — URL"],
  "sections": [
    {"title": "Bölüm başlığı (YouTube chapter)",
     "scenes": [
       {"say": "Bin dokuz yüz otuz sekiz.", "image": "…", "overlay": "1938", "overlay_pos": "top-left"},
       {"say": "…", "reuse": "s01_01", "move": "in"}
     ]}
  ]
}
```

## Teslimden önce
`python -m pipeline validate <slug>` hatasız geçmeli. Süre 7–9 dk, sahne ortalaması ≤3 sn olmalı.
