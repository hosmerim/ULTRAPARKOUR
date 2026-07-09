"""
ULTRAPARKOUR — Relay (Aktarıcı) Sunucu — WebSocket sürümü
===========================================================
Render gibi barındırma servisleri trafiği düzgün yönlendirmek için HTTP/WebSocket
bekliyor (ham TCP'yi tanımıyor, "No open HTTP ports" hatası veriyor). Bu yüzden
bu sürüm ham socket yerine WebSocket protokolünü kullanıyor.

İki oyuncuyu bir "oda kodu" ile eşleştirir ve aralarındaki mesajları aktarır.

Bulutta çalıştırmak için (Render vb.):
  - Bu dosyayı ve requirements.txt'i (içinde 'websockets' satırı olmalı) yükle
  - Start Command: python relay_server.py
  - Build Command: pip install -r requirements.txt

Protokol (JSON metin mesajları, WebSocket çerçeveleri içinde):
  - İlk mesaj:  {"oda": "ABC123"}
  - Sonrası:    oyunun gönderdiği her şey (pos/hit/oldu...) aynen karşı tarafa aktarılır
  - Sunucudan gelen kontrol mesajları:
      {"sys": "bekliyor"} / {"sys": "hazir", "host": true/false} /
      {"sys": "doldu"} / {"sys": "rakip_ayrildi"}
"""

import asyncio
import json
import os
import websockets

PORT = int(os.environ.get('PORT', 5555))

odalar = {}  # oda_kodu -> [websocket, websocket]


async def gonder(ws, veri):
    try:
        await ws.send(json.dumps(veri))
    except Exception:
        pass


async def handler(websocket):
    oda_kodu = None
    try:
        ilk = await websocket.recv()
        veri = json.loads(ilk)
        oda_kodu = str(veri.get('oda', '')).strip().upper()
        if not oda_kodu:
            return

        if oda_kodu not in odalar:
            odalar[oda_kodu] = []
        if len(odalar[oda_kodu]) >= 2:
            await gonder(websocket, {"sys": "doldu"})
            return
        odalar[oda_kodu].append(websocket)
        benim_sira = len(odalar[oda_kodu])  # 1 = ilk gelen (host), 2 = ikinci (client)

        if benim_sira == 1:
            await gonder(websocket, {"sys": "bekliyor"})
        else:
            ikili = list(odalar.get(oda_kodu, []))
            if len(ikili) == 2:
                await gonder(ikili[0], {"sys": "hazir", "host": True})
                await gonder(ikili[1], {"sys": "hazir", "host": False})

        # Bundan sonra gelen her mesajı karşı tarafa aynen aktar
        async for mesaj in websocket:
            ikili = list(odalar.get(oda_kodu, []))
            for c in ikili:
                if c is not websocket:
                    try:
                        await c.send(mesaj)
                    except Exception:
                        pass

    except Exception:
        pass
    finally:
        if oda_kodu and oda_kodu in odalar:
            if websocket in odalar[oda_kodu]:
                odalar[oda_kodu].remove(websocket)
            for c in odalar[oda_kodu]:
                await gonder(c, {"sys": "rakip_ayrildi"})
            if not odalar[oda_kodu]:
                del odalar[oda_kodu]


async def main():
    print(f"[RELAY] WebSocket sunucu {PORT} portunda dinliyor...")
    async with websockets.serve(handler, "0.0.0.0", PORT, ping_interval=None):
        await asyncio.Future()


if __name__ == '__main__':
    asyncio.run(main())
