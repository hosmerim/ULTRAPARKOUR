import os
import sys

# Windows dışı işletim sistemlerinde ses kilitlenmesini önleme
if os.name != 'nt': 
    os.environ["SDL_AUDIODRIVER"] = "pulse"

import pygame
import time
import math
import random
import socket
import threading
import json
import ssl
import struct
import base64

# --- BAŞLATMA & SES FREKANS AYARI ---
pygame.init()

print("--- SES SİSTEMİ KONTROLÜ ---")
try:
    # Frekans kararsızlıklarını önlemek için standart CD kalitesine (44100Hz) zorluyoruz
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.mixer.init()
    ses_aktif = True
    print("[OK] Pygame Ses Motoru Başarıyla Başlatıldı.")
except pygame.error as e:
    ses_aktif = False
    print(f"[HATA] Ses kartı başlatılamadı, oyun sessiz modda açılıyor! Detay: {e}")

EN, BOY = 800, 600
DUNYA_EN = 1600  # Normal bölümlerde ekrandan daha geniş bir dünya (keşif hissi için kamera bunun içinde gezer)

# --- TAM EKRAN ALTYAPISI ---
# 'ekran' her zaman sabit 800x600 boyutunda bir mantıksal çizim yüzeyidir (canvas).
# 'gercek_ekran' ise gerçek pencere/monitördür; pencereli modda EN x BOY, tam ekran modda
# ise masaüstü çözünürlüğündedir. Her karede 'ekran' oranı bozulmadan 'gercek_ekran'a ölçeklenir.
tam_ekran_mi = False
ekran = pygame.Surface((EN, BOY))
gercek_ekran = pygame.display.set_mode((EN, BOY))
pygame.display.set_caption("ULTRAPARKOUR")

def tam_ekran_ac_kapa():
    global tam_ekran_mi, gercek_ekran
    tam_ekran_mi = not tam_ekran_mi
    if tam_ekran_mi:
        gercek_ekran = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:
        gercek_ekran = pygame.display.set_mode((EN, BOY))

def _olcek_bilgisi():
    ger_en, ger_boy = gercek_ekran.get_size()
    olcek = min(ger_en / EN, ger_boy / BOY)
    if olcek <= 0: olcek = 1
    yeni_en, yeni_boy = max(1, int(EN * olcek)), max(1, int(BOY * olcek))
    ofset_x, ofset_y = (ger_en - yeni_en) // 2, (ger_boy - yeni_boy) // 2
    return olcek, ofset_x, ofset_y, yeni_en, yeni_boy

def fare_konumu():
    """pygame.mouse.get_pos()'un yerini alır: gerçek ekran koordinatını
    800x600'lük mantıksal canvas koordinatına çevirir (tam ekranda ölçekleme farkını giderir)."""
    mx, my = pygame.mouse.get_pos()
    olcek, ofset_x, ofset_y, _, _ = _olcek_bilgisi()
    return (int((mx - ofset_x) / olcek), int((my - ofset_y) / olcek))

def ekrani_guncelle():
    """pygame.display.update()'in yerini alır: canvas'ı gerçek ekrana ölçekleyip basar."""
    olcek, ofset_x, ofset_y, yeni_en, yeni_boy = _olcek_bilgisi()
    olceklenmis = pygame.transform.scale(ekran, (yeni_en, yeni_boy))
    gercek_ekran.fill((0, 0, 0))
    gercek_ekran.blit(olceklenmis, (ofset_x, ofset_y))
    pygame.display.flip()

def temel_olaylari_isle(event):
    """Her olay döngüsünde çağrılır: pencere kapama ve F11 ile tam ekran aç/kapa işlerini yönetir."""
    if event.type == pygame.QUIT:
        pygame.quit(); sys.exit()
    if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
        tam_ekran_ac_kapa()

# Çalışma dizinini kodun/kaynakların olduğu klasöre sabitle (Dosya yollarını garantiye alır).
# PyInstaller ile .exe'ye çevrilince, mp3/png dosyaları exe'nin İÇİNE gömülü DEĞİLSE
# (yani sadece kod paketlendiyse), exe'nin bulunduğu klasöre bakmamız gerekir —
# kullanıcı bu dosyaları exe ile aynı klasöre kendisi koyar.
try:
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(os.path.abspath(sys.executable)))
    else:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
except:
    pass

# --- SES DOSYALARINI GÜVENLİ YÜKLEME ---
ses_atis = None
ses_olme = None

if ses_aktif:
    # Atış Sesi Kontrolü (Hem .mp3 hem .wav destekler, hata durumunda çökmez)
    try:
        if os.path.exists("atis.mp3"):
            ses_atis = pygame.mixer.Sound("atis.mp3")
            ses_atis.set_volume(0.4)
            print("[OK] atis.mp3 başarıyla yüklendi.")
        elif os.path.exists("atis.wav"):
            ses_atis = pygame.mixer.Sound("atis.wav")
            ses_atis.set_volume(0.4)
            print("[OK] atis.wav başarıyla yüklendi.")
        else:
            print("[UYARI] 'atis.mp3' veya 'atis.wav' bulunamadı! Atış sesleri çalmayacak.")
    except Exception as e:
        print(f"[SES HATASI] Atış sesi yüklenemedi: {e}")

    # Ölme Sesi Kontrolü (Hem .mp3 hem .wav destekler, hata durumunda çökmez)
    try:
        if os.path.exists("olme.mp3"):
            ses_olme = pygame.mixer.Sound("olme.mp3")
            ses_olme.set_volume(0.6)
            print("[OK] olme.mp3 başarıyla yüklendi.")
        elif os.path.exists("olme.wav"):
            ses_olme = pygame.mixer.Sound("olme.wav")
            ses_olme.set_volume(0.6)
            print("[OK] olme.wav başarıyla yüklendi.")
        else:
            print("[UYARI] 'olme.mp3' veya 'olme.wav' bulunamadı! Ölme sesleri çalmayacak.")
    except Exception as e:
        print(f"[SES HATASI] Ölme sesi yüklenemedi: {e}")
print("----------------------------")

# --- ARKA PLAN MÜZİĞİ SİSTEMİ ---
su_anki_muzik = None

def muzik_cal(dosya, hacim=0.5, dongu=True):
    """Belirtilen mp3 dosyasını arka plan müziği olarak çalar.
    Aynı dosya zaten çalıyorsa yeniden başlatmaz (menü döngüsünde her karede
    çağrılsa bile müzik kesilip tekrar başlamaz)."""
    global su_anki_muzik
    if not ses_aktif:
        return
    if su_anki_muzik == dosya:
        return
    if not os.path.exists(dosya):
        print(f"[UYARI] '{dosya}' bulunamadı, müzik çalınamıyor.")
        su_anki_muzik = dosya  # tekrar tekrar aynı uyarıyı basmamak için
        return
    try:
        pygame.mixer.music.load(dosya)
        pygame.mixer.music.set_volume(hacim)
        pygame.mixer.music.play(-1 if dongu else 0)
        su_anki_muzik = dosya
        print(f"[OK] {dosya} çalınıyor.")
    except Exception as e:
        print(f"[MÜZİK HATASI] {dosya} çalınamadı: {e}")

# --- PARTİKÜL SİSTEMİ ---
parcaciklar = []

def parcacik_ekle(x, y, renk, adet=8):
    for _ in range(adet):
        parcaciklar.append({
            'rect': pygame.Rect(x, y, 4, 4),
            'vx': random.uniform(-5, 5),
            'vy': random.uniform(-5, 5),
            'omur': 20,
            'renk': renk
        })

def parcacik_guncelle():
    for p in parcaciklar[:]:
        p['rect'].x += p['vx']
        p['rect'].y += p['vy']
        p['omur'] -= 1
        if p['omur'] <= 0:
            parcaciklar.remove(p)
        else:
            pygame.draw.rect(ekran, p['renk'], p['rect'])

# --- GÖRSEL YÜKLEME ---
try:
    V1_GORSEL = pygame.image.load("karakter.png").convert_alpha()
    V1_GORSEL = pygame.transform.scale(V1_GORSEL, (30, 30))
    resim_yuklendi = True
except:
    resim_yuklendi = False

# İkinci karakter görseli (multiplayer'da ikinci oyuncu için)
try:
    V2_GORSEL = pygame.image.load("karakter2.png").convert_alpha()
    V2_GORSEL = pygame.transform.scale(V2_GORSEL, (30, 30))
    resim2_yuklendi = True
except:
    resim2_yuklendi = False

# --- AYARLAR & METİNLER ---
ayarlar = {"dil": "TR", "performans_modu": False}
metinler = {
    "EN": {
        "basla": "START", "ayarlar": "SETTINGS", "cikis": "QUIT",
        "dil_sec": "LANGUAGE:", "mod_sec": "PERFORMANCE:", "geri": "BACK",
        "zorluk": "// DIFFICULTY", "sektor": "// SELECT SECTOR", "deploy": "DEPLOY >>>",
        "kolay": "EASY", "orta": "MEDIUM", "zor": "HARD", "extreme": "EXTREME",
        "bitti": "STAGE CLEARED", "oldu": "YOU DIED", "tekrar": "RETRY",
        "sektorler": "SECTORS", "ana_menu": "MENU", "on": "ON", "off": "OFF",
        "yenilikler": "WHAT'S NEW"
    },
    "TR": {
        "basla": "BAŞLA", "ayarlar": "AYARLAR", "cikis": "ÇIKIŞ",
        "dil_sec": "DİL:", "mod_sec": "PERFORMANS:", "geri": "GERİ",
        "zorluk": "// ZORLUK", "sektor": "// SEKTÖR SEÇ", "deploy": "BAŞLAT >>>",
        "kolay": "KOLAY", "orta": "ORTA", "zor": "ZOR", "extreme": "EKSTREM",
        "bitti": "BÖLÜM GEÇİLDİ", "oldu": "YOK EDİLDİN", "tekrar": "TEKRAR",
        "sektorler": "SECTORS", "ana_menu": "MENÜ", "on": "AÇIK", "off": "KAPALI",
        "yenilikler": "YENİLİKLER"
    }
}

# --- RENKLER & ÖN TANIMLI FONTLAR ---
SIYAH, BEYAZ, GRI = (10, 10, 10), (255, 255, 255), (100, 100, 100)
PARLAK_KIRMIZI, KOYU_KIRMIZI = (255, 0, 0), (60, 0, 0)
YESIL, SARI, TURKUAZ, MAVI, MOR = (0, 255, 0), (255, 255, 0), (0, 255, 255), (0, 80, 255), (200, 0, 255)
TURNCU = (255, 128, 0)
GABRIEL_MAVI = (0, 200, 255)
MINOS_MINT = (150, 255, 200)

font_baslik = pygame.font.SysFont("Courier", 70, bold=True)
font_countdown_base = pygame.font.SysFont("Courier", 120, bold=True)
font_buton = pygame.font.SysFont("Courier", 22, bold=True)
font_ui = pygame.font.SysFont("Courier", 16, bold=True)
font_konusma = pygame.font.SysFont("Arial", 14, bold=True)
font_rank = pygame.font.SysFont("Courier", 90, bold=True)
font_style = pygame.font.SysFont("Courier", 20, bold=True)
font_stil_buyuk = pygame.font.SysFont("Courier", 34, bold=True)

saat = pygame.time.Clock()
zorluk_hizi, dusman_sayisi, secili_harita, shake_amount = 1.2, 1, 1, 0

# --- SİLAH SİSTEMİ (oturum boyunca kalıcı: bosslar yenilince açılır) ---
silah_kilitleri = {"taramali": False, "pompali": False}
secili_silah = "tabanca"
SILAH_ISIMLERI = {"tabanca": "TABANCA", "taramali": "TARAMALI", "pompali": "POMPALI"}
swordsmachine_replikler = [
    "STEEL DOES NOT FORGIVE!",
    "FEEL THE EDGE OF JUDGEMENT!",
    "NO MERCY FOR FLESH!"
]
SWORDMACHINE_RENK = (190, 190, 200)

# --- PARALLAX ARKA PLAN KATMANLARI (sabit tohumlu, sadece görsel; global rastgeleliği bozmaz) ---
_arka_rng = random.Random(1337)
_ARKA_ISIK_RENKLERI = [GABRIEL_MAVI, MOR, TURKUAZ, (255, 80, 180)]
ARKA_ISIK_KATMANI = [
    (_arka_rng.randint(0, 2400), _arka_rng.randint(60, 480), _arka_rng.randint(1, 3),
     _arka_rng.choice(_ARKA_ISIK_RENKLERI))
    for _ in range(45)
]
KOD_YAGMURU_SUTUNLARI = [
    (_arka_rng.randint(0, 2400), _arka_rng.uniform(80, 200))
    for _ in range(28)
]
_ARKA_TILE_GENISLIK = 2400

def arka_plan_ciz(kam_x):
    """Cyberpunk temalı iki katmanlı parallax arka plan: uzak şehir ışıkları (yavaş)
    ve dijital kod yağmuru (biraz daha hızlı + sürekli düşen animasyon)."""
    for (bx, by, boyut, renk) in ARKA_ISIK_KATMANI:
        ex = (bx - kam_x * 0.15) % _ARKA_TILE_GENISLIK
        if 0 <= ex <= EN:
            pygame.draw.circle(ekran, renk, (int(ex), by), boyut)

    su_an_t = time.time()
    for (bx, hiz) in KOD_YAGMURU_SUTUNLARI:
        ex = (bx - kam_x * 0.35) % _ARKA_TILE_GENISLIK
        if 0 <= ex <= EN:
            y_off = int((su_an_t * hiz) % (BOY + 60)) - 60
            pygame.draw.line(ekran, (0, 120, 60), (int(ex), y_off), (int(ex), y_off + 40), 2)

def scanline_ciz():
    if not ayarlar["performans_modu"]:
        for y in range(0, BOY, 4): pygame.draw.line(ekran, (0, 0, 0), (0, y), (EN, y))

def harita_getir(no):
    # Boss arenaları dar ve sabit kalır (kamera onlarda gezmez)
    if no == 15 or no == 26 or no == 30:
        zemin = pygame.Rect(0, 550, EN, 50)
        p2 = pygame.Rect(470, 380, 180, 20)
        return [zemin, pygame.Rect(150, 380, 180, 20), p2], p2

    # Normal bölümler geniş dünyada (DUNYA_EN) yayılır -> kamera keşif hissi için gezer
    zemin = pygame.Rect(0, 550, DUNYA_EN, 50)

    # Her sektör ailesine (5 şablon) kendine has bir yerleşim düzeni ve his veriliyor.
    sablon_no = (no - 1) % 5

    if sablon_no == 0:  # MERDİVEN: yükselen basamaklar
        taslak = [(120,480,150,20), (400,420,150,20), (680,350,150,20), (960,280,150,20), (1250,200,140,20)]
    elif sablon_no == 1:  # ADALAR: dağınık, dengesiz irili ufaklı platformlar
        taslak = [(80,500,120,20), (350,440,100,20), (600,500,130,20), (900,400,100,20), (1150,460,120,20), (1400,380,120,20)]
    elif sablon_no == 2:  # ZİGZAG: hızlı alçalıp yükselen ritim
        taslak = [(150,300,140,20), (420,470,140,20), (700,300,140,20), (980,470,140,20), (1260,300,140,20)]
    elif sablon_no == 3:  # KULE: başta dik tırmanış, sonra uzun düz koşu
        taslak = [(150,480,100,20), (180,400,100,20), (220,320,100,20), (260,250,100,20), (600,250,600,20)]
    else:  # AÇIK ALAN: az ama uzun platformlar, hız ve kamera hissi ön planda
        taslak = [(200,420,300,20), (700,420,300,20), (1200,350,300,20)]

    # Aynı şablon içinde de bölümler birbirinin aynı olmasın diye hafif bir kayma (jitter) ekleniyor
    kaymax = (no * 37) % 50
    kaymay = (no * 13) % 25
    platformlar = [zemin] + [pygame.Rect(x + kaymax, max(150, y - kaymay), w, h) for (x, y, w, h) in taslak]
    hedef_platform = platformlar[-1]  # şablonun son (asıl) platformu -> kazanma küpü her zaman burada olacak

    # Her 4 bölümden birine ekstra bir platform ekleyerek biraz daha çeşitlilik katılıyor
    if no % 4 == 0:
        seed_val = no * 45
        y4 = 320 - ((no * 13) % 4) * 20
        platformlar.append(pygame.Rect(((seed_val * 5) % 700) + 400, y4, 100, 18))
    return platformlar, hedef_platform

# --- BÖLÜM (SEKTÖR) TEMALARI: Her bölüm grubu farklı bir renk paleti ve isimle ayırt edilir ---
SEKTOR_TEMALARI = [
    {"ad": "CRIMSON SEKTOR",  "platform": (140, 20, 20),  "vurgu": PARLAK_KIRMIZI, "arka_fon": (16, 4, 4)},
    {"ad": "AZURE SEKTOR",    "platform": (15, 55, 120),  "vurgu": TURKUAZ,        "arka_fon": (3, 8, 18)},
    {"ad": "VIOLET SEKTOR",   "platform": (75, 15, 110),  "vurgu": MOR,            "arka_fon": (12, 3, 18)},
    {"ad": "TOXIC SEKTOR",    "platform": (15, 90, 30),   "vurgu": YESIL,          "arka_fon": (3, 14, 5)},
    {"ad": "SOLAR SEKTOR",    "platform": (130, 100, 10), "vurgu": SARI,           "arka_fon": (16, 12, 2)},
]

def sektor_getir(no):
    return SEKTOR_TEMALARI[(no - 1) % len(SEKTOR_TEMALARI)]

def rank_hesapla(gecen_sure):
    if gecen_sure < 8: return ("S", MOR)
    elif gecen_sure < 14: return ("A", PARLAK_KIRMIZI)
    elif gecen_sure < 22: return ("B", SARI)
    elif gecen_sure < 32: return ("C", MAVI)
    else: return ("D", GRI)

def stil_seviyesi(puan):
    """Stil puanına göre kombo rütbesi döndürür (isim, renk)."""
    if puan >= 160: return ("ULTRAKILL", MOR)
    elif puan >= 100: return ("RESPLENDENT", TURKUAZ)
    elif puan >= 50: return ("DESTRUCTIVE", PARLAK_KIRMIZI)
    elif puan >= 20: return ("STYLISH", SARI)
    else: return ("", GRI)

gabriel_replikler = [
    "BEHOLD THE POWER OF AN ANGEL!",
    "MACHINE, I WILL CUT YOU DOWN!",
    "YOU ARE LESS THAN NOTHING!"
]

minos_replikler = [
    "JUDGEMENT!",
    "THY END IS NOW!",
    "DIE!",
    "CRUSH!"
]

def balon_ciz(metin, x, y, arka_renk):
    txt = font_konusma.render(metin, True, SIYAH)
    b_en, b_boy = txt.get_width() + 14, txt.get_height() + 10
    bx, by = x - b_en // 2, y - b_boy - 15
    bx = max(10, min(EN - b_en - 10, bx))
    pygame.draw.rect(ekran, arka_renk, (bx, by, b_en, b_boy), 0, 4)
    pygame.draw.rect(ekran, BEYAZ, (bx, by, b_en, b_boy), 1, 4)
    ekran.blit(txt, (bx + 7, by + 5))

# --- MENÜ SİSTEMLERİ ---
def ana_menu():
    while True:
        muzik_cal("menu.mp3")
        ekran.fill(SIYAH); L = metinler[ayarlar["dil"]]; fare = fare_konumu()
        baslik = font_baslik.render("ULTRAPARKOUR", True, PARLAK_KIRMIZI)
        ekran.blit(baslik, (EN//2 - baslik.get_width()//2, 120))
        
        btns = [pygame.Rect(300, 220, 200, 38), pygame.Rect(300, 264, 200, 38), pygame.Rect(300, 308, 200, 38), pygame.Rect(300, 352, 200, 38), pygame.Rect(300, 396, 200, 38), pygame.Rect(300, 440, 200, 38)]
        txts = [L["basla"], "CYBERGRIND", "ÇEVRİMİÇİ", L["yenilikler"], L["ayarlar"], L["cikis"]]
        
        for r, t in zip(btns, txts):
            hov = r.collidepoint(fare); c = MOR if (t == "CYBERGRIND" and hov) else (TURKUAZ if (t == "ÇEVRİMİÇİ" and hov) else (PARLAK_KIRMIZI if hov else GRI))
            pygame.draw.rect(ekran, c, r, 2)
            ts = font_buton.render(t, True, c)
            ekran.blit(ts, (r.centerx - ts.get_width()//2, r.centery - 11))
            
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11: tam_ekran_ac_kapa()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: pygame.quit(); sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if btns[0].collidepoint(fare): secim_ekrani()
                if btns[1].collidepoint(fare): cybergrind_dongusu()
                if btns[2].collidepoint(fare): mp_menu()
                if btns[3].collidepoint(fare): yenilikler_sayfasi()
                if btns[4].collidepoint(fare): ayarlar_menusu()
                if btns[5].collidepoint(fare): pygame.quit(); sys.exit()
        scanline_ciz(); ekrani_guncelle()

def ayarlar_menusu():
    while True:
        ekran.fill(SIYAH); L = metinler[ayarlar["dil"]]; fare = fare_konumu(); tik = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11: tam_ekran_ac_kapa()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: return
            if event.type == pygame.MOUSEBUTTONDOWN: tik = True
        
        btn_dil = pygame.Rect(450, 195, 120, 40); btn_mod = pygame.Rect(450, 275, 120, 40); btn_tam = pygame.Rect(450, 355, 120, 40); btn_geri = pygame.Rect(300, 450, 200, 50)
        
        ekran.blit(font_buton.render(L["dil_sec"], True, BEYAZ), (100, 200))
        pygame.draw.rect(ekran, TURKUAZ, btn_dil, 2)
        ekran.blit(font_buton.render(ayarlar["dil"], True, TURKUAZ), (btn_dil.centerx-20, btn_dil.centery-10))
        if tik and btn_dil.collidepoint(fare): ayarlar["dil"] = "TR" if ayarlar["dil"] == "EN" else "EN"
            
        ekran.blit(font_buton.render(L["mod_sec"], True, BEYAZ), (100, 280))
        mod_r = YESIL if ayarlar["performans_modu"] else PARLAK_KIRMIZI
        pygame.draw.rect(ekran, mod_r, btn_mod, 2)
        ekran.blit(font_buton.render(L["on"] if ayarlar["performans_modu"] else L["off"], True, mod_r), (btn_mod.centerx-20, btn_mod.centery-10))
        if tik and btn_mod.collidepoint(fare): ayarlar["performans_modu"] = not ayarlar["performans_modu"]

        ekran.blit(font_buton.render("TAM EKRAN (F11)", True, BEYAZ), (100, 360))
        tam_r = YESIL if tam_ekran_mi else PARLAK_KIRMIZI
        pygame.draw.rect(ekran, tam_r, btn_tam, 2)
        ekran.blit(font_buton.render(L["on"] if tam_ekran_mi else L["off"], True, tam_r), (btn_tam.centerx-20, btn_tam.centery-10))
        if tik and btn_tam.collidepoint(fare): tam_ekran_ac_kapa()
            
        pygame.draw.rect(ekran, BEYAZ, btn_geri, 2)
        ekran.blit(font_buton.render(L["geri"], True, BEYAZ), (btn_geri.centerx-30, btn_geri.centery-10))
        if tik and btn_geri.collidepoint(fare): return
        scanline_ciz(); ekrani_guncelle()

def yenilikler_sayfasi():
    basliklar = [
        ("DİNAMİK KAMERA", TURKUAZ, [
            "Kamera artık oyuncuyu yumuşak bir Lerp ile takip ediyor.",
            "Normal bölümler ekrandan daha geniş bir dünyada geçiyor,",
            "keşif hissi için kazanma noktası haritanın diğer ucunda."
        ]),
        ("PARALLAX ARKA PLAN", MOR, [
            "Cyberpunk temalı iki katmanlı arka plan eklendi:",
            "yavaş kayan şehir ışıkları + dijital kod yağmuru."
        ]),
        ("KUYRUK (TRAIL) EFEKTİ", SARI, [
            "Koşarken veya havadayken arkanda ince, sararan",
            "bir gölge izi bırakıyorsun."
        ]),
        ("STİL PUANI KOMBOLARI", PARLAK_KIRMIZI, [
            "Parry, düşman öldürme ve friendly-fire ile stil puanı kazanılıyor.",
            "STYLISH -> DESTRUCTIVE -> RESPLENDENT -> ULTRAKILL rütbeleri",
            "ekranda büyür ve HUD'da canlı bir stil barı gösterilir."
        ]),
        ("BOSS CAN BARI YENİLENDİ", YESIL, [
            "Uçlarında siber çentik çizgileri ve hasar aldıkça yavaşça",
            "inen sarımsı bir 'hasar gölgesi' bar eklendi."
        ]),
        ("SİLAH SİSTEMİ", TURKUAZ, [
            "Tabanca, Taramalı ve Pompalı silahlar arasında geçiş yapılabiliyor (1/2/3).",
            "Taramalı: Gabriel'i (Bölüm 15) yenince açılır.",
            "Pompalı: yeni mini-boss Swordsmachine'i (Bölüm 26) yenince açılır."
        ]),
        ("CYBERGRIND MODU", MOR, [
            "Ana menüden erişilen sonsuz hayatta kalma modu.",
            "Roundlar ilerledikçe düşman sayısı ve ateş hızı artar,",
            "her 5 roundda Gabriel / Swordsmachine / Minos Prime karışımı bir boss gelir."
        ]),
    ]

    while True:
        ekran.fill(SIYAH); L = metinler[ayarlar["dil"]]; fare = fare_konumu()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11: tam_ekran_ac_kapa()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: return
            if event.type == pygame.MOUSEBUTTONDOWN:
                btn_geri = pygame.Rect(300, BOY - 50, 200, 40)
                if btn_geri.collidepoint(fare): return

        baslik = font_buton.render("YENİLİKLER", True, PARLAK_KIRMIZI)
        ekran.blit(baslik, (EN//2 - baslik.get_width()//2, 20))

        y = 55
        for ad, renk, satirlar in basliklar:
            ekran.blit(font_buton.render(f"» {ad}", True, renk), (40, y))
            y += 20
            for s in satirlar:
                ekran.blit(font_ui.render(s, True, BEYAZ), (60, y))
                y += 16
            y += 4

        pygame.draw.line(ekran, GRI, (30, y + 2), (EN - 30, y + 2), 1)
        y += 14
        sosyal = font_ui.render("Github: hosmerim    YouTube: HosmerimBasar    Instagram: hosmerimbasar", True, TURKUAZ)
        ekran.blit(sosyal, (EN//2 - sosyal.get_width()//2, y))

        btn_geri = pygame.Rect(300, BOY - 50, 200, 40)
        hov = btn_geri.collidepoint(fare); c = PARLAK_KIRMIZI if hov else GRI
        pygame.draw.rect(ekran, c, btn_geri, 2)
        gt = font_buton.render(L["geri"], True, c)
        ekran.blit(gt, (btn_geri.centerx - gt.get_width()//2, btn_geri.centery - 11))

        scanline_ciz(); ekrani_guncelle()

def secim_ekrani():
    global zorluk_hizi, secili_harita, dusman_sayisi
    sayfa = 0
    while True:
        muzik_cal("menu.mp3")
        ekran.fill(SIYAH); L = metinler[ayarlar["dil"]]; fare = fare_konumu(); tik = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11: tam_ekran_ac_kapa()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: return
            if event.type == pygame.MOUSEBUTTONDOWN: tik = True
        
        def d_btn(txt, x, y, spd, cnt, cur_spd, cur_cnt, clr=YESIL, w=140):
            r = pygame.Rect(x, y, w, 40); act = (spd == cur_spd and cnt == cur_cnt)
            c = clr if act else (BEYAZ if r.collidepoint(fare) else GRI)
            if act: pygame.draw.rect(ekran, c, r)
            else: pygame.draw.rect(ekran, c, r, 2)
            ts = font_ui.render(txt, True, SIYAH if act else c)
            ekran.blit(ts, (r.centerx-ts.get_width()//2, r.centery-8))
            return (spd, cnt) if tik and r.collidepoint(fare) else (None, None)

        ekran.blit(font_ui.render(L["zorluk"], True, PARLAK_KIRMIZI), (50, 40))
        for i, (t, s, n, cl) in enumerate([(L["kolay"], 1.2, 1, YESIL), (L["orta"], 1.2, 2, SARI), (L["zor"], 1.2, 3, PARLAK_KIRMIZI), (L["extreme"], 4.5, 3, MOR)]):
            res = d_btn(t, 50 + i*180, 70, s, n, zorluk_hizi, dusman_sayisi, cl, 160)
            if res[0]: zorluk_hizi, dusman_sayisi = res

        ekran.blit(font_ui.render(L["sektor"], True, TURKUAZ), (50, 130))
        
        btn_s1 = pygame.Rect(550, 125, 100, 30); btn_s2 = pygame.Rect(660, 125, 100, 30)
        pygame.draw.rect(ekran, TURKUAZ if sayfa==0 else GRI, btn_s1, 1 if sayfa!=0 else 2)
        pygame.draw.rect(ekran, TURKUAZ if sayfa==1 else GRI, btn_s2, 1 if sayfa!=1 else 2)
        ekran.blit(font_ui.render("1 - 15", True, TURKUAZ if sayfa==0 else GRI), (575, 132))
        ekran.blit(font_ui.render("16 - 30", True, TURKUAZ if sayfa==1 else GRI), (680, 132))
        if tik and btn_s1.collidepoint(fare): sayfa = 0
        if tik and btn_s2.collidepoint(fare): sayfa = 1

        start_map = 1 if sayfa == 0 else 16
        for idx in range(15):
            i = start_map + idx
            row, col = divmod(idx, 5)
            isim = "GABRIEL" if i == 15 else ("SWORDMACH." if i == 26 else ("MINOS PRIME" if i == 30 else f"MAP {i}"))
            clr_box = MOR if i == 15 else (TURNCU if i == 26 else (PARLAK_KIRMIZI if i == 30 else sektor_getir(i)["vurgu"]))
            if d_btn(isim, 40 + col*150, 170 + row*55, i, 0, secili_harita, 0, clr_box, 140)[0]: secili_harita = i

        btn_go = pygame.Rect(300, 480, 200, 50); pygame.draw.rect(ekran, YESIL, btn_go, 2)
        ekran.blit(font_buton.render(L["deploy"], True, YESIL), (330, 492))
        if tik and btn_go.collidepoint(fare): oyun_dongusu()
        scanline_ciz(); ekrani_guncelle()

# --- OYUN DÖNGÜSÜ ---
def oyun_dongusu():
    global shake_amount, secili_harita, parcaciklar, secili_silah
    parcaciklar = [] 
    oyuncu = pygame.Rect(50, 500, 30, 30); oyuncu_y_hiz = 0; oyuncu_yerde = False
    ziplama_hakki, dj_aktif, son_dj, son_ates = 0, False, 0, 0
    son_ziplama_girdisi = 0  # Aynı basışın iki kez işlenmesini önlemek için (debounce)
    mermiler, sari_kureler = [], []
    
    parry_radius = 65
    style_yazilar = []
    dusman_mermileri = []
    kuyruk = []  # Kuyruk/gölge (trail) efekti için geçmiş pozisyonlar

    is_gabriel = (secili_harita == 15)
    is_minos = (secili_harita == 30)
    is_swordsmachine = (secili_harita == 26)
    is_boss = is_gabriel or is_minos or is_swordsmachine

    # Boss arenaları dar ve sabit kalır; normal bölümler geniş dünyada geçer (kamera gezer)
    world_en = EN if is_boss else DUNYA_EN
    kam_x = 0.0  # Kamera pozisyonu (Lerp ile yumuşak takip)

    # Bölüme özgü görsel tema (platform rengi, arka plan tonu, sektör adı)
    sektor = sektor_getir(secili_harita) if not is_boss else {"ad": "BOSS ARENA", "platform": (140, 20, 20), "vurgu": PARLAK_KIRMIZI, "arka_fon": (0, 0, 0)}

    # Stil puanı kombo sistemi
    stil_puani = 0.0
    stil_onceki_seviye = ""

    # --- SEVİYE İLERLEDİKÇE ZORLAŞTIRMA ---
    # Bölüm numarası büyüdükçe düşman/boss hızı ve ateş sıklığı kademeli olarak artar.
    seviye_carpani = 1 + (secili_harita - 1) * 0.04
    efektif_hiz = zorluk_hizi * seviye_carpani
    efektif_ates_araligi = max(1.0, 2.5 - (secili_harita - 1) * 0.05)

    boss = {
        'rect': pygame.Rect(400, 100, 50, 50) if is_boss else None,
        'max_can': 100 if is_gabriel else (150 if is_swordsmachine else 250),
        'can': 100 if is_gabriel else (150 if is_swordsmachine else 250),
        'golge_can': 100 if is_gabriel else (150 if is_swordsmachine else 250),
        'y_hiz': 0,
        'yerde': False,
        'is_dead': False,
        'son_isinlanma': 0,
        'son_saldiri': 0,
        'replik': "",
        'replik_bitis': 0,
        'minos_atiliyor': False,
        'atilim_yonu': 0,
        'atilim_bitis': 0
    }

    spawn_noktalari = [(1500, 100), (800, 50), (100, 50)]
    dusman_turleri = ['nobetci', 'kovalayici', 'teleporter']
    dusmanlar = [] if is_boss else [
        {
            'id': idx,
            'rect': pygame.Rect(sp[0], sp[1], 30, 30), 
            'spawn': sp, 'y_hiz': 0, 'yerde': False, 
            'hayatta': True, 'olum_zamani': 0,
            'son_ates': 0, 'son_isinlanma': 0, 'tur': dusman_turleri[(secili_harita + idx) % 3]
        } for idx, sp in enumerate(spawn_noktalari[:dusman_sayisi])
    ]
    
    platformlar, hedef_platform = harita_getir(secili_harita)
    if not is_boss:
        # Kazanma küpü her zaman şablonun asıl son platformunun üstüne konur (bonus platform hariç);
        # böylece hangi şablon seçilirse seçilsin küp her zaman ulaşılabilir olur.
        kazanma_kupu = pygame.Rect(hedef_platform.centerx - 20, max(60, hedef_platform.y - 70), 40, 40)
    else:
        kazanma_kupu = pygame.Rect(world_en - 100, 50, 40, 40)

    # Bölüm numarasına göre oyun1/oyun2/oyun3.mp3 arasında sırayla geçiş yap
    oyun_muzikleri = ["oyun1.mp3", "oyun2.mp3", "oyun3.mp3"]
    muzik_cal(oyun_muzikleri[(secili_harita - 1) % 3])
    
    # Geri Sayım Sahnesi
    start_t = time.time(); last_sec = 4
    while time.time() - start_t < 3:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11: tam_ekran_ac_kapa()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: return
        ekran.fill(SIYAH); kalan = 3 - int(time.time() - start_t)
        if kalan < last_sec: shake_amount = 30; last_sec = kalan
        pulse = 1.0 + 0.3 * math.sin(time.time() * 20)
        s_ox, s_oy = random.randint(-int(shake_amount), int(shake_amount)), random.randint(-int(shake_amount), int(shake_amount))
        shake_amount *= 0.8
        
        txt = font_countdown_base.render(str(kalan), True, SARI if kalan > 1 else PARLAK_KIRMIZI)
        if pulse != 1.0:
            txt = pygame.transform.scale(txt, (int(txt.get_width()*pulse), int(txt.get_height()*pulse)))
            
        ekran.blit(txt, (EN//2 - txt.get_width()//2 + s_ox, BOY//2 - txt.get_height()//2 + s_oy))
        scanline_ciz(); ekrani_guncelle(); saat.tick(60)

    oyun_baslangic_zamani = time.time()

    while True:
        su_an = time.time()
        gecen_sure = su_an - oyun_baslangic_zamani
        
        silah_beklemeleri = {"tabanca": 3, "taramali": 0.12, "pompali": 1.1}
        ates_cd, dj_cd = max(0, silah_beklemeleri.get(secili_silah, 3)-(su_an-son_ates)), max(0, 1-(su_an-son_dj))
        
        mermi_yakinda = False
        for dm in dusman_mermileri:
            if not dm.get('parried', False):
                mesafe = math.hypot(dm['rect'].centerx - oyuncu.centerx, dm['rect'].centery - oyuncu.centery)
                if mesafe <= parry_radius:
                    mermi_yakinda = True
                    break

        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11: tam_ekran_ac_kapa()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_w:
                    if su_an - son_ziplama_girdisi > 0.1:  # 100ms'den önce gelen ikinci basışı yok say
                        if oyuncu_yerde: oyuncu_y_hiz, oyuncu_yerde, ziplama_hakki = -15, False, 1
                        elif dj_aktif and ziplama_hakki == 1 and dj_cd == 0: oyuncu_y_hiz, ziplama_hakki, son_dj = -15, 2, su_an
                        son_ziplama_girdisi = su_an

                # --- SİLAH SEÇİMİ (1: Tabanca, 2: Taramalı, 3: Pompalı) ---
                if event.key == pygame.K_1: secili_silah = "tabanca"
                if event.key == pygame.K_2:
                    if silah_kilitleri["taramali"]: secili_silah = "taramali"
                    else: style_yazilar.append({'metin': "KİLİTLİ", 'x': EN - 180, 'y': 100, 'omur': 40, 'renk': GRI})
                if event.key == pygame.K_3:
                    if silah_kilitleri["pompali"]: secili_silah = "pompali"
                    else: style_yazilar.append({'metin': "KİLİTLİ", 'x': EN - 180, 'y': 100, 'omur': 40, 'renk': GRI})
                
                # --- PARRY SİSTEMİ (F TUŞU) ---
                if event.key == pygame.K_f:
                    for dm in dusman_mermileri:
                        if not dm.get('parried', False):
                            mesafe = math.hypot(dm['rect'].centerx - oyuncu.centerx, dm['rect'].centery - oyuncu.centery)
                            if mesafe <= parry_radius:
                                dm['parried'] = True
                                shake_amount = 15
                                stil_puani += 15  # Stil puanı: başarılı parry
                                if ses_atis: ses_atis.play()
                                parcacik_ekle(dm['rect'].centerx, dm['rect'].centery, SARI, 20)
                                style_yazilar.append({'metin': "+PARRY", 'x': EN - 180, 'y': 80, 'omur': 45, 'renk': TURKUAZ})
                                
                                if dm['tip'] == 'boss':
                                    b_aci = math.atan2(boss['rect'].centery - dm['rect'].centery, boss['rect'].centerx - dm['rect'].centerx)
                                    dm['vx'] = math.cos(b_aci) * 16
                                    dm['vy'] = math.sin(b_aci) * 16
                                else:
                                    dm['vx'] = -dm['vx'] * 2.5
                                    dm['vy'] = -dm['vy'] * 2.5
                                break

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and secili_silah in ("tabanca", "pompali") and ates_cd == 0:
                fx, fy = fare_konumu()
                # Fare pozisyonu ekran koordinatında, oyuncu ise dünya koordinatında (kamera kayıyor).
                # Açıyı doğru hesaplamak için fare x'ini dünya koordinatına çeviriyoruz.
                fx_dunya = fx + kam_x
                aci = math.atan2(fy - oyuncu.centery, fx_dunya - oyuncu.centerx)
                if secili_silah == "tabanca":
                    mermiler.append({'rect': pygame.Rect(oyuncu.centerx, oyuncu.centery, 10, 10), 'vx': math.cos(aci)*12, 'vy': math.sin(aci)*12, 'hasar': 10})
                    shake_amount = 5
                else:  # pompalı: konik saçma (5 parça)
                    for sapma in (-0.28, -0.14, 0, 0.14, 0.28):
                        a2 = aci + sapma
                        mermiler.append({'rect': pygame.Rect(oyuncu.centerx, oyuncu.centery, 8, 8), 'vx': math.cos(a2)*11, 'vy': math.sin(a2)*11, 'hasar': 6})
                    shake_amount = 14
                son_ates = su_an
                if ses_atis: ses_atis.play()
                parcacik_ekle(oyuncu.centerx, oyuncu.centery, TURKUAZ, 5)

        # --- TARAMALI SİLAH: basılı tutarak sürekli ateş ---
        if secili_silah == "taramali" and pygame.mouse.get_pressed()[0] and ates_cd == 0:
            fx, fy = fare_konumu()
            fx_dunya = fx + kam_x
            aci = math.atan2(fy - oyuncu.centery, fx_dunya - oyuncu.centerx)
            mermiler.append({'rect': pygame.Rect(oyuncu.centerx, oyuncu.centery, 8, 8), 'vx': math.cos(aci)*13, 'vy': math.sin(aci)*13, 'hasar': 4})
            son_ates = su_an; shake_amount = 3
            if ses_atis: ses_atis.play()
            parcacik_ekle(oyuncu.centerx, oyuncu.centery, TURKUAZ, 3)

        tus = pygame.key.get_pressed()
        hareket_ediyor = False
        if tus[pygame.K_a]: oyuncu.x -= 5; hareket_ediyor = True
        if tus[pygame.K_d]: oyuncu.x += 5; hareket_ediyor = True
        oyuncu.x = max(0, min(world_en-30, oyuncu.x)); oyuncu_y_hiz += 0.8; oyuncu.y += oyuncu_y_hiz
        if not oyuncu_yerde: hareket_ediyor = True

        # --- KUYRUK (TRAIL) EFEKTİ İZİ BIRAKMA ---
        if hareket_ediyor:
            kuyruk.append({'x': oyuncu.x, 'y': oyuncu.y, 'omur': 10})
            if len(kuyruk) > 14: kuyruk.pop(0)

        # --- KAMERA GÜNCELLEME (Lerp ile yumuşak takip) ---
        hedef_kam_x = max(0, min(world_en - EN, oyuncu.centerx - EN // 2))
        kam_x += (hedef_kam_x - kam_x) * 0.1

        # --- STİL PUANI ZAMANLA AZALIR ---
        stil_puani = max(0, stil_puani - 0.2)
        stil_isim_guncel, stil_renk_guncel = stil_seviyesi(stil_puani)
        if stil_isim_guncel != stil_onceki_seviye and stil_isim_guncel != "":
            style_yazilar.append({'metin': stil_isim_guncel, 'x': EN // 2, 'y': 130, 'omur': 55, 'renk': stil_renk_guncel, 'buyuk': True})
        stil_onceki_seviye = stil_isim_guncel
        
        # --- BOSS SİSTEMLERİ ---
        if is_boss and not boss['is_dead']:
            if is_gabriel:
                if su_an - boss['son_isinlanma'] > 2.0:
                    boss['rect'].x = random.randint(100, 700)
                    boss['rect'].y = random.randint(100, 300)
                    parcacik_ekle(boss['rect'].centerx, boss['rect'].centery, MOR, 20)
                    boss['son_isinlanma'] = su_an
                    if random.random() < 0.6:
                        boss['replik'] = random.choice(gabriel_replikler)
                        boss['replik_bitis'] = su_an + 1.5
                
                if su_an - boss['son_saldiri'] > 1.2:
                    b_aci = math.atan2(oyuncu.centery - boss['rect'].centery, oyuncu.centerx - boss['rect'].centerx)
                    dusman_mermileri.append({
                        'rect': pygame.Rect(boss['rect'].centerx, boss['rect'].centery, 12, 12),
                        'vx': math.cos(b_aci) * 6, 'vy': math.sin(b_aci) * 6,
                        'parried': False, 'tip': 'boss'
                    })
                    boss['son_saldiri'] = su_an

            elif is_swordsmachine:
                boss['y_hiz'] += 0.8
                boss['rect'].y += boss['y_hiz']

                if boss['minos_atiliyor']:
                    boss['rect'].x += boss['atilim_yonu'] * 18
                    if su_an > boss['atilim_bitis']:
                        boss['minos_atiliyor'] = False
                else:
                    if boss['rect'].centerx < oyuncu.centerx: boss['rect'].x += efektif_hiz * 1.3
                    else: boss['rect'].x -= efektif_hiz * 1.3

                    if su_an - boss['son_saldiri'] > 1.4:
                        zar = random.random()
                        if zar < 0.5:
                            b_aci = math.atan2(oyuncu.centery - boss['rect'].centery, oyuncu.centerx - boss['rect'].centerx)
                            dusman_mermileri.append({
                                'rect': pygame.Rect(boss['rect'].centerx, boss['rect'].centery, 14, 14),
                                'vx': math.cos(b_aci) * 8, 'vy': math.sin(b_aci) * 8,
                                'parried': False, 'tip': 'boss'
                            })
                        else:
                            boss['minos_atiliyor'] = True
                            boss['atilim_yonu'] = 1 if boss['rect'].centerx < oyuncu.centerx else -1
                            boss['atilim_bitis'] = su_an + 0.3
                        boss['replik'] = random.choice(swordsmachine_replikler); boss['replik_bitis'] = su_an + 1.2; boss['son_saldiri'] = su_an

                boss['rect'].x = max(0, min(EN-50, boss['rect'].x))

            elif is_minos:
                boss['y_hiz'] += 0.8
                boss['rect'].y += boss['y_hiz']
                
                if boss['minos_atiliyor']:
                    boss['rect'].x += boss['atilim_yonu'] * 15
                    if su_an > boss['atilim_bitis']:
                        boss['minos_atiliyor'] = False
                else:
                    if boss['rect'].centerx < oyuncu.centerx: boss['rect'].x += efektif_hiz
                    else: boss['rect'].x -= efektif_hiz
                    
                    if su_an - boss['son_saldiri'] > 1.5:
                        zar = random.random()
                        if zar < 0.5 and boss['yerde']:
                            boss['y_hiz'] = -16; boss['yerde'] = False
                            boss['replik'] = "JUDGEMENT!"; boss['replik_bitis'] = su_an + 1.2; boss['son_saldiri'] = su_an
                        elif zar >= 0.5:
                            boss['minos_atiliyor'] = True
                            boss['atilim_yonu'] = 1 if boss['rect'].centerx < oyuncu.centerx else -1
                            boss['atilim_bitis'] = su_an + 0.35
                            boss['replik'] = random.choice(minos_replikler); boss['replik_bitis'] = su_an + 1.2; boss['son_saldiri'] = su_an

                boss['rect'].x = max(0, min(EN-50, boss['rect'].x))

            if oyuncu.colliderect(boss['rect']):
                if ses_olme: ses_olme.play()
                bolum_sonu_menusu(False, gecen_sure)

        # --- NORMAL DÜŞMAN MANTIĞI (tür bazlı: nöbetçi / kovalayıcı / teleporter) ---
        if not is_boss:
            for d in dusmanlar:
                if d['hayatta']:
                    tur = d.get('tur', 'nobetci')
                    hiz_carpani = {'nobetci': 1.0, 'kovalayici': 1.8, 'teleporter': 0.0}.get(tur, 1.0)
                    d['y_hiz'] += 0.8; d['rect'].y += d['y_hiz']
                    d['rect'].x += (efektif_hiz * hiz_carpani) if d['rect'].centerx < oyuncu.centerx else -(efektif_hiz * hiz_carpani)
                    if d['yerde'] and (d['rect'].y > oyuncu.y + 40 or abs(d['rect'].x - oyuncu.x) < 50): d['y_hiz'] = -14.5; d['yerde'] = False

                    # Teleporter: yerinde saplanıp kalmasın diye periyodik olarak oyuncunun yakınına ışınlanır
                    if tur == 'teleporter' and su_an - d.get('son_isinlanma', 0) > 2.3:
                        parcacik_ekle(d['rect'].centerx, d['rect'].centery, MOR, 14)
                        d['rect'].x = max(0, min(world_en - 30, oyuncu.centerx + random.randint(-250, 250)))
                        d['rect'].y = random.randint(50, 400)
                        d['y_hiz'] = 0
                        d['son_isinlanma'] = su_an

                    if tur != 'kovalayici':  # Kovalayıcı ateş etmez, sadece temas ile öldürür
                        ates_araligi_bu = efektif_ates_araligi * (0.5 if tur == 'teleporter' else 1.0)
                        if su_an - d['son_ates'] > ates_araligi_bu:
                            d_aci = math.atan2(oyuncu.centery - d['rect'].centery, oyuncu.centerx - d['rect'].centerx)
                            hiz_mermi = 7 if tur == 'teleporter' else 5
                            dusman_mermileri.append({
                                'rect': pygame.Rect(d['rect'].centerx, d['rect'].centery, 10, 10),
                                'vx': math.cos(d_aci) * hiz_mermi, 'vy': math.sin(d_aci) * hiz_mermi,
                                'parried': False, 'tip': 'normal', 'sahip_id': d['id']
                            })
                            d['son_ates'] = su_an

                    if oyuncu.colliderect(d['rect']):
                        if ses_olme: ses_olme.play()
                        bolum_sonu_menusu(False, gecen_sure)
                elif su_an - d['olum_zamani'] >= 5: d['rect'].topleft, d['y_hiz'], d['hayatta'] = d['spawn'], 0, True

        # --- DÜŞMAN MERMİLERİ GÜNCELLEME ---
        for dm in dusman_mermileri[:]:
            dm['rect'].x += dm['vx']; dm['rect'].y += dm['vy']
            mermi_silindi = False
            
            if dm.get('parried', False):
                if is_boss and not boss['is_dead'] and dm['rect'].colliderect(boss['rect']):
                    boss['can'] -= 25
                    stil_puani += 25  # Stil puanı: boss'a friendly fire
                    parcacik_ekle(boss['rect'].centerx, boss['rect'].centery, SARI, 15)
                    style_yazilar.append({'metin': "+FRIED FRIENDLY FIRE", 'x': EN - 250, 'y': 110, 'omur': 45, 'renk': PARLAK_KIRMIZI})
                    if dm in dusman_mermileri: dusman_mermileri.remove(dm)
                    mermi_silindi = True
                    if boss['can'] <= 0:
                        boss['is_dead'] = True
                        parcacik_ekle(boss['rect'].centerx, boss['rect'].centery, SARI, 50)
                
                elif not is_boss and not mermi_silindi:
                    for d in dusmanlar:
                        if d['hayatta'] and dm['rect'].colliderect(d['rect']):
                            parcacik_ekle(d['rect'].centerx, d['rect'].centery, SARI, 15)
                            sari_kureler.append(pygame.Rect(d['rect'].x, d['rect'].y, 20, 20))
                            d['hayatta'], d['olum_zamani'] = False, su_an
                            stil_puani += 20  # Stil puanı: friendly fire öldürme
                            style_yazilar.append({'metin': "+FRIED FRIENDLY FIRE", 'x': EN - 250, 'y': 110, 'omur': 45, 'renk': PARLAK_KIRMIZI})
                            if dm in dusman_mermileri: dusman_mermileri.remove(dm)
                            mermi_silindi = True
                            break

            elif dm['rect'].colliderect(oyuncu) and not mermi_silindi:
                if ses_olme: ses_olme.play()
                bolum_sonu_menusu(False, gecen_sure)
                
            if not mermi_silindi:
                if dm['rect'].y > BOY or dm['rect'].y < 0 or dm['rect'].x < 0 or dm['rect'].x > world_en:
                    if dm in dusman_mermileri: dusman_mermileri.remove(dm)

        # Oyuncu Standart Ateş Sistemi
        for m in mermiler[:]:
            m['rect'].x += m['vx']; m['rect'].y += m['vy']
            if is_boss and not boss['is_dead'] and boss['rect'].colliderect(m['rect']):
                boss['can'] -= m.get('hasar', 10)
                stil_puani += 3  # Stil puanı: boss'a hasar
                parcacik_ekle(boss['rect'].centerx, boss['rect'].centery, GABRIEL_MAVI if is_gabriel else (SWORDMACHINE_RENK if is_swordsmachine else MINOS_MINT), 12)
                shake_amount = 6; mermiler.remove(m)
                if boss['can'] <= 0:
                    boss['is_dead'] = True; parcacik_ekle(boss['rect'].centerx, boss['rect'].centery, SARI, 50)
                continue

            for d in dusmanlar:
                if d['hayatta'] and d['rect'].colliderect(m['rect']):
                    parcacik_ekle(d['rect'].centerx, d['rect'].centery, PARLAK_KIRMIZI, 12)
                    sari_kureler.append(pygame.Rect(d['rect'].x, d['rect'].y, 20, 20))
                    d['hayatta'], d['olum_zamani'] = False, su_an
                    stil_puani += 10  # Stil puanı: doğrudan düşman öldürme
                    mermiler.remove(m); shake_amount = 10; break

        # Fizik Çarpışmaları (Zemin & Platform)
        oyuncu_yerde = False
        if is_boss and (is_minos or is_swordsmachine): boss['yerde'] = False
        
        for p in platformlar:
            if oyuncu.colliderect(p) and oyuncu_y_hiz > 0: oyuncu.bottom, oyuncu_y_hiz, oyuncu_yerde, ziplama_hakki = p.top, 0, True, 0
            if is_boss and (is_minos or is_swordsmachine):
                if boss['rect'].colliderect(p) and boss['y_hiz'] > 0: boss['rect'].bottom, boss['y_hiz'], boss['yerde'] = p.top, 0, True
            for d in dusmanlar:
                if d['hayatta'] and d['rect'].colliderect(p) and d['y_hiz'] > 0: d['rect'].bottom, d['y_hiz'], d['yerde'] = p.top, 0, True
        
        for k in sari_kureler[:]:
            if oyuncu.colliderect(k): dj_aktif = True; sari_kureler.remove(k); parcacik_ekle(oyuncu.centerx, oyuncu.centery, SARI, 10)
        
        if is_boss:
            if boss['is_dead']: bolum_sonu_menusu(True, gecen_sure)
        else:
            if oyuncu.colliderect(kazanma_kupu): bolum_sonu_menusu(True, gecen_sure)

        if oyuncu.y > BOY: 
            if ses_olme: ses_olme.play()
            bolum_sonu_menusu(False, gecen_sure)

        # --- ÇİZİM SAHNESİ ---
        ekran.fill(sektor["arka_fon"])
        arka_plan_ciz(kam_x)
        shake_ox, shake_oy = random.randint(-int(shake_amount), int(shake_amount)), random.randint(-int(shake_amount), int(shake_amount))
        shake_amount *= 0.9
        ox, oy = int(-kam_x) + shake_ox, shake_oy

        for p in platformlar: pygame.draw.rect(ekran, sektor["platform"], (p.x+ox, p.y+oy, p.w, p.h))
        
        parcacik_guncelle()

        # --- KUYRUK (TRAIL) İZLERİNİ ÇİZ (oyuncudan önce, arkasında kalsın) ---
        for iz in kuyruk[:]:
            iz['omur'] -= 1
            if iz['omur'] <= 0:
                kuyruk.remove(iz)
            else:
                alfa = int(140 * (iz['omur'] / 10))
                iz_yuzey = pygame.Surface((8, 30), pygame.SRCALPHA)
                iz_yuzey.fill((255, 255, 0, alfa))
                ekran.blit(iz_yuzey, (iz['x'] + 11 + ox, iz['y'] + oy))

        if resim_yuklendi: ekran.blit(V1_GORSEL, (oyuncu.x+ox, oyuncu.y+oy))
        else: pygame.draw.rect(ekran, YESIL, (oyuncu.x+ox, oyuncu.y+oy, 30, 30))
        
        if mermi_yakinda:
            pygame.draw.circle(ekran, SARI, (oyuncu.centerx + ox, oyuncu.centery + oy), parry_radius, 2)
            
        if not is_boss:
            for d in dusmanlar:
                if d['hayatta']:
                    tur_renk = {'nobetci': PARLAK_KIRMIZI, 'kovalayici': TURNCU, 'teleporter': MOR}.get(d.get('tur', 'nobetci'), PARLAK_KIRMIZI)
                    pygame.draw.rect(ekran, tur_renk, (d['rect'].x+ox, d['rect'].y+oy, 30, 30))
            pygame.draw.rect(ekran, MAVI, (kazanma_kupu.x+ox, kazanma_kupu.y+oy, 40, 40))
        
        for dm in dusman_mermileri:
            m_renk = SARI if dm.get('parried', False) else (MOR if dm['tip'] == 'boss' else TURNCU)
            pygame.draw.circle(ekran, m_renk, (dm['rect'].centerx+ox, dm['rect'].centery+oy), 6)

        if is_boss and not boss['is_dead']:
            boss_renk = GABRIEL_MAVI if is_gabriel else (SWORDMACHINE_RENK if is_swordsmachine else MINOS_MINT)
            pygame.draw.rect(ekran, boss_renk, (boss['rect'].x+ox, boss['rect'].y+oy, 50, 50))
            
            if is_gabriel:
                pygame.draw.line(ekran, BEYAZ, (boss['rect'].left+ox, boss['rect'].centery+oy), (boss['rect'].left-30+ox, boss['rect'].top-20+oy), 4)
                pygame.draw.line(ekran, BEYAZ, (boss['rect'].right+ox, boss['rect'].centery+oy), (boss['rect'].right+30+ox, boss['rect'].top-20+oy), 4)
            elif is_swordsmachine:
                pygame.draw.circle(ekran, PARLAK_KIRMIZI, (boss['rect'].centerx+ox, boss['rect'].centery+oy), 7)
                if boss['minos_atiliyor']:
                    pygame.draw.line(ekran, BEYAZ, (boss['rect'].centerx - (boss['atilim_yonu']*60)+ox, boss['rect'].centery+oy), (boss['rect'].centerx+ox, boss['rect'].centery+oy), 5)
                else:
                    pygame.draw.line(ekran, BEYAZ, (boss['rect'].right+ox, boss['rect'].top+oy), (boss['rect'].right+25+ox, boss['rect'].bottom+oy), 4)
            else:
                pygame.draw.circle(ekran, SIYAH, (boss['rect'].centerx+ox, boss['rect'].centery+oy), 7)
                if boss['minos_atiliyor']:
                    pygame.draw.rect(ekran, SARI, (boss['rect'].x + ox - (boss['atilim_yonu']*15), boss['rect'].y + oy, 50, 50), 3)
                    pygame.draw.line(ekran, SARI, (boss['rect'].centerx - (boss['atilim_yonu']*70)+ox, boss['rect'].centery+oy), (boss['rect'].centerx+ox, boss['rect'].centery+oy), 6)

            # --- YENİLENMİŞ BOSS CAN BARI: hasar gölgesi + siber uç çizgileri ---
            if boss['golge_can'] > boss['can']:
                boss['golge_can'] = max(boss['can'], boss['golge_can'] - 0.6)
            b_bar_x, b_bar_y, b_bar_w, b_bar_h = 200, 30, 400, 15
            oran_can = boss['can'] / boss['max_can']
            oran_golge = boss['golge_can'] / boss['max_can']
            pygame.draw.rect(ekran, GRI, (b_bar_x, b_bar_y, b_bar_w, b_bar_h))
            pygame.draw.rect(ekran, (235, 235, 160), (b_bar_x, b_bar_y, b_bar_w * oran_golge, b_bar_h))
            bar_renk = MOR if is_gabriel else (GRI if is_swordsmachine else PARLAK_KIRMIZI)
            pygame.draw.rect(ekran, bar_renk, (b_bar_x, b_bar_y, b_bar_w * oran_can, b_bar_h))
            pygame.draw.rect(ekran, BEYAZ, (b_bar_x, b_bar_y, b_bar_w, b_bar_h), 1)
            pygame.draw.line(ekran, BEYAZ, (b_bar_x - 12, b_bar_y - 6), (b_bar_x, b_bar_y + b_bar_h + 6), 2)
            pygame.draw.line(ekran, BEYAZ, (b_bar_x + b_bar_w + 12, b_bar_y - 6), (b_bar_x + b_bar_w, b_bar_y + b_bar_h + 6), 2)
            b_adi = "GABRIEL, JUDGE OF HELL" if is_gabriel else ("SWORDSMACHINE" if is_swordsmachine else "MINOS PRIME")
            b_isim = font_ui.render(b_adi, True, BEYAZ)
            ekran.blit(b_isim, (EN//2 - b_isim.get_width()//2, 10))

            if boss['replik'] and su_an < boss['replik_bitis']:
                balon_ciz(boss['replik'], boss['rect'].centerx + ox, boss['rect'].top + oy, BEYAZ if is_gabriel else (SWORDMACHINE_RENK if is_swordsmachine else MINOS_MINT))

        for k in sari_kureler: pygame.draw.ellipse(ekran, SARI, (k.x+ox, k.y+oy, k.w, k.h))
        for m in mermiler: pygame.draw.rect(ekran, TURKUAZ, (m['rect'].x+ox, m['rect'].y+oy, 10, 10))
        
        pygame.draw.rect(ekran, GRI, (20, 20, 150, 10)); pygame.draw.rect(ekran, TURKUAZ, (20, 20, 150*(1-ates_cd/3), 10))
        if dj_aktif: pygame.draw.rect(ekran, GRI, (20, 40, 150, 10)); pygame.draw.rect(ekran, SARI, (20, 40, 150*(1-dj_cd/1), 10))

        sektor_yazi = font_ui.render(sektor["ad"], True, sektor["vurgu"])
        silah_hud = font_ui.render(f"SILAH: {SILAH_ISIMLERI.get(secili_silah,'TABANCA')}  [1][2][3]", True, SARI)
        ekran.blit(silah_hud, (20, 58))
        ekran.blit(sektor_yazi, (20, BOY - 30))

        s_metin = font_ui.render(f"TIME: {gecen_sure:.2f}s", True, BEYAZ)
        r_harf, r_renk = rank_hesapla(gecen_sure)
        r_metin = font_ui.render(f"RANK: {r_harf}", True, r_renk)
        ekran.blit(s_metin, (EN - 150, 20))
        ekran.blit(r_metin, (EN - 150, 40))

        # --- STİL PUANI BARI (HUD) ---
        stil_bar_oran = min(1.0, stil_puani / 200)
        stil_bar_renk = stil_renk_guncel if stil_isim_guncel != "" else GRI
        pygame.draw.rect(ekran, GRI, (EN - 150, 62, 130, 8))
        pygame.draw.rect(ekran, stil_bar_renk, (EN - 150, 62, 130 * stil_bar_oran, 8))
        if stil_isim_guncel:
            etiket = font_ui.render(stil_isim_guncel, True, stil_bar_renk)
            ekran.blit(etiket, (EN - 150, 74))

        for st in style_yazilar[:]:
            buyuk = st.get('buyuk', False)
            f = font_stil_buyuk if buyuk else font_style
            txt_s = f.render(st['metin'], True, st['renk'])
            bx = st['x'] - txt_s.get_width() // 2 if buyuk else st['x']
            ekran.blit(txt_s, (bx, st['y']))
            st['y'] -= 0.6 if buyuk else 0.5
            st['omur'] -= 1
            if st['omur'] <= 0: style_yazilar.remove(st)

        scanline_ciz(); ekrani_guncelle(); saat.tick(60)

def bolum_sonu_menusu(kazandi, final_sure):
    global secili_harita
    yeni_silah_mesaji = None
    if kazandi:
        if secili_harita == 15 and not silah_kilitleri["taramali"]:
            silah_kilitleri["taramali"] = True; yeni_silah_mesaji = "YENİ SİLAH AÇILDI: TARAMALI SİLAH! (Tuş: 2)"
        elif secili_harita == 26 and not silah_kilitleri["pompali"]:
            silah_kilitleri["pompali"] = True; yeni_silah_mesaji = "YENİ SİLAH AÇILDI: POMPALI SİLAH! (Tuş: 3)"
    while True:
        ekran.fill(SIYAH); L = metinler[ayarlar["dil"]]
        
        if kazandi:
            txt = "JUDGEMENT CRUSHED!" if secili_harita == 30 else L["bitti"]
            t_s = font_baslik.render(txt, True, YESIL if secili_harita != 30 else SARI)
            ekran.blit(t_s, (EN//2 - t_s.get_width()//2, 80))
            
            rank, r_renk = rank_hesapla(final_sure)
            rank_ts = font_rank.render(rank, True, r_renk)
            sure_ts = font_buton.render(f"FINAL TIME: {final_sure:.2f} SECONDS", True, BEYAZ)
            
            ekran.blit(rank_ts, (EN//2 - rank_ts.get_width()//2, 170))
            ekran.blit(sure_ts, (EN//2 - sure_ts.get_width()//2, 270))

            if yeni_silah_mesaji:
                ys_ts = font_buton.render(yeni_silah_mesaji, True, SARI)
                ekran.blit(ys_ts, (EN//2 - ys_ts.get_width()//2, 320))
        else:
            txt = L["oldu"]
            t_s = font_baslik.render(txt, True, PARLAK_KIRMIZI)
            ekran.blit(t_s, (EN//2 - t_s.get_width()//2, 150))
        
        fare, tik = fare_konumu(), False
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11: tam_ekran_ac_kapa()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: ana_menu()
            if event.type == pygame.MOUSEBUTTONDOWN: tik = True
        
        m_btn = "NEXT LEVEL" if kazandi and secili_harita < 30 else ("YOU BEAT THE GAME!" if kazandi else "RETRY")
        btns = [(m_btn, 300, 360), (L["sektorler"], 300, 420), (L["ana_menu"], 300, 480)]
        
        for i, (m, x, y) in enumerate(btns):
            r = pygame.Rect(x, y, 200, 45)
            hov = r.collidepoint(fare); c = BEYAZ if hov else GRI
            pygame.draw.rect(ekran, c, r, 1)
            ts = font_buton.render(m, True, c)
            ekran.blit(ts, (r.centerx - ts.get_width()//2, y+10))
            if tik and r.collidepoint(fare):
                if i == 0:
                    if kazandi and secili_harita < 30: secili_harita += 1
                    oyun_dongusu()
                elif i == 1: secim_ekrani()
                elif i == 2: ana_menu()
        scanline_ciz(); ekrani_guncelle()

def cybergrind_sonu_menusu(round_no):
    while True:
        ekran.fill(SIYAH)
        t_s = font_baslik.render("CYBERGRIND", True, MOR)
        ekran.blit(t_s, (EN//2 - t_s.get_width()//2, 90))
        alt = font_buton.render(f"HAYATTA KALINAN ROUND: {round_no}", True, BEYAZ)
        ekran.blit(alt, (EN//2 - alt.get_width()//2, 200))

        fare, tik = fare_konumu(), False
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11: tam_ekran_ac_kapa()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: ana_menu()
            if event.type == pygame.MOUSEBUTTONDOWN: tik = True

        btns = [("TEKRAR DENE", 300, 320), (metinler[ayarlar["dil"]]["ana_menu"], 300, 380)]
        for i, (m, x, y) in enumerate(btns):
            r = pygame.Rect(x, y, 200, 45)
            hov = r.collidepoint(fare); c = BEYAZ if hov else GRI
            pygame.draw.rect(ekran, c, r, 1)
            ts = font_buton.render(m, True, c)
            ekran.blit(ts, (r.centerx - ts.get_width()//2, y+10))
            if tik and r.collidepoint(fare):
                if i == 0: cybergrind_dongusu()
                else: ana_menu()
        scanline_ciz(); ekrani_guncelle()

def cybergrind_dongusu():
    global shake_amount, secili_silah, parcaciklar
    parcaciklar = []
    oyuncu = pygame.Rect(50, 500, 30, 30); oyuncu_y_hiz = 0; oyuncu_yerde = False
    ziplama_hakki, dj_aktif, son_dj, son_ates = 0, False, 0, 0
    son_ziplama_girdisi = 0
    mermiler, sari_kureler = [], []
    parry_radius = 65
    style_yazilar = []
    dusman_mermileri = []
    kuyruk = []
    kam_x = 0.0
    world_en = EN

    stil_puani = 0.0
    stil_onceki_seviye = ""

    zemin = pygame.Rect(0, 550, EN, 50)
    platformlar = [
        zemin,
        pygame.Rect(60, 460, 130, 20), pygame.Rect(610, 460, 130, 20),
        pygame.Rect(250, 380, 120, 20), pygame.Rect(430, 380, 120, 20),
        pygame.Rect(120, 280, 110, 20), pygame.Rect(570, 280, 110, 20),
        pygame.Rect(335, 200, 130, 20)
    ]
    cg_tema = {"ad": "CYBERGRIND", "platform": (90, 20, 110), "vurgu": MOR, "arka_fon": (8, 2, 14)}

    durum = {"round_no": 0, "dusmanlar": [], "boss": None, "gecis_bekleniyor": False, "gecis_zamani": 0, "sayimda": False, "sayim_bitis": 0}
    cg_boss_listesi = [("GABRIEL", GABRIEL_MAVI), ("SWORDSMACHINE", SWORDMACHINE_RENK), ("MINOS PRIME", MINOS_MINT)]

    def dalga_olustur():
        durum["dusmanlar"] = []
        durum["boss"] = None
        rn = durum["round_no"]
        if rn % 5 == 0:
            b_isim, b_renk = cg_boss_listesi[(rn // 5 - 1) % 3]
            can = 50 + rn * 5
            durum["boss"] = {
                'rect': pygame.Rect(EN//2 - 25, 150, 50, 50), 'can': can, 'max_can': can, 'golge_can': can,
                'isim': b_isim, 'renk': b_renk, 'son_isinlanma': 0.0, 'son_saldiri': 0.0
            }
            style_yazilar.append({'metin': f"BOSS ROUND: {b_isim}", 'x': EN // 2, 'y': 130, 'omur': 70, 'renk': b_renk, 'buyuk': True})
        else:
            sayi = min(2 + rn // 2, 8)
            turler = ['nobetci', 'kovalayici', 'teleporter']
            for idx in range(sayi):
                sx = EN // 2 - 15 + random.randint(-70, 70); sy = -50 - random.randint(0, 150)
                durum["dusmanlar"].append({
                    'id': idx, 'rect': pygame.Rect(sx, sy, 30, 30), 'spawn': (sx, sy),
                    'y_hiz': 0, 'yerde': False, 'hayatta': True, 'olum_zamani': 0,
                    'son_ates': 0, 'son_isinlanma': 0, 'tur': turler[idx % 3]
                })
            style_yazilar.append({'metin': f"ROUND {rn}", 'x': EN // 2, 'y': 130, 'omur': 55, 'renk': TURKUAZ, 'buyuk': True})

    def sonraki_round_planla():
        # Dalga hemen başlamaz; 5 saniyelik bir geri sayım sonrası gerçekten oluşturulur.
        durum["round_no"] += 1
        durum["sayimda"] = True
        durum["sayim_bitis"] = time.time() + 5

    sonraki_round_planla()
    muzik_cal("oyun1.mp3")

    while True:
        su_an = time.time()
        silah_beklemeleri = {"tabanca": 3, "taramali": 0.12, "pompali": 1.1}
        ates_cd, dj_cd = max(0, silah_beklemeleri.get(secili_silah, 3)-(su_an-son_ates)), max(0, 1-(su_an-son_dj))
        rn = durum["round_no"]
        cg_hiz = 1.2 * (1 + rn * 0.02)
        cg_ates_araligi = max(0.7, 1.8 - rn * 0.02)

        mermi_yakinda = False
        for dm in dusman_mermileri:
            if not dm.get('parried', False):
                if math.hypot(dm['rect'].centerx - oyuncu.centerx, dm['rect'].centery - oyuncu.centery) <= parry_radius:
                    mermi_yakinda = True; break

        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11: tam_ekran_ac_kapa()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_w:
                    if su_an - son_ziplama_girdisi > 0.1:
                        if oyuncu_yerde: oyuncu_y_hiz, oyuncu_yerde, ziplama_hakki = -15, False, 1
                        elif dj_aktif and ziplama_hakki == 1 and dj_cd == 0: oyuncu_y_hiz, ziplama_hakki, son_dj = -15, 2, su_an
                        son_ziplama_girdisi = su_an
                if event.key == pygame.K_1: secili_silah = "tabanca"
                if event.key == pygame.K_2:
                    if silah_kilitleri["taramali"]: secili_silah = "taramali"
                    else: style_yazilar.append({'metin': "KİLİTLİ", 'x': EN - 180, 'y': 100, 'omur': 40, 'renk': GRI})
                if event.key == pygame.K_3:
                    if silah_kilitleri["pompali"]: secili_silah = "pompali"
                    else: style_yazilar.append({'metin': "KİLİTLİ", 'x': EN - 180, 'y': 100, 'omur': 40, 'renk': GRI})
                if event.key == pygame.K_f:
                    for dm in dusman_mermileri:
                        if not dm.get('parried', False):
                            mesafe = math.hypot(dm['rect'].centerx - oyuncu.centerx, dm['rect'].centery - oyuncu.centery)
                            if mesafe <= parry_radius:
                                dm['parried'] = True
                                shake_amount = 15
                                stil_puani += 15
                                if ses_atis: ses_atis.play()
                                parcacik_ekle(dm['rect'].centerx, dm['rect'].centery, SARI, 20)
                                style_yazilar.append({'metin': "+PARRY", 'x': EN - 180, 'y': 80, 'omur': 45, 'renk': TURKUAZ})
                                if dm['tip'] == 'boss' and durum["boss"]:
                                    b_aci = math.atan2(durum["boss"]['rect'].centery - dm['rect'].centery, durum["boss"]['rect'].centerx - dm['rect'].centerx)
                                    dm['vx'] = math.cos(b_aci) * 16; dm['vy'] = math.sin(b_aci) * 16
                                else:
                                    dm['vx'] = -dm['vx'] * 2.5; dm['vy'] = -dm['vy'] * 2.5
                                break

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and secili_silah in ("tabanca", "pompali") and ates_cd == 0:
                fx, fy = fare_konumu()
                aci = math.atan2(fy - oyuncu.centery, fx - oyuncu.centerx)
                if secili_silah == "tabanca":
                    mermiler.append({'rect': pygame.Rect(oyuncu.centerx, oyuncu.centery, 10, 10), 'vx': math.cos(aci)*12, 'vy': math.sin(aci)*12, 'hasar': 10})
                    shake_amount = 5
                else:
                    for sapma in (-0.28, -0.14, 0, 0.14, 0.28):
                        a2 = aci + sapma
                        mermiler.append({'rect': pygame.Rect(oyuncu.centerx, oyuncu.centery, 8, 8), 'vx': math.cos(a2)*11, 'vy': math.sin(a2)*11, 'hasar': 6})
                    shake_amount = 14
                son_ates = su_an
                if ses_atis: ses_atis.play()
                parcacik_ekle(oyuncu.centerx, oyuncu.centery, TURKUAZ, 5)

        if secili_silah == "taramali" and pygame.mouse.get_pressed()[0] and ates_cd == 0:
            fx, fy = fare_konumu()
            aci = math.atan2(fy - oyuncu.centery, fx - oyuncu.centerx)
            mermiler.append({'rect': pygame.Rect(oyuncu.centerx, oyuncu.centery, 8, 8), 'vx': math.cos(aci)*13, 'vy': math.sin(aci)*13, 'hasar': 4})
            son_ates = su_an; shake_amount = 3
            if ses_atis: ses_atis.play()
            parcacik_ekle(oyuncu.centerx, oyuncu.centery, TURKUAZ, 3)

        tus = pygame.key.get_pressed()
        hareket_ediyor = False
        if tus[pygame.K_a]: oyuncu.x -= 5; hareket_ediyor = True
        if tus[pygame.K_d]: oyuncu.x += 5; hareket_ediyor = True
        oyuncu.x = max(0, min(world_en-30, oyuncu.x)); oyuncu_y_hiz += 0.8; oyuncu.y += oyuncu_y_hiz
        if not oyuncu_yerde: hareket_ediyor = True

        if hareket_ediyor:
            kuyruk.append({'x': oyuncu.x, 'y': oyuncu.y, 'omur': 10})
            if len(kuyruk) > 14: kuyruk.pop(0)

        stil_puani = max(0, stil_puani - 0.2)
        stil_isim_guncel, stil_renk_guncel = stil_seviyesi(stil_puani)
        if stil_isim_guncel != stil_onceki_seviye and stil_isim_guncel != "":
            style_yazilar.append({'metin': stil_isim_guncel, 'x': EN // 2, 'y': 130, 'omur': 55, 'renk': stil_renk_guncel, 'buyuk': True})
        stil_onceki_seviye = stil_isim_guncel

        # --- CYBERGRIND BOSS / DALGA MANTIĞI ---
        if durum["sayimda"]:
            if su_an >= durum["sayim_bitis"]:
                durum["sayimda"] = False
                dalga_olustur()
        elif durum["boss"]:
            b = durum["boss"]
            if su_an - b['son_isinlanma'] > 1.6:
                b['rect'].x = random.randint(60, EN - 110); b['rect'].y = random.randint(60, 300)
                parcacik_ekle(b['rect'].centerx, b['rect'].centery, b['renk'], 18)
                b['son_isinlanma'] = su_an
            if su_an - b['son_saldiri'] > max(0.5, 1.1 - rn * 0.01):
                b_aci = math.atan2(oyuncu.centery - b['rect'].centery, oyuncu.centerx - b['rect'].centerx)
                dusman_mermileri.append({'rect': pygame.Rect(b['rect'].centerx, b['rect'].centery, 12, 12), 'vx': math.cos(b_aci)*7, 'vy': math.sin(b_aci)*7, 'parried': False, 'tip': 'boss'})
                b['son_saldiri'] = su_an
            if oyuncu.colliderect(b['rect']):
                if ses_olme: ses_olme.play()
                cybergrind_sonu_menusu(rn); return
        elif not durum["gecis_bekleniyor"]:
            for d in durum["dusmanlar"]:
                if d['hayatta']:
                    tur = d.get('tur', 'nobetci')
                    hiz_carpani = {'nobetci': 1.0, 'kovalayici': 1.8, 'teleporter': 0.0}.get(tur, 1.0)
                    d['y_hiz'] += 0.8; d['rect'].y += d['y_hiz']
                    d['rect'].x += (cg_hiz * hiz_carpani) if d['rect'].centerx < oyuncu.centerx else -(cg_hiz * hiz_carpani)
                    if d['yerde'] and (d['rect'].y > oyuncu.y + 40 or abs(d['rect'].x - oyuncu.x) < 50): d['y_hiz'] = -14.5; d['yerde'] = False

                    if tur == 'teleporter' and su_an - d.get('son_isinlanma', 0) > 2.3:
                        parcacik_ekle(d['rect'].centerx, d['rect'].centery, MOR, 14)
                        d['rect'].x = max(30, min(EN - 60, oyuncu.centerx + random.randint(-200, 200)))
                        d['rect'].y = random.randint(50, 350)
                        d['y_hiz'] = 0
                        d['son_isinlanma'] = su_an

                    if tur != 'kovalayici':
                        ates_araligi_bu = cg_ates_araligi * (0.5 if tur == 'teleporter' else 1.0)
                        if su_an - d['son_ates'] > ates_araligi_bu:
                            d_aci = math.atan2(oyuncu.centery - d['rect'].centery, oyuncu.centerx - d['rect'].centerx)
                            hiz_mermi = 7 if tur == 'teleporter' else 5
                            dusman_mermileri.append({'rect': pygame.Rect(d['rect'].centerx, d['rect'].centery, 10, 10), 'vx': math.cos(d_aci)*hiz_mermi, 'vy': math.sin(d_aci)*hiz_mermi, 'parried': False, 'tip': 'normal', 'sahip_id': d['id']})
                            d['son_ates'] = su_an

                    if oyuncu.colliderect(d['rect']):
                        if ses_olme: ses_olme.play()
                        cybergrind_sonu_menusu(rn); return

            if durum["dusmanlar"] and all(not d['hayatta'] for d in durum["dusmanlar"]):
                durum["gecis_bekleniyor"] = True; durum["gecis_zamani"] = su_an

        if durum["gecis_bekleniyor"] and su_an - durum["gecis_zamani"] > 1.5:
            durum["gecis_bekleniyor"] = False
            sonraki_round_planla()

        # --- DÜŞMAN MERMİLERİ GÜNCELLEME ---
        for dm in dusman_mermileri[:]:
            dm['rect'].x += dm['vx']; dm['rect'].y += dm['vy']
            mermi_silindi = False
            if dm.get('parried', False):
                if durum["boss"] and dm['rect'].colliderect(durum["boss"]['rect']):
                    durum["boss"]['can'] -= 25
                    stil_puani += 25
                    parcacik_ekle(durum["boss"]['rect'].centerx, durum["boss"]['rect'].centery, SARI, 15)
                    style_yazilar.append({'metin': "+FRIED FRIENDLY FIRE", 'x': EN - 250, 'y': 110, 'omur': 45, 'renk': PARLAK_KIRMIZI})
                    if dm in dusman_mermileri: dusman_mermileri.remove(dm)
                    mermi_silindi = True
                    if durum["boss"]['can'] <= 0:
                        parcacik_ekle(durum["boss"]['rect'].centerx, durum["boss"]['rect'].centery, SARI, 50)
                        durum["boss"] = None; durum["gecis_bekleniyor"] = True; durum["gecis_zamani"] = su_an
                elif not durum["boss"] and not mermi_silindi:
                    for d in durum["dusmanlar"]:
                        if d['hayatta'] and dm['rect'].colliderect(d['rect']):
                            parcacik_ekle(d['rect'].centerx, d['rect'].centery, SARI, 15)
                            d['hayatta'], d['olum_zamani'] = False, su_an
                            stil_puani += 20
                            style_yazilar.append({'metin': "+FRIED FRIENDLY FIRE", 'x': EN - 250, 'y': 110, 'omur': 45, 'renk': PARLAK_KIRMIZI})
                            if dm in dusman_mermileri: dusman_mermileri.remove(dm)
                            mermi_silindi = True; break
            elif dm['rect'].colliderect(oyuncu) and not mermi_silindi:
                if ses_olme: ses_olme.play()
                cybergrind_sonu_menusu(rn); return

            if not mermi_silindi:
                if dm['rect'].y > BOY or dm['rect'].y < 0 or dm['rect'].x < 0 or dm['rect'].x > world_en:
                    if dm in dusman_mermileri: dusman_mermileri.remove(dm)

        # --- OYUNCU MERMİLERİ ---
        for m in mermiler[:]:
            m['rect'].x += m['vx']; m['rect'].y += m['vy']
            if m['rect'].x < -50 or m['rect'].x > EN + 50 or m['rect'].y < -50 or m['rect'].y > BOY + 50:
                if m in mermiler: mermiler.remove(m); continue
            if durum["boss"] and durum["boss"]['rect'].colliderect(m['rect']):
                durum["boss"]['can'] -= m.get('hasar', 10)
                stil_puani += 3
                parcacik_ekle(durum["boss"]['rect'].centerx, durum["boss"]['rect'].centery, durum["boss"]['renk'], 12)
                shake_amount = 6
                if m in mermiler: mermiler.remove(m)
                if durum["boss"]['can'] <= 0:
                    parcacik_ekle(durum["boss"]['rect'].centerx, durum["boss"]['rect'].centery, SARI, 50)
                    durum["boss"] = None; durum["gecis_bekleniyor"] = True; durum["gecis_zamani"] = su_an
                continue
            for d in durum["dusmanlar"]:
                if d['hayatta'] and d['rect'].colliderect(m['rect']):
                    parcacik_ekle(d['rect'].centerx, d['rect'].centery, PARLAK_KIRMIZI, 12)
                    d['hayatta'], d['olum_zamani'] = False, su_an
                    stil_puani += 10
                    if m in mermiler: mermiler.remove(m)
                    shake_amount = 10; break

        # --- FİZİK ÇARPIŞMALARI ---
        oyuncu_yerde = False
        for p in platformlar:
            if oyuncu.colliderect(p) and oyuncu_y_hiz > 0: oyuncu.bottom, oyuncu_y_hiz, oyuncu_yerde, ziplama_hakki = p.top, 0, True, 0
            for d in durum["dusmanlar"]:
                if d['hayatta'] and d['rect'].colliderect(p) and d['y_hiz'] > 0: d['rect'].bottom, d['y_hiz'], d['yerde'] = p.top, 0, True

        if oyuncu.y > BOY:
            if ses_olme: ses_olme.play()
            cybergrind_sonu_menusu(rn); return

        # --- ÇİZİM SAHNESİ ---
        ekran.fill(cg_tema["arka_fon"])
        arka_plan_ciz(kam_x)
        shake_ox, shake_oy = random.randint(-int(shake_amount), int(shake_amount)), random.randint(-int(shake_amount), int(shake_amount))
        shake_amount *= 0.9
        ox, oy = int(-kam_x) + shake_ox, shake_oy

        for p in platformlar: pygame.draw.rect(ekran, cg_tema["platform"], (p.x+ox, p.y+oy, p.w, p.h))
        parcacik_guncelle()

        for iz in kuyruk[:]:
            iz['omur'] -= 1
            if iz['omur'] <= 0: kuyruk.remove(iz)
            else:
                alfa = int(140 * (iz['omur'] / 10))
                iz_yuzey = pygame.Surface((8, 30), pygame.SRCALPHA)
                iz_yuzey.fill((255, 255, 0, alfa))
                ekran.blit(iz_yuzey, (iz['x'] + 11 + ox, iz['y'] + oy))

        if resim_yuklendi: ekran.blit(V1_GORSEL, (oyuncu.x+ox, oyuncu.y+oy))
        else: pygame.draw.rect(ekran, YESIL, (oyuncu.x+ox, oyuncu.y+oy, 30, 30))

        if mermi_yakinda:
            pygame.draw.circle(ekran, SARI, (oyuncu.centerx+ox, oyuncu.centery+oy), parry_radius, 2)

        for d in durum["dusmanlar"]:
            if d['hayatta']:
                tur_renk = {'nobetci': PARLAK_KIRMIZI, 'kovalayici': TURNCU, 'teleporter': MOR}.get(d.get('tur', 'nobetci'), PARLAK_KIRMIZI)
                pygame.draw.rect(ekran, tur_renk, (d['rect'].x+ox, d['rect'].y+oy, 30, 30))

        for dm in dusman_mermileri:
            m_renk = SARI if dm.get('parried', False) else (MOR if dm['tip'] == 'boss' else TURNCU)
            pygame.draw.circle(ekran, m_renk, (dm['rect'].centerx+ox, dm['rect'].centery+oy), 6)

        if durum["boss"]:
            b = durum["boss"]
            pygame.draw.rect(ekran, b['renk'], (b['rect'].x+ox, b['rect'].y+oy, 50, 50))
            pygame.draw.circle(ekran, PARLAK_KIRMIZI, (b['rect'].centerx+ox, b['rect'].centery+oy), 7)

            if b['golge_can'] > b['can']: b['golge_can'] = max(b['can'], b['golge_can'] - 0.6)
            b_bar_x, b_bar_y, b_bar_w, b_bar_h = 200, 30, 400, 15
            oran_can = b['can'] / b['max_can']; oran_golge = b['golge_can'] / b['max_can']
            pygame.draw.rect(ekran, GRI, (b_bar_x, b_bar_y, b_bar_w, b_bar_h))
            pygame.draw.rect(ekran, (235, 235, 160), (b_bar_x, b_bar_y, b_bar_w * oran_golge, b_bar_h))
            pygame.draw.rect(ekran, b['renk'], (b_bar_x, b_bar_y, b_bar_w * oran_can, b_bar_h))
            pygame.draw.rect(ekran, BEYAZ, (b_bar_x, b_bar_y, b_bar_w, b_bar_h), 1)
            pygame.draw.line(ekran, BEYAZ, (b_bar_x - 12, b_bar_y - 6), (b_bar_x, b_bar_y + b_bar_h + 6), 2)
            pygame.draw.line(ekran, BEYAZ, (b_bar_x + b_bar_w + 12, b_bar_y - 6), (b_bar_x + b_bar_w, b_bar_y + b_bar_h + 6), 2)
            b_isim = font_ui.render(b['isim'], True, BEYAZ)
            ekran.blit(b_isim, (EN//2 - b_isim.get_width()//2, 10))

        for m in mermiler: pygame.draw.rect(ekran, TURKUAZ, (m['rect'].x+ox, m['rect'].y+oy, 10, 10))

        pygame.draw.rect(ekran, GRI, (20, 20, 150, 10)); pygame.draw.rect(ekran, TURKUAZ, (20, 20, 150*(1-ates_cd/3), 10))
        if dj_aktif: pygame.draw.rect(ekran, GRI, (20, 40, 150, 10)); pygame.draw.rect(ekran, SARI, (20, 40, 150*(1-dj_cd/1), 10))

        silah_hud = font_ui.render(f"SILAH: {SILAH_ISIMLERI.get(secili_silah,'TABANCA')}  [1][2][3]", True, SARI)
        ekran.blit(silah_hud, (20, 58))
        round_yazi = font_ui.render(f"ROUND: {rn}", True, MOR)

        if durum["sayimda"]:
            kalan = max(1, int(durum["sayim_bitis"] - su_an) + 1)
            baslik_cg = font_buton.render(f"ROUND {rn} BAŞLIYOR", True, TURKUAZ)
            ekran.blit(baslik_cg, (EN//2 - baslik_cg.get_width()//2, BOY//2 - 90))
            sayi_txt = font_countdown_base.render(str(kalan), True, SARI)
            ekran.blit(sayi_txt, (EN//2 - sayi_txt.get_width()//2, BOY//2 - sayi_txt.get_height()//2))
        ekran.blit(round_yazi, (20, BOY - 30))

        stil_bar_oran = min(1.0, stil_puani / 200)
        stil_bar_renk = stil_renk_guncel if stil_isim_guncel != "" else GRI
        pygame.draw.rect(ekran, GRI, (EN - 150, 20, 130, 8))
        pygame.draw.rect(ekran, stil_bar_renk, (EN - 150, 20, 130 * stil_bar_oran, 8))
        if stil_isim_guncel:
            etiket = font_ui.render(stil_isim_guncel, True, stil_bar_renk)
            ekran.blit(etiket, (EN - 150, 32))

        for st in style_yazilar[:]:
            buyuk = st.get('buyuk', False)
            f = font_stil_buyuk if buyuk else font_style
            txt_s = f.render(st['metin'], True, st['renk'])
            bx = st['x'] - txt_s.get_width() // 2 if buyuk else st['x']
            ekran.blit(txt_s, (bx, st['y']))
            st['y'] -= 0.6 if buyuk else 0.5
            st['omur'] -= 1
            if st['omur'] <= 0: style_yazilar.remove(st)

        scanline_ciz(); ekrani_guncelle(); saat.tick(60)

MP_PORT = 5555

# --- İNTERNET (RELAY) AYARLARI ---
# Kendi relay sunucunu (relay_server.py) bir yere kurunca, buraya onun adresini yaz.
# Örnek: "ultraparkour-relay.onrender.com" ve port 443 ya da sağlayıcının verdiği port.
# Şimdilik yer tutucu — kurmadan "İNTERNET ODASI" çalışmaz (bağlanamaz hatası verir).
RELAY_SUNUCU_ADRES = "ultraparkour.onrender.com"
RELAY_SUNUCU_PORT = 443  # Render dışarıya sadece HTTPS(443) ile açık, kod otomatik TLS kullanır

def yerel_ip_bul():
    """Bilgisayarın yerel ağ (LAN) IP adresini bulur. Gerçekte veri göndermez,
    sadece işletim sisteminin hangi arayüzü kullanacağını öğrenmek için bir rota sorgular."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip
    except Exception:
        return '127.0.0.1'

def metin_girisi(baslik, on_deger=""):
    """Basit bir metin girişi ekranı. ENTER ile yazılan metni döndürür, ESC ile None döndürür."""
    metin = on_deger
    while True:
        ekran.fill(SIYAH)
        b_yazi = font_buton.render(baslik, True, BEYAZ)
        ekran.blit(b_yazi, (EN//2 - b_yazi.get_width()//2, 200))

        kutu = pygame.Rect(EN//2 - 160, 260, 320, 46)
        pygame.draw.rect(ekran, TURKUAZ, kutu, 2)
        imlec = "_" if int(time.time() * 2) % 2 == 0 else ""
        girilen = font_buton.render(metin + imlec, True, BEYAZ)
        ekran.blit(girilen, (kutu.x + 12, kutu.y + 10))

        ipucu = font_ui.render("ENTER: Onayla    ESC: İptal", True, GRI)
        ekran.blit(ipucu, (EN//2 - ipucu.get_width()//2, 330))

        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN: return metin
                elif event.key == pygame.K_ESCAPE: return None
                elif event.key == pygame.K_BACKSPACE: metin = metin[:-1]
                elif event.unicode and event.unicode.isprintable() and len(metin) < 30:
                    metin += event.unicode
        scanline_ciz(); ekrani_guncelle(); saat.tick(30)

def hata_goster(mesaj):
    while True:
        ekran.fill(SIYAH)
        t = font_buton.render("HATA", True, PARLAK_KIRMIZI)
        ekran.blit(t, (EN//2 - t.get_width()//2, 200))
        m = font_ui.render(mesaj, True, BEYAZ)
        ekran.blit(m, (EN//2 - m.get_width()//2, 250))
        ipucu = font_ui.render("Devam etmek için tıkla ya da bir tuşa bas", True, GRI)
        ekran.blit(ipucu, (EN//2 - ipucu.get_width()//2, 300))
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN: return
            if event.type == pygame.MOUSEBUTTONDOWN: return
        scanline_ciz(); ekrani_guncelle()

def baglanti_koptu_ekrani():
    while True:
        ekran.fill(SIYAH)
        t = font_buton.render("BAĞLANTI KOPTU", True, PARLAK_KIRMIZI)
        ekran.blit(t, (EN//2 - t.get_width()//2, 250))
        ipucu = font_ui.render("Devam etmek için tıkla ya da bir tuşa bas", True, GRI)
        ekran.blit(ipucu, (EN//2 - ipucu.get_width()//2, 300))
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN: return
            if event.type == pygame.MOUSEBUTTONDOWN: return
        scanline_ciz(); ekrani_guncelle()

def mp_menu():
    while True:
        ekran.fill(SIYAH); L = metinler[ayarlar["dil"]]; fare = fare_konumu()
        baslik = font_buton.render("ÇEVRİMİÇİ", True, TURKUAZ)
        ekran.blit(baslik, (EN//2 - baslik.get_width()//2, 90))

        aciklamalar = [
            "AYNI AĞ: Aynı Wi-Fi'daki biriyle. Biri SUNUCU KUR, diğeri KATIL (IP ile).",
            "İNTERNET: Uzaktaki biriyle. İkiniz de aynı ODA KODU'nu girersiniz."
        ]
        y = 135
        for s in aciklamalar:
            t = font_ui.render(s, True, GRI)
            ekran.blit(t, (EN//2 - t.get_width()//2, y)); y += 22

        btn_host = pygame.Rect(250, 195, 300, 44)
        btn_join = pygame.Rect(250, 248, 300, 44)
        btn_net  = pygame.Rect(250, 315, 300, 50)
        btn_geri = pygame.Rect(300, 400, 200, 44)

        lan_lbl = font_ui.render("— AYNI AĞ (LAN) —", True, GRI)
        ekran.blit(lan_lbl, (EN//2 - lan_lbl.get_width()//2, 178))
        net_lbl = font_ui.render("— İNTERNET (ODA KODU) —", True, MOR)
        ekran.blit(net_lbl, (EN//2 - net_lbl.get_width()//2, 298))

        for r, t, renk in [(btn_host, "SUNUCU KUR", TURKUAZ), (btn_join, "KATIL (IP)", TURKUAZ),
                            (btn_net, "İNTERNET ODASI", MOR), (btn_geri, L["geri"], GRI)]:
            hov = r.collidepoint(fare); c = SARI if hov else renk
            pygame.draw.rect(ekran, c, r, 2)
            ts = font_buton.render(t, True, c)
            ekran.blit(ts, (r.centerx - ts.get_width()//2, r.centery - 11))

        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11: tam_ekran_ac_kapa()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: return
            if event.type == pygame.MOUSEBUTTONDOWN:
                if btn_host.collidepoint(fare): mp_sunucu_kur()
                if btn_join.collidepoint(fare): mp_istemci_baglan()
                if btn_net.collidepoint(fare): mp_internet_baglan()
                if btn_geri.collidepoint(fare): return
        scanline_ciz(); ekrani_guncelle()

# ============================================================
# WEBSOCKET İSTEMCİ DESTEĞİ (sadece İNTERNET/relay bağlantısı için)
# Render gibi barındırma servisleri ham TCP'yi tanımadığı için, internet
# üzerinden bağlanırken WebSocket protokolü kullanıyoruz. Bu sınıf, ham
# socket'i WebSocket çerçeveleri altında saklayıp dışarıya normal bir
# socket gibi (sendall/makefile/close/settimeout) görünmesini sağlıyor —
# böylece mp_oyun_dongusu ve mp_alici_thread HİÇ değişmeden, hem LAN (düz
# TCP) hem İNTERNET (WebSocket) modunda aynı şekilde çalışıyor.
# ============================================================

def _ws_el_sikismasi(soket, host, yol="/"):
    """WebSocket açılış el sıkışmasını senkron soket üzerinden yapar."""
    anahtar = base64.b64encode(os.urandom(16)).decode()
    istek = (
        f"GET {yol} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {anahtar}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"\r\n"
    )
    soket.sendall(istek.encode())
    yanit = b""
    while b"\r\n\r\n" not in yanit:
        parca = soket.recv(1)
        if not parca:
            raise ConnectionError("El sıkışma sırasında bağlantı koptu")
        yanit += parca
    ilk_satir = yanit.split(b"\r\n")[0]
    if b"101" not in ilk_satir:
        raise ConnectionError("Sunucu WebSocket yükseltmesini kabul etmedi: " + ilk_satir.decode(errors="ignore"))
    return True


class _WebSocketDosyaGibi:
    """conn.makefile('r')'ın yerini tutar; 'for satir in dosya:' ile satır satır JSON okunmasını sağlar."""
    def __init__(self, ws_soket):
        self._ws = ws_soket

    def __iter__(self):
        return self

    def __next__(self):
        try:
            veri = self._ws._cerceve_al()
        except Exception:
            raise StopIteration
        return veri.decode('utf-8', errors='ignore') + "\n"

    def readline(self):
        try:
            veri = self._ws._cerceve_al()
        except Exception:
            return ""
        return veri.decode('utf-8', errors='ignore') + "\n"


class _WebSocketSoket:
    """Ham socket'i WebSocket çerçeveleri altında saklayan ince sarmalayıcı."""
    def __init__(self, ham_soket):
        self._s = ham_soket
        self._yazma_kilidi = threading.Lock()

    def sendall(self, veri_bytes):
        with self._yazma_kilidi:
            self._cerceve_gonder(veri_bytes)

    def _cerceve_gonder(self, veri_bytes):
        uzunluk = len(veri_bytes)
        maske = os.urandom(4)
        maskelenmis = bytes(b ^ maske[i % 4] for i, b in enumerate(veri_bytes))
        ilk_bayt = 0x81  # FIN=1, opcode=1 (metin çerçevesi)
        if uzunluk < 126:
            baslik = struct.pack('!BB', ilk_bayt, 0x80 | uzunluk)
        elif uzunluk < 65536:
            baslik = struct.pack('!BBH', ilk_bayt, 0x80 | 126, uzunluk)
        else:
            baslik = struct.pack('!BBQ', ilk_bayt, 0x80 | 127, uzunluk)
        self._s.sendall(baslik + maske + maskelenmis)

    def _tam_oku(self, n):
        veri = b""
        while len(veri) < n:
            parca = self._s.recv(n - len(veri))
            if not parca:
                raise ConnectionError("bağlantı kapandı")
            veri += parca
        return veri

    def _cerceve_al(self):
        while True:
            ilk_iki = self._tam_oku(2)
            ilk_bayt, ikinci_bayt = ilk_iki[0], ilk_iki[1]
            opcode = ilk_bayt & 0x0F
            uzunluk = ikinci_bayt & 0x7F
            if uzunluk == 126:
                uzunluk = struct.unpack('!H', self._tam_oku(2))[0]
            elif uzunluk == 127:
                uzunluk = struct.unpack('!Q', self._tam_oku(8))[0]
            veri = self._tam_oku(uzunluk) if uzunluk else b""
            if opcode == 0x8:  # close çerçevesi
                raise ConnectionError("karşı taraf bağlantıyı kapattı")
            elif opcode in (0x9, 0xA):  # ping/pong -> yok say, sıradaki çerçeveyi oku
                continue
            else:
                return veri

    def makefile(self, mod='r'):
        return _WebSocketDosyaGibi(self)

    def settimeout(self, t):
        self._s.settimeout(t)

    def close(self):
        try: self._s.close()
        except Exception: pass


def mp_internet_baglan():
    # Relay sunucu adresi. Render gibi barındırma kullanıyorsan port 443 (TLS gerekir);
    # kendi bilgisayarında/RPi'de barındırıyorsan port 5555 (düz TCP, TLS gerekmez).
    relay_adres = RELAY_SUNUCU_ADRES
    relay_port = RELAY_SUNUCU_PORT
    oda = metin_girisi("ODA KODU (arkadaşınla aynı olsun):", "")
    if not oda: return
    oda = oda.strip().upper()

    ham_soket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ham_soket.settimeout(10)
    kutu_baglanti = {"durum": "baglaniyor", "is_host": None, "hata": None, "soket": None}

    def baglan():
        try:
            ham_soket.connect((relay_adres, relay_port))
            if relay_port == 443:
                # 443 = barındırma servisi (Render vb.). TLS + WebSocket şart
                # (Render ham TCP'yi yönlendirmiyor, "No open HTTP ports" hatası veriyor).
                baglam = ssl.create_default_context()
                tls_soket = baglam.wrap_socket(ham_soket, server_hostname=relay_adres)
                _ws_el_sikismasi(tls_soket, relay_adres)
                aktif_soket = _WebSocketSoket(tls_soket)
            else:
                # Kendi sunucun (RPi, ev bilgisayarı vb.), düz bağlantı yeterli
                aktif_soket = ham_soket
            kutu_baglanti["soket"] = aktif_soket
            # oda kodunu gönder
            aktif_soket.sendall((json.dumps({"oda": oda}) + "\n").encode())
            # sunucudan yanıt bekle (bekliyor / hazir / doldu)
            dosya = aktif_soket.makefile('r')
            for satir in dosya:
                try:
                    veri = json.loads(satir.strip())
                except Exception:
                    continue
                sys_mesaj = veri.get("sys")
                if sys_mesaj == "bekliyor":
                    kutu_baglanti["durum"] = "bekliyor"
                elif sys_mesaj == "doldu":
                    kutu_baglanti["hata"] = "Bu oda zaten dolu (2 kişi)."
                    return
                elif sys_mesaj == "hazir":
                    kutu_baglanti["is_host"] = veri.get("host", False)
                    kutu_baglanti["durum"] = "hazir"
                    return
        except Exception as e:
            kutu_baglanti["hata"] = str(e)

    threading.Thread(target=baglan, daemon=True).start()

    while True:
        ekran.fill(SIYAH)
        b = font_buton.render(f"ODA: {oda}", True, SARI)
        ekran.blit(b, (EN//2 - b.get_width()//2, 180))
        durum = kutu_baglanti["durum"]
        if durum == "baglaniyor":
            mesaj = "Sunucuya bağlanılıyor..."
        elif durum == "bekliyor":
            mesaj = "Arkadaşının aynı oda kodunu girmesi bekleniyor..."
        else:
            mesaj = "..."
        m = font_ui.render(mesaj, True, TURKUAZ)
        ekran.blit(m, (EN//2 - m.get_width()//2, 240))
        ipucu = font_ui.render("ESC: İptal", True, GRI)
        ekran.blit(ipucu, (EN//2 - ipucu.get_width()//2, 290))

        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                try: ham_soket.close()
                except Exception: pass
                return

        if kutu_baglanti["hata"]:
            try: ham_soket.close()
            except Exception: pass
            hata_goster(kutu_baglanti["hata"])
            return
        if kutu_baglanti["durum"] == "hazir":
            baglanti_soketi = kutu_baglanti["soket"]
            baglanti_soketi.settimeout(None)
            mp_oyun_dongusu(baglanti_soketi, kutu_baglanti["is_host"])
            return
        scanline_ciz(); ekrani_guncelle(); saat.tick(30)

def mp_sunucu_kur():
    ip = yerel_ip_bul()
    sunucu_soket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sunucu_soket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sunucu_soket.bind(('', MP_PORT))
        sunucu_soket.listen(1)
    except Exception as e:
        hata_goster(f"Sunucu başlatılamadı: {e}")
        return

    kutu = {"conn": None, "hata": None}

    def bekle():
        try:
            sunucu_soket.settimeout(120)
            conn, addr = sunucu_soket.accept()
            kutu["conn"] = conn
        except Exception as e:
            kutu["hata"] = str(e)

    threading.Thread(target=bekle, daemon=True).start()
    baslangic = time.time()

    while True:
        ekran.fill(SIYAH)
        b = font_buton.render("SUNUCU KURULDU", True, TURKUAZ)
        ekran.blit(b, (EN//2 - b.get_width()//2, 150))
        ip_yazi = font_buton.render(f"IP: {ip}    PORT: {MP_PORT}", True, SARI)
        ekran.blit(ip_yazi, (EN//2 - ip_yazi.get_width()//2, 220))
        bekleme = font_ui.render(f"Arkadaşının bağlanması bekleniyor... ({int(time.time()-baslangic)}s)", True, GRI)
        ekran.blit(bekleme, (EN//2 - bekleme.get_width()//2, 280))
        ipucu = font_ui.render("ESC: İptal", True, GRI)
        ekran.blit(ipucu, (EN//2 - ipucu.get_width()//2, 320))

        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                try: sunucu_soket.close()
                except Exception: pass
                return

        if kutu["conn"]:
            mp_oyun_dongusu(kutu["conn"], True)
            try: sunucu_soket.close()
            except Exception: pass
            return
        if kutu["hata"]:
            hata_goster(f"Bağlantı hatası: {kutu['hata']}")
            try: sunucu_soket.close()
            except Exception: pass
            return

        scanline_ciz(); ekrani_guncelle(); saat.tick(30)

def mp_istemci_baglan():
    ip = metin_girisi("Sunucunun IP Adresini Gir:", "192.168.1.")
    if not ip: return
    soket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    soket.settimeout(5)
    kutu = {"basarili": False, "hata": None}

    def baglan():
        try:
            soket.connect((ip.strip(), MP_PORT))
            kutu["basarili"] = True
        except Exception as e:
            kutu["hata"] = str(e)

    threading.Thread(target=baglan, daemon=True).start()

    while True:
        ekran.fill(SIYAH)
        b = font_buton.render(f"{ip} adresine bağlanılıyor...", True, TURKUAZ)
        ekran.blit(b, (EN//2 - b.get_width()//2, 220))
        ipucu = font_ui.render("ESC: İptal", True, GRI)
        ekran.blit(ipucu, (EN//2 - ipucu.get_width()//2, 280))

        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: return

        if kutu["basarili"]:
            soket.settimeout(None)
            mp_oyun_dongusu(soket, False)
            return
        if kutu["hata"]:
            hata_goster(f"Bağlanılamadı: {kutu['hata']}")
            return
        scanline_ciz(); ekrani_guncelle(); saat.tick(30)

def mp_alici_thread(conn, kutu):
    """Karşı taraftan gelen mesajları sürekli okuyup 'kutu' sözlüğüne yazan arka plan thread'i."""
    try:
        dosya = conn.makefile('r')
        for satir in dosya:
            satir = satir.strip()
            if not satir: continue
            try:
                veri = json.loads(satir)
            except Exception:
                continue
            tip = veri.get('t')
            if tip == 'pos':
                kutu['x'] = veri.get('x', kutu.get('x', 0))
                kutu['y'] = veri.get('y', kutu.get('y', 0))
                kutu['can'] = veri.get('can', 100)
            elif tip == 'hit':
                kutu['gelen_hasar'] = kutu.get('gelen_hasar', 0) + veri.get('dmg', 10)
            elif tip == 'oldu':
                kutu['rakip_oldu'] = True
            elif tip == 'atis':
                kutu.setdefault('gelen_mermiler', []).append(veri)
    except Exception:
        pass
    kutu['baglanti_koptu'] = True

def mp_oyun_dongusu(conn, is_host):
    global shake_amount
    conn.settimeout(None)
    kutu = {'x': (EN - 100 if is_host else 100), 'y': 500, 'can': 100,
            'gelen_hasar': 0, 'rakip_oldu': False, 'baglanti_koptu': False}
    threading.Thread(target=mp_alici_thread, args=(conn, kutu), daemon=True).start()

    # Sabit, dar bir düello arenası (kamera gezmez, iki oyuncu da her zaman ekranda)
    zemin = pygame.Rect(0, 550, EN, 50)
    platformlar = [zemin, pygame.Rect(150, 400, 180, 20), pygame.Rect(470, 400, 180, 20), pygame.Rect(325, 280, 150, 20)]

    oyuncu = pygame.Rect(100 if is_host else EN - 130, 500, 30, 30)
    oyuncu_y_hiz = 0; oyuncu_yerde = False
    son_ziplama_girdisi = 0
    can = 100
    mermiler = []
    rakip_mermiler = []  # rakibin attığı, sadece görsel amaçlı gösterilen mermiler
    kazandi = None  # None: devam ediyor, True: kazandın, False: kaybettin
    son_gonderim = 0

    # --- Silahlar ve parry (multiplayer'da tüm silahlar baştan açık) ---
    secili_silah = "tabanca"
    silah_beklemeleri = {"tabanca": 3, "taramali": 0.12, "pompali": 1.1}
    son_ates = 0
    parry_radius = 65

    # Rakibi ekranda yumuşak göstermek için: gerçek konum (kutu'dan gelen) yerine
    # her karede o konuma doğru kayan bir "görüntü konumu" tutuyoruz (interpolation).
    rakip_gorsel_x = float(kutu.get('x', EN - 100))
    rakip_gorsel_y = float(kutu.get('y', 500))

    muzik_cal("oyun1.mp3")

    while True:
        su_an = time.time()

        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11: tam_ekran_ac_kapa()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                try: conn.close()
                except Exception: pass
                return
            if kazandi is None and event.type == pygame.KEYDOWN and event.key == pygame.K_w:
                if su_an - son_ziplama_girdisi > 0.1:
                    if oyuncu_yerde: oyuncu_y_hiz, oyuncu_yerde = -15, False
                    son_ziplama_girdisi = su_an

            # --- SİLAH SEÇİMİ (1: Tabanca, 2: Taramalı, 3: Pompalı — multiplayer'da hepsi açık) ---
            if kazandi is None and event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1: secili_silah = "tabanca"
                if event.key == pygame.K_2: secili_silah = "taramali"
                if event.key == pygame.K_3: secili_silah = "pompali"

            # --- PARRY (F): rakibin mermisini yakalayıp kendi mermin gibi geri gönderir ---
            if kazandi is None and event.type == pygame.KEYDOWN and event.key == pygame.K_f:
                for dm in rakip_mermiler[:]:
                    mesafe = math.hypot(dm['rect'].centerx - oyuncu.centerx, dm['rect'].centery - oyuncu.centery)
                    if mesafe <= parry_radius:
                        rakip_mermiler.remove(dm)
                        dm['vx'] *= -2.2; dm['vy'] *= -2.2
                        dm['hasar'] = 15  # parry edilen mermi daha sert vurur
                        mermiler.append(dm)
                        shake_amount = 15
                        parcacik_ekle(dm['rect'].centerx, dm['rect'].centery, SARI, 20)
                        if ses_atis: ses_atis.play()
                        break

            ates_cd_kalan = max(0, silah_beklemeleri.get(secili_silah, 3) - (su_an - son_ates))
            if kazandi is None and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 \
               and secili_silah in ("tabanca", "pompali") and ates_cd_kalan == 0:
                fx, fy = fare_konumu()
                aci = math.atan2(fy - oyuncu.centery, fx - oyuncu.centerx)
                if secili_silah == "tabanca":
                    vx, vy = math.cos(aci) * 12, math.sin(aci) * 12
                    mermiler.append({'rect': pygame.Rect(oyuncu.centerx, oyuncu.centery, 10, 10), 'vx': vx, 'vy': vy, 'hasar': 10})
                    try:
                        conn.sendall((json.dumps({'t': 'atis', 'x': oyuncu.centerx, 'y': oyuncu.centery, 'vx': vx, 'vy': vy}) + "\n").encode())
                    except Exception:
                        kutu['baglanti_koptu'] = True
                    shake_amount = 5
                else:  # pompalı: konik saçma (5 parça)
                    for sapma in (-0.28, -0.14, 0, 0.14, 0.28):
                        a2 = aci + sapma
                        vx, vy = math.cos(a2) * 11, math.sin(a2) * 11
                        mermiler.append({'rect': pygame.Rect(oyuncu.centerx, oyuncu.centery, 8, 8), 'vx': vx, 'vy': vy, 'hasar': 6})
                        try:
                            conn.sendall((json.dumps({'t': 'atis', 'x': oyuncu.centerx, 'y': oyuncu.centery, 'vx': vx, 'vy': vy}) + "\n").encode())
                        except Exception:
                            kutu['baglanti_koptu'] = True
                    shake_amount = 14
                son_ates = su_an
                if ses_atis: ses_atis.play()
                parcacik_ekle(oyuncu.centerx, oyuncu.centery, TURKUAZ, 5)

        # --- TARAMALI SİLAH: basılı tutarak sürekli ateş ---
        ates_cd_kalan = max(0, silah_beklemeleri.get(secili_silah, 3) - (su_an - son_ates))
        if kazandi is None and secili_silah == "taramali" and pygame.mouse.get_pressed()[0] and ates_cd_kalan == 0:
            fx, fy = fare_konumu()
            aci = math.atan2(fy - oyuncu.centery, fx - oyuncu.centerx)
            vx, vy = math.cos(aci) * 13, math.sin(aci) * 13
            mermiler.append({'rect': pygame.Rect(oyuncu.centerx, oyuncu.centery, 8, 8), 'vx': vx, 'vy': vy, 'hasar': 4})
            try:
                conn.sendall((json.dumps({'t': 'atis', 'x': oyuncu.centerx, 'y': oyuncu.centery, 'vx': vx, 'vy': vy}) + "\n").encode())
            except Exception:
                kutu['baglanti_koptu'] = True
            son_ates = su_an; shake_amount = 3

        if kazandi is None:
            tus = pygame.key.get_pressed()
            if tus[pygame.K_a]: oyuncu.x -= 5
            if tus[pygame.K_d]: oyuncu.x += 5
            oyuncu.x = max(0, min(EN - 30, oyuncu.x))
            oyuncu_y_hiz += 0.8; oyuncu.y += oyuncu_y_hiz

            oyuncu_yerde = False
            for p in platformlar:
                if oyuncu.colliderect(p) and oyuncu_y_hiz > 0:
                    oyuncu.bottom, oyuncu_y_hiz, oyuncu_yerde = p.top, 0, True

            if oyuncu.y > BOY + 100:
                oyuncu.x, oyuncu.y, oyuncu_y_hiz = EN // 2, 400, 0  # düşerse ortaya ışınlan

        # Rakibin görüntü konumunu, gelen gerçek konuma doğru her karede %25 yaklaştır.
        # Bu, seyrek gelen ağ verisini (20/sn) 60 FPS'e yumuşatarak takılmayı giderir.
        hedef_x = kutu.get('x', rakip_gorsel_x)
        hedef_y = kutu.get('y', rakip_gorsel_y)
        rakip_gorsel_x += (hedef_x - rakip_gorsel_x) * 0.25
        rakip_gorsel_y += (hedef_y - rakip_gorsel_y) * 0.25
        rakip_rect = pygame.Rect(int(rakip_gorsel_x), int(rakip_gorsel_y), 30, 30)

        # Rakipten "atış yaptım" mesajı geldiyse, o mermiyi görsel olarak ekle
        yeni_mermiler = kutu.get('gelen_mermiler')
        if yeni_mermiler:
            for vm in yeni_mermiler:
                rakip_mermiler.append({'rect': pygame.Rect(int(vm.get('x', 0)), int(vm.get('y', 0)), 10, 10),
                                        'vx': vm.get('vx', 0), 'vy': vm.get('vy', 0)})
            kutu['gelen_mermiler'] = []

        # Rakibin mermilerini hareket ettir (sadece görsel — isabeti atan taraf belirler)
        for m in rakip_mermiler[:]:
            m['rect'].x += m['vx']; m['rect'].y += m['vy']
            if m['rect'].x < -20 or m['rect'].x > EN + 20 or m['rect'].y < -20 or m['rect'].y > BOY + 20:
                rakip_mermiler.remove(m); continue
            if kazandi is None and m['rect'].colliderect(oyuncu):
                rakip_mermiler.remove(m)
                parcacik_ekle(oyuncu.centerx, oyuncu.centery, PARLAK_KIRMIZI, 10)  # görsel geri bildirim (hasar zaten 'hit' mesajıyla ayrı işleniyor)

        for m in mermiler[:]:
            m['rect'].x += m['vx']; m['rect'].y += m['vy']
            if m['rect'].x < -20 or m['rect'].x > EN + 20 or m['rect'].y < -20 or m['rect'].y > BOY + 20:
                mermiler.remove(m); continue
            if kazandi is None and m['rect'].colliderect(rakip_rect):
                mermiler.remove(m)
                try: conn.sendall((json.dumps({'t': 'hit', 'dmg': m.get('hasar', 10)}) + "\n").encode())
                except Exception: kutu['baglanti_koptu'] = True
                parcacik_ekle(rakip_rect.centerx, rakip_rect.centery, SARI, 12)
                shake_amount = 8

        if kutu.get('gelen_hasar', 0) > 0 and kazandi is None:
            can -= kutu['gelen_hasar']
            kutu['gelen_hasar'] = 0
            shake_amount = 12
            if can <= 0:
                can = 0; kazandi = False
                try: conn.sendall((json.dumps({'t': 'oldu'}) + "\n").encode())
                except Exception: pass

        if kutu.get('rakip_oldu') and kazandi is None:
            kazandi = True

        if kutu.get('baglanti_koptu'):
            baglanti_koptu_ekrani()
            try: conn.close()
            except Exception: pass
            return

        if su_an - son_gonderim > 0.033:  # saniyede ~30 kez konum gönder (daha akıcı senkron)
            try:
                conn.sendall((json.dumps({'t': 'pos', 'x': oyuncu.x, 'y': oyuncu.y, 'can': can}) + "\n").encode())
            except Exception:
                kutu['baglanti_koptu'] = True
            son_gonderim = su_an

        # --- ÇİZİM ---
        ekran.fill(SIYAH)
        for p in platformlar: pygame.draw.rect(ekran, KOYU_KIRMIZI, p)
        parcacik_guncelle()

        # Host oyuncu karakter.png, client oyuncu karakter2.png kullanır.
        # Her oyuncu kendi görselini ve rakibinin görselini doğru şekilde görür.
        benim_gorsel = V1_GORSEL if is_host else (V2_GORSEL if resim2_yuklendi else None)
        benim_var = resim_yuklendi if is_host else resim2_yuklendi
        rakip_gorsel = (V2_GORSEL if resim2_yuklendi else None) if is_host else V1_GORSEL
        rakip_var = resim2_yuklendi if is_host else resim_yuklendi

        if benim_var: ekran.blit(benim_gorsel, (oyuncu.x, oyuncu.y))
        else: pygame.draw.rect(ekran, YESIL, oyuncu)      # görsel yoksa yeşil kutu
        if rakip_var: ekran.blit(rakip_gorsel, (rakip_rect.x, rakip_rect.y))
        else: pygame.draw.rect(ekran, TURKUAZ, rakip_rect)  # görsel yoksa turkuaz kutu

        # Parry menzil halkası: sadece bir mermi menzile (parry mesafesinin biraz dışına) girince görünsün
        if kazandi is None:
            for m in rakip_mermiler:
                if math.hypot(m['rect'].centerx - oyuncu.centerx, m['rect'].centery - oyuncu.centery) <= parry_radius * 1.6:
                    pygame.draw.circle(ekran, SARI, oyuncu.center, parry_radius, 1)
                    break

        for m in mermiler: pygame.draw.rect(ekran, SARI, m['rect'])
        for m in rakip_mermiler: pygame.draw.rect(ekran, PARLAK_KIRMIZI, m['rect'])  # rakibin mermisi: kırmızı (dikkat çeksin)

        pygame.draw.rect(ekran, GRI, (20, 20, 200, 16))
        pygame.draw.rect(ekran, YESIL, (20, 20, 200 * max(0, can) / 100, 16))
        ekran.blit(font_ui.render("SEN", True, YESIL), (20, 40))

        rakip_can = kutu.get('can', 100)
        pygame.draw.rect(ekran, GRI, (EN - 220, 20, 200, 16))
        pygame.draw.rect(ekran, TURKUAZ, (EN - 220, 20, 200 * max(0, rakip_can) / 100, 16))
        ekran.blit(font_ui.render("RAKİP", True, TURKUAZ), (EN - 220, 40))

        silah_hud = font_ui.render(f"SILAH: {SILAH_ISIMLERI.get(secili_silah,'TABANCA')}  [1][2][3]  |  F: PARRY", True, SARI)
        ekran.blit(silah_hud, (20, BOY - 30))

        if kazandi is True:
            t = font_baslik.render("KAZANDIN!", True, YESIL)
            ekran.blit(t, (EN // 2 - t.get_width() // 2, 200))
        elif kazandi is False:
            t = font_baslik.render("KAYBETTİN!", True, PARLAK_KIRMIZI)
            ekran.blit(t, (EN // 2 - t.get_width() // 2, 200))
        if kazandi is not None:
            ipucu = font_ui.render("ESC: Ana Menü", True, GRI)
            ekran.blit(ipucu, (EN // 2 - ipucu.get_width() // 2, 280))

        scanline_ciz(); ekrani_guncelle(); saat.tick(60)

ana_menu()