import streamlit as st
from PIL import Image
from processor import load_data_from_google_sheets, panggil_ai_vision, proses_rute_dan_histori

# Konfigurasi Halaman Web
st.set_page_config(page_title="Asisten MBS", layout="wide", page_icon="🚚")

# Load Data Google Sheets
st.cache_data.clear()
df_histori, df_alamat = load_data_from_google_sheets()

# ==========================================
# NAVIGASI MENU UTAMA
# ==========================================
st.sidebar.title("📌 Menu Utama")
menu_pilihan = st.sidebar.radio(
    "Pilih Fitur / Layanan:",
    ["1. Asisten Kunjungan & Data Histori", "2. Penghitungan Total Hari Ini"]
)

# Indikator Koneksi Google Sheets di Sidebar
if df_alamat is not None:
    st.sidebar.success("✅ Database Google Sheets Terhubung!")

# ==========================================
# MENU 1: ASISTEN KUNJUNGAN & DATA HISTORI
# ==========================================
if menu_pilihan == "1. Asisten Kunjungan & Data Histori":
    st.title("🚚 Asisten Kunjungan & Data Histori")
    st.write("Silakan pilih kode rute terlebih dahulu sebelum mengunggah jadwal harian.")

    # Sub-Menu Pilihan Kode Rute
    rute_pilihan = st.selectbox(
        "📍 Pilih Kode Rute / Call Plan:",
        ["RS CP-08"]  # Nantinya tinggal tambahkan rute lain di sini (misal: "RS CP-09", "RS CP-10")
    )

    st.markdown("---")
    st.sidebar.header("⚙️ Pengaturan Tampilan")
    sembunyikan_nol = st.sidebar.checkbox("Sembunyikan Toko Tanpa Order (7 Bulan Kosong)", value=False)

    st.subheader(f"📸 Upload Foto Jadwal Harian ({rute_pilihan})")
    uploaded_file = st.file_uploader("Pilih foto jadwal harian...", type=["jpg", "jpeg", "png"])

    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption=f"Foto Jadwal Terupload - Rute {rute_pilihan}", use_container_width=True)

        if st.button("🚀 Proses Jadwal & Buat Rute Maps"):
            with st.spinner("AI sedang membaca foto, menyusun rute & menghitung jarak dari PT MBS Waru..."):
                try:
                    list_toko_foto = panggil_ai_vision(image)
                    st.info(f"🔍 **Toko Terdeteksi di Foto oleh AI:** {', '.join(list_toko_foto)}")

                    hasil_rekomendasi, rute_maps_full = proses_rute_dan_histori(list_toko_foto, df_histori, df_alamat)

                    if rute_maps_full:
                        st.markdown(f"""
                        [
                            
                                🗺️ Buka Rute Navigasi Keseluruhan di Google Maps (Start dari PT MBS Waru)
                            
                        ]({rute_maps_full})
                        """, unsafe_allow_html=True)
                        st.write("")

                    st.subheader(f"📍 Rute Call Plan Hari Ini [{rute_pilihan}] (Diurutkan dari Jarak Terdekat)")

                    if not hasil_rekomendasi:
                        st.warning("Data toko terdeteksi, namun tidak ditemukan kecocokan pada Data Alamat Toko.")
                    else:
                        for idx, res in enumerate(hasil_rekomendasi, 1):
                            if sembunyikan_nol and "Tidak Pernah Order" in res['status_label']:
                                continue

                            with st.expander(f"#{idx} [{res['wilayah']}] {res['nama']} — 📏 {res['txt_jarak']}", expanded=True):
                                col1, col2 = st.columns([3, 1])
                                
                                with col1:
                                    st.write(f"🏢 **Area / Kota:** {res['wilayah']}")
                                    st.write(f"📍 **Alamat:** {res['alamat']}")
                                    st.write(f"📏 **Estimasi Jarak dari Start (PT MBS Waru):** `{res['txt_jarak']}`")
                                    st.markdown(f"📊 **Status Order:** {res['status_label']}")
                                    
                                    # Tampilkan Catatan / NOTE jika ada di Google Sheets
                                    if res.get('catatan'):
                                        st.error(f"📌 **CATATAN TOKO:** {res['catatan']}")

                                with col2:
                                    st.markdown(f"[📍 Buka Lokasi Toko Ini]({res['maps_url']})")

                                st.markdown("**🛒 Produk yang Pernah Dipesan:**")
                                if res['produk_terbanyak']:
                                    for p_idx, p_nama in enumerate(res['produk_terbanyak'][:10], 1):
                                        st.write(f"{p_idx}. {p_nama}")
                                else:
                                    st.caption("⚠️ *Tidak ada riwayat order barang di tahun 2026.*")

                except Exception as e:
                    st.error(f"Terjadi kesalahan saat memproses data: {e}")

# ==========================================
# MENU 2: PENGHITUNGAN TOTAL HARI INI
# ==========================================
elif menu_pilihan == "2. Penghitungan Total Hari Ini":
    st.title("🧮 Penghitungan Total Hari Ini")
    st.info("ℹ️ Halaman ini siap digunakan. Perintah dan fitur kalkulasi akan ditambahkan pada tahap berikutnya.")