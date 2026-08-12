import streamlit as st
from PIL import Image
from processor import load_data_from_google_sheets, panggil_ai_vision, proses_rute_dan_histori

# Setup Halaman Streamlit
st.set_page_config(page_title="Asisten Kunjungan Toko MBS", layout="wide", page_icon="🚚")
st.title("🚚 Asisten Rute & Status Kunjungan Toko")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Pengaturan Tampilan")
sembunyikan_nol = st.sidebar.checkbox("Sembunyikan Toko Tanpa Order (7 Bulan Kosong)", value=False)

# Load Data dari Backend
st.cache_data.clear()
df_histori, df_alamat = load_data_from_google_sheets()

if df_alamat is not None:
    st.sidebar.success("✅ Database Google Sheets Terhubung!")

# --- TAMPILKAN APLIKASI ---
st.subheader("📸 Upload Foto Jadwal Kunjungan Harian")
uploaded_file = st.file_uploader("Pilih foto jadwal harian...", type=["jpg", "jpeg", "png"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Foto Jadwal Terupload", use_container_width=True)

    if st.button("🚀 Proses Jadwal & Buat Rute Maps"):
        with st.spinner("AI sedang membaca foto dan mengecek status histori order..."):
            try:
                # 1. Panggil AI Vision
                list_toko_foto = panggil_ai_vision(image)
                st.info(f"🔍 **Toko Terdeteksi di Foto oleh AI:** {', '.join(list_toko_foto)}")

                # 2. Olah Data Rute
                hasil_rekomendasi, rute_maps_full = proses_rute_dan_histori(list_toko_foto, df_histori, df_alamat)

                # 3. Tombol Rute Navigasi Google Maps Gabungan
                if rute_maps_full:
                    st.markdown(f"""
                    <a href="{rute_maps_full}" target="_blank">
                        <button style="background-color: #4CAF50; color: white; padding: 12px 20px; border: none; border-radius: 8px; cursor: pointer; font-size: 16px; font-weight: bold; width: 100%;">
                            🗺️ Buka Rute Navigasi Keseluruhan di Google Maps (Start dari PT MBS)
                        </button>
                    </a>
                    """, unsafe_allow_html=True)
                    st.write("")

                # 4. Tampilkan List Toko & Status Order
                st.subheader("📍 Urutan Kunjungan Toko & Status Keaktifan")

                if not hasil_rekomendasi:
                    st.warning("Data toko terdeteksi, namun tidak ditemukan kecocokan pada Data Alamat Toko.")
                else:
                    for idx, res in enumerate(hasil_rekomendasi, 1):
                        # Filter sembunyikan jika tidak pernah order
                        if sembunyikan_nol and "Tidak Pernah Order" in res['status_label']:
                            continue

                        with st.expander(f"#{idx} [{res['wilayah']}] {res['nama']} ({res['kode']}) — {res['status_label']}", expanded=True):
                            col1, col2 = st.columns([3, 1])
                            
                            with col1:
                                st.write(f"🏢 **Area / Kota:** {res['wilayah']}")
                                st.write(f"📍 **Alamat:** {res['alamat']}")
                                st.markdown(f"📊 **Status Keaktifan:** `{res['detail_status']}`")

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