import argparse
import sys
import time

import numpy as np
import soundcard as sc


def _mono_int16(block):
    if block is None or len(block) == 0:
        return b""
    arr = np.asarray(block, dtype=np.float32)
    if arr.ndim == 2:
        arr = arr.mean(axis=1)
    arr = np.clip(arr, -1.0, 1.0)
    return (arr * 32767.0).astype("<i2", copy=False).tobytes()


def _find_loopback():
    speaker = sc.default_speaker()
    return sc.get_microphone(speaker.id, include_loopback=True)


def _capture_single(source, sample_rate, chunk):
    device = sc.default_microphone() if source == "microphone" else _find_loopback()
    with device.recorder(samplerate=sample_rate, channels=2, blocksize=chunk) as recorder:
        while True:
            data = recorder.record(numframes=chunk)
            sys.stdout.buffer.write(_mono_int16(data))
            sys.stdout.buffer.flush()


def _capture_mixed(sample_rate, chunk):
    mic = sc.default_microphone()
    loopback = _find_loopback()
    with mic.recorder(samplerate=sample_rate, channels=2, blocksize=chunk) as mic_rec, loopback.recorder(
        samplerate=sample_rate, channels=2, blocksize=chunk
    ) as sys_rec:
        while True:
            mic_data = np.asarray(mic_rec.record(numframes=chunk), dtype=np.float32)
            sys_data = np.asarray(sys_rec.record(numframes=chunk), dtype=np.float32)
            if mic_data.ndim == 2:
                mic_data = mic_data.mean(axis=1)
            if sys_data.ndim == 2:
                sys_data = sys_data.mean(axis=1)
            n = min(len(mic_data), len(sys_data))
            if n <= 0:
                time.sleep(chunk / float(sample_rate))
                continue
            mixed = np.clip((mic_data[:n] + sys_data[:n]) * 0.5, -1.0, 1.0)
            sys.stdout.buffer.write((mixed * 32767.0).astype("<i2", copy=False).tobytes())
            sys.stdout.buffer.flush()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("system", "both"), required=True)
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--chunk", type=int, default=1024)
    args = parser.parse_args()

    if args.mode == "both":
        _capture_mixed(args.sample_rate, args.chunk)
    else:
        _capture_single("system", args.sample_rate, args.chunk)


if __name__ == "__main__":
    main()
