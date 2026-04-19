"""
Audio Analyzer - Ses sınıflandırma ve analiz modülü.
librosa ile ses özelliklerini çıkarıp türünü belirler.
"""
import os
import subprocess
import tempfile
import numpy as np


def analyze_audio(video_path: str) -> dict:
    """
    Video dosyasından sesi çıkarıp analiz eder.
    Returns dict with keys: 'has_audio', 'description', 'features'
    """
    result = {
        'has_audio': False,
        'description': '',
        'features': {}
    }

    # Extract audio to WAV
    wav_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            wav_path = tmp.name

        proc = subprocess.run(
            ['ffmpeg', '-i', video_path, '-vn', '-acodec', 'pcm_s16le',
             '-ar', '16000', '-ac', '1', '-y', wav_path],
            capture_output=True, text=True, timeout=120
        )

        if proc.returncode != 0 or not os.path.exists(wav_path) or os.path.getsize(wav_path) < 200:
            return result

        import librosa
        import soundfile as sf

        # Load audio
        y, sr = librosa.load(wav_path, sr=16000, mono=True)

        if len(y) < sr * 0.5:  # Less than 0.5 seconds
            return result

        result['has_audio'] = True
        duration = len(y) / sr

        # ── Feature Extraction ──
        # 1. RMS Energy (loudness)
        rms = librosa.feature.rms(y=y)[0]
        avg_rms = float(np.mean(rms))
        max_rms = float(np.max(rms))

        # 2. Zero Crossing Rate (noise vs tonal)
        zcr = librosa.feature.zero_crossing_rate(y)[0]
        avg_zcr = float(np.mean(zcr))

        # 3. Spectral Centroid (brightness)
        spec_cent = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        avg_centroid = float(np.mean(spec_cent))

        # 4. Spectral Rolloff
        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
        avg_rolloff = float(np.mean(rolloff))

        # 5. MFCCs (timbre)
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        mfcc_means = [float(np.mean(m)) for m in mfccs]

        # 6. Tempo (BPM)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo_val = float(tempo) if np.isscalar(tempo) else float(tempo[0]) if len(tempo) > 0 else 0

        # 7. Harmonic vs Percussive
        y_harmonic, y_percussive = librosa.effects.hpss(y)
        harmonic_ratio = float(np.sum(y_harmonic**2) / (np.sum(y**2) + 1e-10))

        # 8. Spectral Bandwidth
        spec_bw = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
        avg_bandwidth = float(np.mean(spec_bw))

        # 9. Spectral Flatness (noise-like vs tonal)
        flatness = librosa.feature.spectral_flatness(y=y)[0]
        avg_flatness = float(np.mean(flatness))

        result['features'] = {
            'duration': duration,
            'avg_rms': avg_rms,
            'max_rms': max_rms,
            'avg_zcr': avg_zcr,
            'avg_centroid': avg_centroid,
            'avg_rolloff': avg_rolloff,
            'tempo': tempo_val,
            'harmonic_ratio': harmonic_ratio,
            'avg_bandwidth': avg_bandwidth,
            'avg_flatness': avg_flatness,
        }

        # ── Sound Classification ──
        detected_sounds = []

        # Silence check
        if avg_rms < 0.005:
            detected_sounds.append("sessizlik/çok düşük ses")
            result['description'] = "Videoda neredeyse hiç ses yok (sessiz)."
            return result

        # Music detection
        if harmonic_ratio > 0.4 and 60 < tempo_val < 200 and avg_flatness < 0.1:
            detected_sounds.append("müzik")

        # Speech detection
        if 200 < avg_centroid < 3000 and avg_zcr < 0.15 and harmonic_ratio > 0.2:
            detected_sounds.append("insan konuşması")

        # High-pitched sounds (birds, whistles)
        if avg_centroid > 3000 and avg_zcr > 0.1:
            detected_sounds.append("yüksek frekanslı sesler (kuş sesi, ıslık vb.)")

        # Low frequency sounds (traffic, machinery)
        if avg_centroid < 500 and avg_rms > 0.02:
            detected_sounds.append("düşük frekanslı sesler (trafik, makine, motor vb.)")

        # Percussive sounds (drums, clapping, impacts)
        if harmonic_ratio < 0.3 and avg_zcr > 0.1:
            detected_sounds.append("vurmalı/darbe sesleri (alkış, vuruş vb.)")

        # Nature/ambient sounds
        if 0.05 < avg_flatness < 0.4 and avg_bandwidth > 2000:
            detected_sounds.append("doğa/ortam sesleri (rüzgar, su, yaprak hışırtısı vb.)")

        # Noise-like sounds
        if avg_flatness > 0.4:
            detected_sounds.append("gürültü/beyaz ses benzeri sesler")

        # Loud/energetic sounds
        if avg_rms > 0.1:
            detected_sounds.append("yüksek sesli/enerjik ses")

        # Build description
        if detected_sounds:
            desc_parts = [
                f"Ses süresi: {duration:.1f} saniye.",
                f"Ses seviyesi: {'yüksek' if avg_rms > 0.05 else 'orta' if avg_rms > 0.01 else 'düşük'}.",
                f"Tempo: {tempo_val:.0f} BPM.",
                f"Tespit edilen ses türleri: {', '.join(detected_sounds)}.",
                f"Harmonik oran: %{harmonic_ratio*100:.0f} (yüksek=müzik/konuşma, düşük=gürültü/vuruş).",
                f"Spektral parlaklık: {'parlak/tiz' if avg_centroid > 3000 else 'orta' if avg_centroid > 1000 else 'koyu/bas'}."
            ]
            result['description'] = ' '.join(desc_parts)
        else:
            result['description'] = f"Ses tespit edildi ({duration:.1f}s) ancak belirli bir ses türü sınıflandırılamadı."

    except Exception as e:
        result['description'] = f"Ses analizi hatası: {str(e)[:100]}"
    finally:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)

    return result


def generate_spectrogram(audio_path: str, output_path: str) -> bool:
    """
    Generate a mel spectrogram image from an audio/video file.
    Returns True if successful.
    """
    wav_path = None
    try:
        import librosa
        import librosa.display
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt

        # If not a WAV file, convert first
        if not audio_path.lower().endswith('.wav'):
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                wav_path = tmp.name
            subprocess.run(
                ['ffmpeg', '-y', '-i', audio_path, '-vn', '-acodec', 'pcm_s16le',
                 '-ar', '22050', '-ac', '1', wav_path],
                capture_output=True, text=True, timeout=60
            )
            load_path = wav_path
        else:
            load_path = audio_path

        y, sr = librosa.load(load_path, sr=22050, mono=True)

        if len(y) < sr * 0.3:
            return False

        # Generate mel spectrogram
        fig, ax = plt.subplots(1, 1, figsize=(10, 4), dpi=100)
        S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128, fmax=8000)
        S_dB = librosa.power_to_db(S, ref=np.max)
        img = librosa.display.specshow(S_dB, sr=sr, x_axis='time', y_axis='mel',
                                        ax=ax, cmap='magma')
        ax.set_title('Mel Spektrogram', fontsize=14)
        ax.set_xlabel('Zaman (s)')
        ax.set_ylabel('Frekans (Hz)')
        fig.colorbar(img, ax=ax, format='%+2.0f dB', label='Güç (dB)')
        fig.tight_layout()
        fig.savefig(output_path, bbox_inches='tight', pad_inches=0.1)
        plt.close(fig)

        return os.path.exists(output_path)

    except Exception as e:
        print(f"[Spectrogram] Hata: {str(e)[:80]}")
        return False
    finally:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)
