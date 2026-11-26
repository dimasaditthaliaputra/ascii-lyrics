# lyricviz — ASCII Lyrics Visualizer

Visualizer lirik di terminal: lirik muncul sinkron dengan timestamp, sementara di sisi lain
layar ada "dunia kecil" ASCII yang hidup — bunga yang mekar, kelopak berjatuhan, salju, hujan,
hati 3D yang berputar, album artwork yang diubah jadi ASCII, dan transisi antar-scene.

Semua visual dibuat dari karakter teks (ASCII/Unicode) + warna terminal. Tidak ada gambar
raster yang ditampilkan langsung; gambar album dikonversi ke karakter dengan Pillow.

Isi bawaan:

| Lagu | Folder | Keterangan |
|---|---|---|
| Drop Dead — Olivia Rodrigo | `songs/drop_dead/` | 8 scene floral: intro artwork, kamar malam, bola kristal, Versailles, detak jantung, chorus hati 3D, semua bunga mekar bersamaan, outro satu mawar |
| First Snow (demo) | `songs/winter_demo/` | Lirik orisinal untuk demo suasana: christmas → sad → dreamy → dark |

---

## 1. Instalasi

Butuh Python 3.9+.

```bash
cd ascii_lyric_visualizer
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt      # rich, Pillow, PyYAML
pip install pygame-ce                # opsional: hanya kalau mau audio ikut diputar
```

## 2. Menjalankan

Satu entry point:

```bash
python main.py                  # lagu default: drop_dead
python main.py winter_demo      # lagu lain (nama folder di songs/)
python main.py path/ke/song.yaml
python -m lyricviz drop_dead    # sama saja
```

Jalankan di terminal sungguhan (bukan panel output IDE). Ukuran minimal 60×18; paling bagus
sekitar 120×36 ke atas, dengan font yang punya glyph seperti ❀ ✿ ♥ ✦.

### Kontrol keyboard

| Tombol | Fungsi |
|---|---|
| `spasi` | pause / lanjut |
| `←` / `→` | mundur / maju 5 detik |
| `n` / `p` | scene berikutnya / sebelumnya |
| `h` | tampilkan / sembunyikan status bar |
| `r` | ulang dari awal |
| `q` / `Esc` | keluar |

### Opsi command line

| Opsi | Fungsi |
|---|---|
| `--start 30` | mulai dari detik ke-30 |
| `--until 45` | berhenti di detik ke-45 |
| `--loop` | ulang terus |
| `--fps 24` | target frame rate (default 30); turunkan kalau terasa berat |
| `--speed 0.5` | putar lebih lambat (untuk mengecek timing) |
| `--color truecolor\|256\|standard\|none` | paksa sistem warna (default: deteksi otomatis) |
| `--no-color` | sama dengan `--color none` |
| `--ascii` | hanya karakter ASCII murni |
| `--no-audio` | jangan putar audio walau ada di config |
| `--no-hud` | sembunyikan status bar |
| `--list` | daftar lagu di `songs/` |
| `--validate` | cek config + tampilkan timeline scene/lirik |
| `--snapshot 30 --size 120x36` | cetak satu frame di detik 30 lalu keluar |
| `--benchmark` | jalankan loop real-time tanpa layar, laporkan fps & akurasi sinkron lirik |

---

## 3. Struktur folder

```
ascii_lyric_visualizer/
├── main.py                  # entry point
├── requirements.txt
├── lyricviz/
│   ├── cli.py               # argumen command line, --validate/--snapshot/--benchmark
│   ├── app.py               # Visualizer.render(t) + loop real-time (asyncio)
│   ├── clock.py             # jam lagu presisi tinggi (pause/seek/speed)
│   ├── config.py            # baca & validasi song.yaml
│   ├── lyrics.py            # LyricsManager: timing baris, kata, dan karakter
│   ├── lyrics_view.py       # render lirik: efek typing, emphasis, font besar
│   ├── scenes.py            # SceneManager, layout kiri/kanan/tengah, transisi
│   ├── transitions.py       # dissolve, wipe, bloom, petal_rain, fade, flash
│   ├── layers/              # semua elemen visual (registry "type: ...")
│   │   ├── base.py          # kelas Layer + @register
│   │   ├── background.py    # gradient, stars, moon, clouds, fog, bokeh, ...
│   │   ├── particles.py     # petals, snow, rain, sparkles, hearts, burst, ...
│   │   └── illustrations.py # flower, garden, rose, mesh, sprite, phone, ...
│   ├── art/                 # bunga prosedural, mawar spiral, mesh 3D, sprite
│   ├── artwork.py           # konversi album artwork -> ASCII + layer artwork
│   ├── canvas.py            # buffer sel (glyph, warna depan, warna latar)
│   ├── terminal.py          # deteksi kemampuan terminal + penulis frame
│   ├── themes.py            # palet warna & preset atmosfer
│   ├── font.py              # font blok 5 baris untuk judul/lirik besar
│   ├── keys.py              # input keyboard non-blocking
│   └── audio.py             # pemutar audio opsional (pygame-ce)
├── songs/
│   ├── drop_dead/           # song.yaml + artwork.png
│   └── winter_demo/
└── tools/
    ├── tap_sync.py          # rekam timestamp lirik dengan mengetuk spasi
    ├── frame_to_png.py      # render frame ke PNG (preview / QA visual)
    └── make_sample_artwork.py
```

### Cara kerjanya

```
Clock ──t──► SceneManager ──► Scene (stack layer, belakang → depan) ──► Canvas
                 │ (transisi: render 2 scene, lalu blend per sel)          │
                 └────────────► LyricsView (lirik di atas ilustrasi) ──────┤
                                                                            ▼
                                       FrameWriter: hanya baris yang berubah, satu kali tulis
```

- **Frame-based.** Setiap frame membaca jam, merender ulang semua layer, lalu menunggu sisa
  waktu frame dengan `asyncio.sleep`. Tidak ada `sleep` per baris lirik, jadi semua animasi
  tetap bergerak bersamaan.
- **Tanpa flicker.** Frame digambar di buffer dulu; ke terminal hanya dikirim baris yang
  berubah, dibungkus *synchronized output* sehingga terminal yang mendukung menampilkannya
  sekaligus.
- **Sinkronisasi.** Semua efek lirik dihitung dari "umur" tiap karakter (`t - waktu_karakter`),
  jadi tampilan selalu mengikuti jam, termasuk setelah seek atau pause.
- **Responsif.** Ukuran terminal dibaca tiap frame; layout dihitung ulang dalam proporsi.

---

## 4. Format `song.yaml`

```yaml
song:
  title: First Snow
  artist: lyricviz demo
  duration: 42.0          # detik
  bpm: 118                # opsional, informasi saja
  audio: song.mp3         # opsional, relatif ke folder lagu (butuh pygame-ce)
  audio_offset: 0.0       # geser audio kalau intro file berbeda

artwork:
  image: artwork.png      # opsional; kalau file tidak ada dipakai cover pengganti
  contrast: 1.35
  saturation: 1.25
  # enabled: false        # matikan artwork untuk lagu ini

defaults:                 # berlaku untuk semua scene kecuali di-override
  theme: dusk_rose
  gap: 0.15               # jeda otomatis sebelum baris berikutnya
  transition: {type: dissolve, duration: 1.2}
  lyrics: {effect: typewriter, glass: true}

lyrics:
  - {t: 1.0, end: 4.2, text: "*Snow* on the windowsill"}
  - ...

scenes:
  - name: first_snow
    start: 0
    ...
```

### 4.1 Lirik

Setiap baris diatur sendiri-sendiri — tidak ada delay statis yang sama untuk semua baris.

| Key | Arti |
|---|---|
| `t` | detik baris mulai dinyanyikan (wajib) |
| `end` / `dur` | detik selesai, atau durasi. Kalau keduanya tidak ada: sampai baris berikutnya dikurangi `gap` |
| `text` | teks baris (wajib). `*kata*` = penekanan, `\*` = bintang biasa |
| `reveal` | lama efek mengetik dalam detik (default 85% durasi baris) |
| `effect` | `typewriter`, `fade`, `rise`, `wave`, `drop`, `pop` |
| `words` | waktu mulai tiap kata, misalnya `[42.0, 42.35, 42.9]` (jumlahnya harus sama dengan jumlah kata) |
| `big` | `true` = tampil dengan font blok besar (kalau muat) |

Tanpa `words`, waktu tiap kata diperkirakan dari jumlah suku katanya, lalu huruf-huruf
dalam kata itu muncul berurutan. Pakai `words` untuk bagian yang penyanyinya menahan
atau mempercepat kata.

Kata yang diberi `*...*` akan berdenyut warna, bercahaya, dan memercikkan sparkle saat
muncul. Kata yang sedang dinyanyikan disorot (gaya karaoke); baris yang sudah lewat
meredup.

Lirik dikelompokkan per scene berdasarkan waktu. Saat scene berganti, lirik lama baru
memudar **setelah** baris terakhirnya selesai, jadi tidak pernah terpotong.

### 4.2 Scene

| Key | Arti |
|---|---|
| `name` | nama scene (muncul di status bar & `--validate`) |
| `start` | detik scene mulai; berakhir saat scene berikutnya mulai |
| `layout` | posisi lirik: `left`, `right`, `center`, `top`, `bottom` (default selang-seling kiri/kanan) |
| `split` | lebar kolom lirik untuk `left`/`right` (default 0.42) |
| `theme` | nama tema, atau `{base: dusk_rose, accent: "#ff0000", ...}` untuk override |
| `atmosphere` | preset background: `romantic`, `dreamy`, `night`, `christmas`, `sad`, `dark` |
| `layers` | daftar layer visual, digambar dari atas ke bawah daftar (belakang → depan) |
| `transition` | `{type: ..., duration: detik, color: "@accent"}` — cara masuk ke scene ini |
| `lyrics` | gaya lirik scene ini: `effect`, `align` (`left`/`center`/`right`), `glass`, `glass_strength`, `colors`, `emph`, `past`, `sing`, `glow` |

Tipe transisi: `dissolve`, `wipe`, `wipe_left`, `bloom` (iris berbentuk kelopak),
`petal_rain`, `fade` (lewat hitam), `flash` (lewat cahaya putih), `cut`.

Setiap layout menghasilkan tiga area yang bisa dipakai layer lewat `region`:
`full` (seluruh layar), `art` (sisi ilustrasi), `lyrics` (kolom lirik).

### 4.3 Warna dan tema

Nilai warna bisa berupa hex (`"#ff8fb8"`) atau referensi ke tema dengan `@`
(`"@accent"`, `"@petals"`, `"@glow"`). Jadi satu definisi scene bisa dipakai ulang
dengan tema lain.

Tema bawaan: `dusk_rose`, `midnight`, `lavender_dream`, `versailles_gold`, `passion`,
`bloom`, `christmas`, `rain`, `shadow`. Key tema: `sky`, `lyric`, `emph`, `past`, `sing`,
`glow`, `accent`, `petals`, `leaf`, `stem`, `center` (+ `gold` di `versailles_gold`).

Menambah tema: tambahkan entri di `THEMES` pada `lyricviz/themes.py`, atau tulis inline
di scene: `theme: {base: midnight, accent: "#7fffd4", petals: ["#7fffd4", "#ffffff"]}`.

---

## 5. Menambah lagu baru

1. Buat folder `songs/nama_lagu/` berisi `song.yaml` (salin `songs/winter_demo/song.yaml`
   sebagai titik awal — itu contoh terkecil yang lengkap).
2. Isi `lyrics:` dengan teks dan perkiraan `t`.
3. (Opsional) taruh cover album di folder itu dan isi `artwork.image`.
4. (Opsional) taruh file audio dan isi `song.audio`, lalu `pip install pygame-ce`.
5. Rapikan timing dengan `tap_sync` (bagian berikut).
6. Cek dengan `python main.py nama_lagu --validate`, lalu jalankan.

### Merekam timing dengan `tools/tap_sync.py`

Ketuk spasi tepat saat setiap baris mulai dinyanyikan:

```bash
python tools/tap_sync.py nama_lagu             # coba dulu: hasil hanya ditampilkan
python tools/tap_sync.py nama_lagu --write     # simpan ke song.yaml (+ song.yaml.bak)
python tools/tap_sync.py nama_lagu --from 7    # ulang mulai baris ke-7 saja
```

- Kalau `song.audio` ada (dan pygame-ce terpasang), lagu diputar otomatis setelah hitung
  mundur 3 detik.
- Kalau tidak ada audio: putar lagunya di aplikasi lain, lalu tekan spasi tepat saat lagu
  mulai (ketukan itu dihitung sebagai 0.00 detik), kemudian lanjut mengetuk tiap baris.
- Tombol: `spasi` ketuk, `u` batalkan ketukan terakhir, `s` lewati baris (waktunya tetap),
  `q` selesai.

Yang diubah oleh `--write`: `t` tiap baris yang diketuk; `end` disesuaikan ke awal baris
berikutnya (tapi tidak pernah melewati awal scene berikutnya); `words` ikut bergeser;
`start` tiap scene ikut bergeser bersama baris pertamanya. Komentar dan format file
dibiarkan apa adanya.

---

## 6. Membuat scene baru

Scene hanyalah tumpukan layer. Contoh: scene hujan di sisi kiri dengan satu bunga yang
mekar pelan, lirik di kanan:

```yaml
  - name: rainy_window
    start: 30.0
    layout: right
    theme: rain
    atmosphere: sad                      # gradient + awan + hujan + kabut
    transition: {type: petal_rain, duration: 1.5}
    lyrics: {effect: fade, align: left}
    layers:
      - {type: flower, pos: [0.5, 0.95], height: 0.5, size: 0.18,
         grow: [[0, 0], [3, 1]], bloom: [[2, 0], [6, 1]], colors: ["#8fb8de", "#e6f2ff"]}
      - {type: sparkles, rate: 3, start: 4.0, fade_in: 1.5}
      - {type: vignette, strength: 0.6}
```

Kunci yang berlaku untuk **semua** layer:

| Key | Arti |
|---|---|
| `type` | jenis layer (lihat tabel di bawah) |
| `region` | `full`, `art`, atau `lyrics` |
| `pos` | `[x, y]` pecahan 0..1 di dalam region |
| `start` / `until` | detik (relatif ke awal scene) layer muncul / hilang |
| `fade_in` / `fade_out` | durasi muncul / hilang perlahan |
| `opacity` | 0..1 |
| `seed` | ganti pola acak (posisi bintang, bunga, dll.) |

Banyak angka bisa dibuat **keyframe**: `[[detik, nilai], ...]`, diinterpolasi linear.
Contoh `rate: [[0, 4], [5, 20]]` membuat kelopak makin deras selama 5 detik. Parameter
yang mendukung keyframe ditandai \* di tabel.

Tips komposisi:
- Taruh background (gradient, stars, bokeh) paling atas daftar, efek depan (petals,
  vignette) paling bawah.
- Satu fokus utama per scene (bunga besar, bola kristal, hati 3D) + 2–3 lapisan
  atmosfer sudah cukup ramai.
- Pakai `start` + `fade_in` untuk menyelaraskan kemunculan elemen dengan baris lirik
  tertentu (misalnya ilustrasi baru muncul saat kata kunci dinyanyikan).
- Cek hasilnya tanpa menjalankan seluruh lagu:
  `python main.py nama_lagu --start 29` atau
  `python tools/frame_to_png.py nama_lagu 31.5 --out previews/`.

### 6.1 Daftar layer

**Background & atmosfer**

| Layer | Parameter |
|---|---|
| `gradient` | `colors` (default `@sky`), `to` + `shift: [t0, t1]` (berubah warna perlahan), `breathe` |
| `stars` | `density`, `band: [atas, bawah]`, `twinkle`, `shooting` (detik antar bintang jatuh, 0 = mati), `colors` |
| `moon` | `pos`, `size`, `phase` (0 purnama .. 1 sabit tipis), `color`, `halo` |
| `clouds` | `density`, `speed`, `band`, `color` |
| `fog` | `strength`, `color`, `band` |
| `bokeh` | `count`, `colors`, `strength`, `size` — bola cahaya blur yang melayang |
| `rays` | `source: [x, y]`, `count`, `strength`, `color` — sinar cahaya |
| `hills` | `colors` (jauh → dekat), `height`, `speed`, `grass` |
| `wallpaper` | `color`, `strength` — pola damask istana |
| `pulse` | `bpm` (+ `offset`, `sharp`) atau `hits: [detik, ...]` (+ `decay`), `color`, `strength` |
| `vignette` | `strength` — sudut layar lebih gelap |

**Partikel**

| Layer | Parameter |
|---|---|
| `petals` | `rate`\*, `wind`\*, `swirl`\*, `fall`, `flutter`, `colors`, `prewarm` |
| `snow` | `rate`\*, `wind`\*, `fall`, `color` |
| `rain` | `rate`\*, `wind`\*, `fall`, `color` — dengan percikan di tanah |
| `sparkles` | `rate`\*, `colors` |
| `fireflies` | `count`, `color` |
| `hearts` | `rate`\*, `rise`, `colors` |
| `burst` | `at: [detik, ...]`, `origin: [x, y]`, `count`, `power`, `gravity`, `colors` — ledakan kelopak |

Partikel punya kedalaman: yang jauh kecil, redup, dan lambat; yang dekat besar, terang,
dan cepat (efek parallax / pseudo-3D).

**Ilustrasi**

| Layer | Parameter |
|---|---|
| `flower` | `pos` (pangkal batang), `height`, `size`, `grow`\*, `bloom`\*, `petals`, `colors`, `stem`, `leaf`, `center`, `sway`, `spin`, `phase` |
| `garden` | `count`, `height: [min, max]`, `size`, `grow: [t0, t1]`, `bloom: [t0, t1]` **atau** `bloom_at` (semua mekar bersamaan) + `bloom_spread`, `ground`, `grass`, `colors` |
| `rose` | `pos`, `size`, `bloom`\*, `spin`, `stem`, `deep`, `light`, `leaf` — mawar spiral |
| `mesh` | `shape: heart \| flower`, `pos`, `size`, `spin`, `pitch`, `yaw`, `wobble`, `bpm` (hati berdetak), `bloom`\* (bunga), `colors` — objek 3D berputar dengan pencahayaan |
| `sprite` | `name: butterfly \| cherub \| couple \| snowman`, `pos`, `fps`, `bob`, `bob_speed`, `palette`, `bold` |
| `butterflies` | `count`, `big` (berapa yang besar), `speed`, `colors`, `accent` |
| `phone` | `pos`, `width`, `height`, `scroll`, `screen`, `glow`, `body`, `text`, `accent` |
| `window` | `box: [x, y, w, h]`, `pots`, `frame`, `night`, `moon`, `curtain`, `flowers` |
| `frame` | `box`, `color`, `panel` — bingkai emas barok |
| `crystal_ball` | `pos`, `size`, `content` (nama sprite), `reveal` (detik kabut menipis), `mist`, `glass`, `stand` |
| `heartbeat` | `bpm`, `y`, `amp`, `speed`, `decay`, `color`, `heart_y` — monitor detak jantung |
| `tree` | `pos` (pangkal), `size`, `color` — pohon Natal dengan lampu berkedip |
| `title` | `text`, `subtitle`, `pos`, `colors`, `letter_delay`, `sub_color` — judul font blok |
| `caption` | `text`, `pos`, `char_delay`, `color`, `bold` |
| `artwork` | lihat bagian 7 |

`palette` pada `sprite` memetakan kunci warna sprite ke warna: `cherub` → `w` sayap,
`f` bulu, `h` rambut, `s` kulit; `couple` → `a`, `b`; `snowman` → `h` topi, `c` wortel,
`k` kancing, `a` lengan, `s` badan; `butterfly` → `w` sayap, `p` motif, `b` badan.

### 6.2 Membuat jenis layer baru (Python)

Buat kelas turunan `Layer`, daftarkan dengan `@register`, lalu impor modulnya di
`lyricviz/layers/__init__.py`:

```python
# lyricviz/layers/lanterns.py
import math

from .base import Layer, register


@register("lanterns")
class Lanterns(Layer):
    """Lampion yang naik perlahan sambil bergoyang."""

    default_region = "full"

    def draw(self, cv, t, rect, alpha):
        col = self.color("color", "@glow")            # hex atau "@kunci_tema"
        for i in range(int(self.num("count", 5))):
            x = rect.x + rect.w * (i + 0.5) / 5 + math.sin(t + i) * 2
            y = rect.y2 - ((t * self.num("speed", 1.5) + i * 7) % (rect.h + 4))
            cv.glow(x, y, 5, col, 0.3 * alpha)        # cahaya di latar
            cv.text(x - 1, y, "(@)", col, bold=True, alpha=alpha)
```

```python
# lyricviz/layers/__init__.py
from . import background, illustrations, particles, lanterns  # noqa: F401
```

Setelah itu `- {type: lanterns, count: 6}` bisa dipakai di scene mana pun.

API yang tersedia:
- **Kanvas:** `cv.put`, `cv.text`, `cv.glow`, `cv.tint`, `cv.blit` (sprite), `cv.darken_rect`.
- **Helper layer:** `self.num`, `self.kf` (keyframe), `self.color`, `self.colors`,
  `self.g(unicode, ascii)` untuk glyph cadangan.
- **Simulasi:** untuk layer yang menyimpan state (partikel), override `update(dt, t, rect)`
  dan `reset()`. `reset()` dipanggil setelah seek.

---

## 7. Album artwork

Layer `artwork` mengonversi gambar dari `artwork.image` menjadi karakter. Prosesnya:
sesuaikan rasio sel terminal, autocontrast, tajamkan tepi, petakan kecerahan ke glyph
sambil mempertahankan warna piksel. Hasil konversi di-cache per ukuran.

| `mode` | Kegunaan |
|---|---|
| `focus` | besar di tengah, larut masuk dari tengah, sulur bunga tumbuh mengelilingi (intro) |
| `decor` | polaroid kecil tergantung dan berayun (verse) |
| `inspired` | digambar ulang dengan glyph bunga ✿❀ dan kilau bergelombang (chorus) |
| `fade` | hancur menjadi kelopak yang terbang (outro); `duration` = lama prosesnya |

| `style` | Hasil |
|---|---|
| `blocks` | setengah-blok `▀` (2 piksel per sel, paling detail) |
| `ascii` | ramp karakter ASCII klasik |
| `floral` | ramp glyph bunga |

Parameter lain: `size`, `pos`, `reveal`, `border`, `border_time`, `caption`.

Kalau file gambar tidak ditemukan, dipakai cover pengganti buatan program (mawar senja).
`songs/drop_dead/artwork.png` adalah cover pengganti itu, **bukan** cover album asli.
Timpa file itu dengan gambar cover milikmu (format apa pun yang dibaca Pillow) untuk
memakai artwork sebenarnya.

---

## 8. Terminal yang terbatas

- **Warna:** dideteksi otomatis (truecolor → 256 → 16 warna → tanpa warna). `NO_COLOR`
  dihormati. Paksa dengan `--color ...`.
- **Unicode:** kalau encoding terminal bukan UTF-8, atau dengan `--ascii`, semua glyph
  khusus diganti padanan ASCII (❀ → `*`, █ → `#`, ♥ → `<`, ...).
- **Tanpa warna:** panel di belakang lirik dikosongkan supaya teks tetap terbaca.
- **Terminal kecil:** di bawah 60×18 muncul pesan untuk memperbesar jendela.
- **Berat / patah-patah:** jalankan dengan `--fps 24` atau perkecil jendela terminal
  (biaya render sebanding dengan jumlah sel).

---

## 9. Mengecek hasil

```bash
python main.py drop_dead --validate          # timeline + peringatan timing
python main.py drop_dead --benchmark         # fps nyata + seberapa cepat tiap baris muncul
python main.py drop_dead --snapshot 30 --size 120x36
python tools/frame_to_png.py drop_dead 6 14 22 30 40 45 56 --out previews/
```

`--validate` memperingatkan baris yang bertumpuk, scene yang mulai di tengah baris (lirik
akan terbelah), transisi yang lebih panjang dari scene-nya, serta file audio/artwork yang
tidak ada.

Hasil `--benchmark` di MacBook pengembang, ukuran 120×36, truecolor: sekitar 27 fps,
rata-rata 19 ms per frame, dan tiap baris lirik muncul paling lambat ~30 ms (kurang dari
satu frame) setelah timestamp-nya. Frame saat transisi lebih berat (dua scene dirender
sekaligus, ~34 ms) selama 1–2 detik.

---

## 10. Catatan

- Timestamp di `songs/drop_dead/song.yaml` adalah perkiraan buatan tangan, bukan hasil
  sinkronisasi dengan rekaman. Sesuaikan dengan `tools/tap_sync.py` menggunakan file
  lagumu sendiri.
- Lirik dan cover album adalah milik pemegang hak ciptanya. Project ini tidak menyertakan
  file audio atau cover asli.
