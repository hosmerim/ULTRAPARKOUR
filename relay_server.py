"""
ULTRAPARKOUR — Relay (Aktarıcı) Sunucu — Oda Sistemi Sürümü
==============================================================
WebSocket üzerinden çalışır (Render gibi barındırma servisleri ham TCP'yi
yönlendirmediği için). Artık sadece "oda kodu eşleştirme" değil, gerçek bir
LOBİ SİSTEMİ var:
  - Oda oluşturma (isim + isteğe bağlı şifre + mod: duello/futbol)
  - Aktif odaların listesini isteme (Odaları Ara ekranı için)
  - Şifreli/şifresiz odaya katılma
  - Bağlantı kurulduktan sonra: iki oyuncu arasında mesajları aynen aktarma
    (pos/atis/hit/oldu/top/topat/vb — oyunun kendi protokolü, sunucu içeriğe
    karışmaz, sadece kime ait olduğunu bilip diğerine iletir)

Bulutta çalıştırmak için (Render vb.):
  - Bu dosyayı ve requirements.txt'i (içinde 'websockets' satırı olmalı) yükle
  - Start Command: python relay_server.py
"""

import asyncio
import json
import os
import time
import websockets

PORT = int(os.environ.get('PORT', 5555))
PROTOKOL_SURUMU = 2  # ULTRAPARKOUR.py'deki MP_PROTOKOL_SURUMU ile eşleşmeli

# oda_adi -> {
#   'sifre': str,              # "" ise şifresiz
#   'mod': 'duello'|'futbol',
#   'oyuncular': [websocket, websocket?],
#   'adlar': [kullanici_adi, kullanici_adi?],
#   'olusturulma': zaman damgası
# }
odalar = {}


async def gonder(ws, veri):
    try:
        await ws.send(json.dumps(veri))
    except Exception:
        pass


async def oda_listesi_gonder(ws):
    liste = []
    for ad, oda in odalar.items():
        if len(oda['oyuncular']) < 2:  # sadece boş yer olan odalar listelensin
            liste.append({
                'ad': ad,
                'mod': oda['mod'],
                'sifreli': bool(oda['sifre']),
                'host': oda['adlar'][0] if oda['adlar'] else '?',
            })
    await gonder(ws, {'sys': 'oda_listesi', 'odalar': liste})


async def handler(websocket):
    oda_adi = None
    try:
        async for ilk_mesaj in websocket:
            try:
                veri = json.loads(ilk_mesaj)
            except Exception:
                continue
            tip = veri.get('t')

            # --- SÜRÜM KONTROLÜ: giriş noktası mesajlarında istemcinin sürümünü doğrula ---
            if tip in ('oda_listesi_iste', 'oda_kur', 'oda_katil'):
                istemci_surumu = veri.get('surum')
                if istemci_surumu != PROTOKOL_SURUMU:
                    await gonder(websocket, {
                        'sys': 'surum_uyumsuz',
                        'sunucu_surumu': PROTOKOL_SURUMU,
                        'sizin_surumu': istemci_surumu if istemci_surumu is not None else 'bilinmiyor (çok eski sürüm)',
                    })
                    continue

            if tip == 'oda_listesi_iste':
                await oda_listesi_gonder(websocket)
                continue

            if tip == 'oda_kur':
                istenen_ad = str(veri.get('oda_adi', '')).strip()[:24]
                if not istenen_ad:
                    await gonder(websocket, {'sys': 'hata', 'mesaj': 'Oda adı boş olamaz.'})
                    continue
                if istenen_ad in odalar:
                    await gonder(websocket, {'sys': 'oda_var'})
                    continue
                odalar[istenen_ad] = {
                    'sifre': str(veri.get('sifre', ''))[:24],
                    'mod': veri.get('mod', 'duello'),
                    'oyuncular': [websocket],
                    'adlar': [str(veri.get('kullanici_adi', 'Oyuncu'))[:16]],
                    'olusturulma': time.time(),
                    'hazir_event': asyncio.Event(),
                }
                oda_adi = istenen_ad
                await gonder(websocket, {'sys': 'bekliyor'})

                # ÖNEMLİ DÜZELTME: kurucu burada eski haliyle "yeni mesaj bekle" döngüsünde kalıp
                # rakip katılınca aktarım moduna hiç geçmiyordu (rakip görüyordu ama kurucunun
                # kendi hareketleri sessizce yok sayılıyordu). Basit bir bekleme (polling) döngüsüyle
                # rakip katılana ya da bağlantı kopana kadar bekliyoruz, sonra aktarım moduna geçiyoruz.
                while True:
                    if websocket.close_code is not None:
                        return  # bağlantı koptu, finally bloğu temizleyecek
                    if oda_adi not in odalar:
                        return  # oda bir şekilde silindi (örn. temizleyici tarafından)
                    if odalar[oda_adi]['hazir_event'].is_set():
                        break  # rakip katıldı, aktarım moduna geç
                    await asyncio.sleep(0.3)
                break

            if tip == 'oda_katil':
                istenen_ad = str(veri.get('oda_adi', '')).strip()[:24]
                oda = odalar.get(istenen_ad)
                if not oda:
                    await gonder(websocket, {'sys': 'oda_yok'})
                    continue
                if len(oda['oyuncular']) >= 2:
                    await gonder(websocket, {'sys': 'doldu'})
                    continue
                if oda['sifre'] and oda['sifre'] != str(veri.get('sifre', '')):
                    await gonder(websocket, {'sys': 'sifre_yanlis'})
                    continue
                oda['oyuncular'].append(websocket)
                oda['adlar'].append(str(veri.get('kullanici_adi', 'Oyuncu'))[:16])
                oda_adi = istenen_ad
                # ikisine de "hazır" bilgisini (mod dahil) gönder — mod uyuşmazlığı olmasın diye
                # mod HER ZAMAN odayı kuran (host) tarafından belirlenir
                await gonder(oda['oyuncular'][0], {'sys': 'hazir', 'host': True, 'mod': oda['mod'], 'rakip_adi': oda['adlar'][1]})
                await gonder(oda['oyuncular'][1], {'sys': 'hazir', 'host': False, 'mod': oda['mod'], 'rakip_adi': oda['adlar'][0]})
                oda['hazir_event'].set()  # kurucunun bekleyişini sonlandır, o da aktarım moduna geçsin
                break  # artık lobi mesajları bitti, aşağıdaki döngü ham aktarım yapacak

        # --- Bağlantı kuruldu: bundan sonra gelen her mesajı karşı tarafa aynen aktar ---
        if oda_adi and oda_adi in odalar:
            async for mesaj in websocket:
                oda = odalar.get(oda_adi)
                if not oda:
                    break
                for c in oda['oyuncular']:
                    if c is not websocket:
                        try:
                            await c.send(mesaj)
                        except Exception:
                            pass

    except Exception:
        pass
    finally:
        if oda_adi and oda_adi in odalar:
            oda = odalar[oda_adi]
            if websocket in oda['oyuncular']:
                idx = oda['oyuncular'].index(websocket)
                oda['oyuncular'].remove(websocket)
                if idx < len(oda['adlar']):
                    oda['adlar'].pop(idx)
            for c in oda['oyuncular']:
                await gonder(c, {'sys': 'rakip_ayrildi'})
            if not oda['oyuncular']:
                del odalar[oda_adi]
        try:
            await websocket.close()
        except Exception:
            pass


async def stale_oda_temizleyici():
    """Uzun süre (15 dk) tek kişiyle rakip beklemiş ya da her nasılsa askıda kalmış
    odaları düzenli aralıklarla temizler — 'kullanılmayan sunucu' birikmesini önler."""
    while True:
        await asyncio.sleep(120)  # 2 dakikada bir kontrol et
        simdi = time.time()
        silinecekler = [ad for ad, oda in odalar.items()
                         if len(oda['oyuncular']) < 2 and simdi - oda['olusturulma'] > 900]
        for ad in silinecekler:
            oda = odalar.get(ad)
            if oda:
                for c in oda['oyuncular']:
                    try:
                        await c.close()
                    except Exception:
                        pass
                del odalar[ad]
        if silinecekler:
            print(f"[RELAY] {len(silinecekler)} kullanılmayan oda temizlendi: {silinecekler}")


async def main():
    print(f"[RELAY] Oda sistemi sunucusu {PORT} portunda dinliyor...")
    asyncio.create_task(stale_oda_temizleyici())
    async with websockets.serve(handler, "0.0.0.0", PORT, ping_interval=None):
        await asyncio.Future()


if __name__ == '__main__':
    asyncio.run(main())
