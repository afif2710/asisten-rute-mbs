from PIL import Image
import pandas as pd
import requests
import json
import urllib.parse
import base64
import io   
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# 1. KONFIGURASI NAMA MODEL, API KEY & SHEET ID
MODEL_AI = "deepseek-chat"  # Ubah ke "claude-3-opus" atau "deepseek-chat" sesuai petunjuk Sylor API
SYLOR_TOKEN = "sk-P4SsjGL7xtrxPSiNwC7uxaVzm1pUgj69t6iD8frhWokWaDA" 
SHEET_ID = "1IK85aVNFgbzWHCwua4NWnqRxc_Ce-C0Gn8xhqnxFK8w"
TITIK_AWAL_MBS = "PT Mensa Bina Sukses Surabaya"

# Inisialisasi Geolocator untuk Hitung Jarak
geolocator = Nominatim(user_agent="mbs_route_app_v2")

def get_koordinat_mbs():
    """Mengambil koordinat PT Mensa Bina Sukses"""
    try:
        loc = geolocator.geocode(TITIK_AWAL_MBS, timeout=5)
        if loc:
            return (loc.latitude, loc.longitude)
    except:
        pass
    # Default Koordinat Surabaya (Margomulyo/Surabaya) jika geocode timeout
    return (-7.2600, 112.7200)

COORD_MBS = get_koordinat_mbs()

def hitung_jarak_km(alamat_toko):
    """Menghitung perkiraan jarak (km) dari PT MBS ke Alamat Toko"""
    try:
        loc = geolocator.geocode(f"{alamat_toko}, Jawa Timur", timeout=3)
        if loc:
            coord_toko = (loc.latitude, loc.longitude)
            jarak = geodesic(COORD_MBS, coord_toko).km
            return round(jarak, 1)
    except:
        pass
    return None

def konversi_foto_ke_base64(image, max_dim=1024):
    img = image.copy()
    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    buffered = io.BytesIO()
    img.convert("RGB").save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def bersihkan_angka(val):
    if pd.isna(val) or val is None:
        return 0.0
    s = str(val).strip()
    if not s or s == '-' or s.lower() in ['nan', 'none']:
        return 0.0

    is_negative = False
    if s.startswith('(') and s.endswith(')'):
        is_negative = True
        s = s[1:-1].strip()
    elif s.endswith('-'):
        is_negative = True
        s = s[:-1].strip()
    elif s.startswith('-'):
        is_negative = True
        s = s[1:].strip()

    s = s.replace('Rp', '').replace(' ', '').strip()

    if '.' in s and ',' in s:
        if s.rfind('.') > s.rfind(','):
            s = s.replace(',', '')
        else:
            s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        parts = s.split(',')
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
            s = s.replace(',', '')
        else:
            s = s.replace(',', '.')
    elif '.' in s:
        parts = s.split('.')
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
            s = s.replace('.', '')

    try:
        num = float(s)
        return -num if is_negative else num
    except ValueError:
        return 0.0

def load_data_from_google_sheets():
    try:
        base_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet="
        s_histori = urllib.parse.quote("Data Histori Januari - Juli 2026")
        s_alamat = urllib.parse.quote("Data Alamat Toko")

        df_histori = pd.read_csv(base_url + s_histori, dtype=str)
        df_alamat = pd.read_csv(base_url + s_alamat, dtype=str)

        cols_to_fill = df_histori.columns[:4]
        df_histori[cols_to_fill] = df_histori[cols_to_fill].ffill()

        return df_histori, df_alamat
    except Exception as e:
        print(f"Error Load Sheets: {e}")
        return None, None

def panggil_ai_vision(image):
    base64_img = konversi_foto_ke_base64(image)
    headers = {
        "Authorization": f"Bearer {SYLOR_TOKEN.strip()}",
        "Content-Type": "application/json"
    }

    prompt = """
    Analisis foto jadwal harian ini.
    Ekstrak semua Nama Toko atau Kode Toko yang tertera di lembar jadwal ini.
    Kembalikan HANYA dalam format JSON valid seperti ini tanpa penjelasan atau markdown tambahan:
    {
        "toko_ditemukan": ["Toko A", "Toko B", "T-SUB-001"]
    }
    """

    payload = {
        "model": MODEL_AI,  # Memakai model pengganti (deepseek-chat / claude-3-opus)
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                ]
            }
        ],
        "temperature": 0.1
    }

    url = "https://api.sylorapi.com/v1/chat/completions"
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    
    if response.status_code == 200:
        res_data = response.json()
        response_text = res_data["choices"][0]["message"]["content"]
        clean_json = response_text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(clean_json)
        return parsed.get("toko_ditemukan", [])
    else:
        raise Exception(f"API Error ({response.status_code}): {response.text}")

def proses_rute_dan_histori(list_toko_foto, df_histori, df_alamat):
    hasil = []

    df_a = df_alamat.copy()
    df_h = df_histori.copy()

    df_a.columns = df_a.columns.astype(str).str.strip().str.lower()
    df_h.columns = df_h.columns.astype(str).str.strip().str.lower()

    col_kode_alamat = next((c for c in df_a.columns if 'cust' in c or 'code' in c or 'kode' in c), df_a.columns[1])
    col_nama_alamat = next((c for c in df_a.columns if 'nama' in c or 'customer' in c or 'toko' in c), df_a.columns[2])

    col_kode_histori = next((c for c in df_h.columns if 'id' in c or 'kode' in c or 'cust' in c), df_h.columns[1])
    col_nama_histori = next((c for c in df_h.columns if 'nama' in c or 'toko' in c), df_h.columns[2])
    col_produk_histori = next((c for c in df_h.columns if 'produk' in c or 'item' in c), df_h.columns[4])

    sales_cols = [c for c in df_h.columns[5:] if not str(c).startswith('unnamed') and str(c).strip() != '']
    month_cols = [c for c in sales_cols if 'grand' not in str(c).lower() and 'total' not in str(c).lower()]

    for c in month_cols:
        df_h[c] = df_h[c].apply(bersihkan_angka)

    cols_3_bulan_terakhir = month_cols[-3:] if len(month_cols) >= 3 else month_cols
    cols_4_bulan_awal = month_cols[:-3] if len(month_cols) > 3 else []

    df_h['sum_3_bulan'] = df_h[cols_3_bulan_terakhir].sum(axis=1) if cols_3_bulan_terakhir else 0
    df_h['sum_awal_tahun'] = df_h[cols_4_bulan_awal].sum(axis=1) if cols_4_bulan_awal else 0
    df_h['sum_7_bulan'] = df_h[month_cols].sum(axis=1)

    for _, toko in df_a.iterrows():
        kode = str(toko[col_kode_alamat]).strip()
        nama = str(toko[col_nama_alamat]).strip()
        alamat = str(toko.get('alamat', '-')).strip()

        wilayah = "Surabaya / Sekitar"
        if "sidoarjo" in alamat.lower():
            wilayah = "Sidoarjo"
        elif "gresik" in alamat.lower():
            wilayah = "Gresik"
        elif "pasuruan" in alamat.lower():
            wilayah = "Pasuruan"

        is_match = any(
            t.lower().strip() in kode.lower() or 
            t.lower().strip() in nama.lower() or 
            nama.lower() in t.lower().strip()
            for t in list_toko_foto
        )

        if is_match:
            match_kode = df_h[col_kode_histori].astype(str).str.strip().str.lower() == kode.lower()
            match_nama = df_h[col_nama_histori].astype(str).str.strip().str.lower() == nama.lower()
            tx_toko = df_h[match_kode | match_nama]

            sum_3m = tx_toko['sum_3_bulan'].sum() if not tx_toko.empty else 0.0
            sum_awal = tx_toko['sum_awal_tahun'].sum() if not tx_toko.empty else 0.0
            sum_7m = tx_toko['sum_7_bulan'].sum() if not tx_toko.empty else 0.0

            if sum_3m > 0 and sum_awal > 0:
                status_label = "✅ Toko Ini Selalu Order (Jan - Jul 2026)"
                detail_status = "3 Bulan Terakhir: ✅ | 7 Bulan Total: ✅"
                rank_order = 1
            elif sum_3m > 0 and sum_awal <= 0:
                status_label = "⚡ Toko Ini Order dalam 3 Bulan Terakhir"
                detail_status = "3 Bulan Terakhir: ✅ | 7 Bulan Total: ❌"
                rank_order = 2
            elif sum_3m <= 0 and sum_7m > 0:
                status_label = "⚠️ Vakum (Pernah Order Awal Tahun, 3 Bulan Terakhir Kosong)"
                detail_status = "3 Bulan Terakhir: ❌ | 7 Bulan Total: ✅"
                rank_order = 3
            else:
                status_label = "❌ Tidak Pernah Order Tahun 2026"
                detail_status = "3 Bulan Terakhir: ❌ | 7 Bulan Total: ❌"
                rank_order = 4

            produk_terbanyak = []
            if not tx_toko.empty:
                top_items = tx_toko.sort_values(by='sum_7_bulan', ascending=False).dropna(subset=[col_produk_histori])
                for _, item in top_items.iterrows():
                    p_nama = str(item[col_produk_histori]).strip()
                    p_total = item['sum_7_bulan']
                    if p_total > 0 and p_nama not in produk_terbanyak:
                        produk_terbanyak.append(p_nama)

            # Hitung Jarak (km) dari PT MBS
            jarak_km = hitung_jarak_km(alamat)
            txt_jarak = f"{jarak_km} km dari PT MBS" if jarak_km is not None else "Jarak Lihat di Maps"

            query_maps = urllib.parse.quote(f"{nama}, {alamat}")
            maps_single_url = f"https://www.google.com/maps/search/?api=1&query={query_maps}"

            hasil.append({
                "kode": kode,
                "nama": nama,
                "wilayah": wilayah,
                "alamat": alamat,
                "status_label": status_label,
                "detail_status": detail_status,
                "rank_order": rank_order,
                "jarak_km": jarak_km if jarak_km is not None else 999.0,
                "txt_jarak": txt_jarak,
                "produk_terbanyak": produk_terbanyak,
                "maps_url": maps_single_url
            })

    # Urutkan berdasarkan Wilayah, lalu Jarak Terdekat dari PT MBS
    hasil.sort(key=lambda x: (x['wilayah'], x['jarak_km'], x['rank_order']))

    # Link Google Maps Gabungan
    rute_maps_full = ""
    if hasil:
        origin = urllib.parse.quote(TITIK_AWAL_MBS)
        destination = urllib.parse.quote(f"{hasil[-1]['nama']}, {hasil[-1]['alamat']}")
        
        waypoints_list = [urllib.parse.quote(f"{t['nama']}, {t['alamat']}") for t in hasil[:-1]]
        waypoints = "|".join(waypoints_list)
        
        if waypoints:
            rute_maps_full = f"https://www.google.com/maps/dir/?api=1&origin={origin}&destination={destination}&waypoints={waypoints}"
        else:
            rute_maps_full = f"https://www.google.com/maps/dir/?api=1&origin={origin}&destination={destination}"

    return hasil, rute_maps_full