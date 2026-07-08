"""
ULTRAPARKOUR — Relay (Aktarıcı) Sunucu
=======================================
İki oyuncuyu bir "oda kodu" ile eşleştirir ve aralarındaki mesajları aktarır.
Her iki oyuncu da bu sunucuya DIŞARI doğru bağlandığı için (kimse dışarıdan
bağlantı kabul etmez), router/NAT engeli olmadan uzaktan oynayabilirler.

Bulutta çalıştırmak için (Render, Railway, Fly.io vb.):
  - Bu tek dosyayı yükle
  - Başlatma komutu: python relay_server.py
  - Sunucu, PORT ortam değişkenini otomatik kullanır (bulut sağlayıcıları bunu verir);
    yoksa 5555 kullanır.

Protokol (satır bazlı JSON, her mesaj \n ile biter):
  - İlk mesaj:  {"oda": "ABC123"}   → oyuncu hangi odaya katılmak istediğini söyler
  - Sonrası:    oyunun gönderdiği her şey (pos/hit/oldu...) aynen karşı tarafa aktarılır
  - Sunucudan gelen kontrol mesajları:
      {"sys": "bekliyor"}  → oda oluşturuldu, ikinci oyuncu bekleniyor
      {"sys": "hazir", "host": true/false}  → eşleşme tamam, oyun başlayabilir
      {"sys": "doldu"}     → oda zaten iki kişiyle dolu
      {"sys": "rakip_ayrildi"}  → karşı oyuncunun bağlantısı koptu
"""

import socket
import threading
import json
import os

HOST = ''
PORT = int(os.environ.get('PORT', 5555))

# oda_kodu -> [ (conn1, addr1), (conn2, addr2) ]
odalar = {}
kilit = threading.Lock()


def gonder(conn, veri):
    """Bir sözlüğü JSON satırı olarak gönderir. Hata olursa sessizce yutar."""
    try:
        conn.sendall((json.dumps(veri) + "\n").encode())
    except Exception:
        pass


def istemci_isle(conn, addr):
    oda_kodu = None
    dosya = None
    try:
        dosya = conn.makefile('r')

        # 1) İlk satır oda kodunu içermeli
        ilk = dosya.readline()
        if not ilk:
            return
        try:
            veri = json.loads(ilk.strip())
        except Exception:
            return
        oda_kodu = str(veri.get('oda', '')).strip().upper()
        if not oda_kodu:
            return

        # 2) Odaya yerleştir
        with kilit:
            if oda_kodu not in odalar:
                odalar[oda_kodu] = []
            if len(odalar[oda_kodu]) >= 2:
                gonder(conn, {"sys": "doldu"})
                return
            odalar[oda_kodu].append(conn)
            benim_sira = len(odalar[oda_kodu])  # 1 = ilk gelen (host), 2 = ikinci (client)

        if benim_sira == 1:
            gonder(conn, {"sys": "bekliyor"})
        else:
            # İkinci oyuncu geldi -> iki tarafa da "hazir" gönder
            with kilit:
                ikili = list(odalar.get(oda_kodu, []))
            if len(ikili) == 2:
                gonder(ikili[0], {"sys": "hazir", "host": True})
                gonder(ikili[1], {"sys": "hazir", "host": False})

        # 3) Bundan sonra gelen her satırı karşı tarafa aktar
        for satir in dosya:
            with kilit:
                ikili = list(odalar.get(oda_kodu, []))
            karsi = None
            for c in ikili:
                if c is not conn:
                    karsi = c
            if karsi is not None:
                try:
                    karsi.sendall(satir.encode())
                except Exception:
                    pass

    except Exception:
        pass
    finally:
        # Temizlik: odadan çık, karşı tarafa haber ver
        with kilit:
            if oda_kodu and oda_kodu in odalar:
                if conn in odalar[oda_kodu]:
                    odalar[oda_kodu].remove(conn)
                for c in odalar[oda_kodu]:
                    gonder(c, {"sys": "rakip_ayrildi"})
                if not odalar[oda_kodu]:
                    del odalar[oda_kodu]
        try:
            conn.close()
        except Exception:
            pass


def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(16)
    print(f"[RELAY] Sunucu {PORT} portunda dinliyor...")
    while True:
        conn, addr = s.accept()
        threading.Thread(target=istemci_isle, args=(conn, addr), daemon=True).start()


if __name__ == '__main__':
    main()
