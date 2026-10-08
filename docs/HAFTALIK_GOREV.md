# Haftalık görev talimatı (Claude zamanlanmış görevi bunu uygular)

1. Repoyu klonla. `docs/SENARYO_REHBERI.md`, `topics.yaml` ve son bölümün `episodes/<slug>/script.yaml` dosyasını oku. Son bölüm üslup örneğidir; cümlelerini tekrar etme.
2. `python -m pipeline next-topic` ile sıradaki konuyu al. Kuyruk boşsa 5 yeni konu öner, kullanıcıya bildir ve dur.
3. **Araştır:** web aramasıyla 30+ doğrulanmış olgu topla (tarih, rakam, kaynak URL). Güvenilir kaynak kullan: TÜİK, resmi kurumlar, akademik dergiler, Wikipedia'da kaynaklı rakamlar. Kaynaklar arasında çelişki varsa yumuşak ifade kullan ya da rakamı atla.
4. **Yaz:** `episodes/<slug>/script.yaml` dosyasını rehberdeki şemaya ve iskelete göre yaz. Hedef 1.100–1.250 kelime, 170–210 sahne, 12–16 bölüm. Kaynakları `sources` listesine ekle.
5. `python -m pipeline validate <slug>` hatasız geçmeli. Ardından `IMAGES_PROVIDER=placeholder VOICE_PROVIDER=dummy python -m pipeline render <slug>` ile kuru deneme yap (zamanlamayı kontrol eder, para harcamaz). Sonra `episodes/<slug>/build` klasörünü sil.
6. **Kendi kendine olgu kontrolü:** senaryodaki her rakamı `sources` listesiyle karşılaştır. Kaynağı olmayanı düzelt.
7. Commit at ve `main`'e push et. Push, GitHub Actions'taki "Videoyu üret" iş akışını tetikler (görseller, ses, kurgu ~30–60 dk).
8. İş akışını bekle. Actions API'si bu ortamdan kapalı; durumu commit'in check-run'larından oku: `gh api repos/lemnex09/haftalik-tarih-videosu/commits/<sha>/check-runs --jq '.check_runs[]|[.name,.status,.conclusion]|@tsv'` (birkaç dakikada bir). `render` tamamlanınca `gh api repos/lemnex09/haftalik-tarih-videosu/releases/latest` ile en yeni release'i bul ve `gh release download <tag> -R lemnex09/haftalik-tarih-videosu` ile mp4, thumbnail.jpg, onizleme.jpg ve YOUTUBE.md dosyalarını indir. Başarısızsa check-run'ın `output.summary`/`output.text` alanlarını ve `html_url`'i oku.
9. `onizleme.jpg` dosyasına bak. Bozuk ya da eksik görsel varsa ilgili sahnenin `image` metnini düzelt ve push et. script.yaml değiştiği için iş akışı yeniden çalışır, değişmeyen görseller önbellekten gelir.
10. Videoyu, kapağı ve YOUTUBE.md'yi kullanıcıya gönder, telefonuna bildirim yolla. Mesajda başlığı, süreyi ve kontrol etmesi gereken 2–3 noktayı yaz. İş akışı başarısız olduysa hatanın özetini ve çözümünü gönder.
